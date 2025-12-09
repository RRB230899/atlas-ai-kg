import os
import psycopg2
import torch
import logging
from dotenv import load_dotenv
from neo4j import Driver
from sentence_transformers import SentenceTransformer
from fastapi import HTTPException
from collections import defaultdict
from typing import List, Dict

# -------------------------
#  LOAD ENV & DEVICE
# -------------------------
load_dotenv()

if torch.backends.mps.is_available():
    DEVICE = "mps"
    print("FastAPI: Using Apple Silicon MPS GPU for embeddings")
else:
    DEVICE = "cpu"
    print("FastAPI: Using CPU for embeddings")

# -------------------------
#  EMBEDDING MODEL
# -------------------------
model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device=DEVICE
)

# -------------------------
#  POSTGRES DATABASE CONNECTION
# -------------------------
def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DBNAME"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host="localhost",
        port=5432
    )

# -------------------------
#  RAG SEARCH FUNCTION
# -------------------------
def search_rag(
    query: str,
    top_docs: int = 5,
    top_chunks: int = 3,
    chunk_pool: int = 200,
    include_entities: bool = True
) -> dict:
    """
    Perform RAG-style search over documents and return top documents with chunks and optional entities.
    
    Parameters:
    - query: str, the user query
    - top_docs: int, number of top documents to return
    - top_chunks: int, number of top chunks per document to keep
    - chunk_pool: int, initial number of chunks to consider for ranking
    - include_entities: bool, whether to include entities in the result

    Returns:
    - dict: {"query": ..., "top_docs": ..., "results": [...]}
    """
    logging.info(f"[search_rag] query='{query}' top_docs={top_docs} top_chunks={top_chunks} "
                 f"chunk_pool={chunk_pool} include_entities={include_entities}")

    # 1️⃣ Embed query
    emb = model.encode(query).tolist()
    if len(emb) != 384:
        raise HTTPException(status_code=400, detail=f"Embedding dimension mismatch: expected 384, got {len(emb)}")

    conn = get_conn()
    cur = conn.cursor()
    try:
        # 2️⃣ Fetch top chunk_pool chunks
        cur.execute(
            """
            SELECT c.id::text AS chunk_id,
                   c.document_id::text AS document_id,
                   c.ord,
                   c.text,
                   (c.embedding <-> %s::vector) AS distance
            FROM chunk c
            ORDER BY c.embedding <-> %s::vector
            LIMIT %s;
            """,
            (emb, emb, chunk_pool)
        )
        rows = cur.fetchall()
        if not rows:
            return {"query": query, "top_docs": top_docs, "results": []}

        # 3️⃣ Aggregate chunks by document
        docs_tmp = defaultdict(lambda: {"chunks": [], "agg_scores": []})
        for chunk_id, document_id, ord_, text, distance in rows:
            docs_tmp[document_id]["chunks"].append({
                "chunk_id": chunk_id, 
                "ord": int(ord_) if ord_ is not None else 0, 
                "text": text, 
                "distance": float(distance)
            })
            docs_tmp[document_id]["agg_scores"].append(float(distance))

        # 4️⃣ Keep top_chunks per document & compute avg distance
        docs_list = []
        for doc_id, info in docs_tmp.items():
            sorted_chunks = sorted(info["chunks"], key=lambda x: x["distance"])[:top_chunks]
            avg_distance = sum(c["distance"] for c in sorted_chunks) / len(sorted_chunks)
            docs_list.append({
                "document_id": doc_id,
                "avg_distance": avg_distance,
                "chunks": sorted_chunks
            })

        # 5️⃣ Sort by avg_distance and select top_docs
        docs_list = sorted(docs_list, key=lambda x: x["avg_distance"])[:top_docs]
        selected_doc_ids = [d["document_id"] for d in docs_list]

        # 6️⃣ Fetch document metadata
        cur.execute(
            """
            SELECT id::text, title, source_url, sha256
            FROM document
            WHERE id::text = ANY(%s)
            """,
            (selected_doc_ids,)
        )
        meta_map = {r[0]: {"title": r[1], "source_url": r[2], "sha256": r[3]} for r in cur.fetchall()}

        # 7️⃣ Fetch entities if requested
        entities_map = defaultdict(list)
        if include_entities:
            sel_chunk_ids = [c["chunk_id"] for d in docs_list for c in d["chunks"]]
            if sel_chunk_ids:
                cur.execute(
                    """
                    SELECT ce.chunk_id::text, e.name, e.type
                    FROM chunk_entity ce
                    JOIN entity e ON e.id = ce.entity_id
                    WHERE ce.chunk_id::text = ANY(%s)
                    """,
                    (sel_chunk_ids,)
                )
                chunk_to_entities = defaultdict(list)
                for chunk_id, name, etype in cur.fetchall():
                    chunk_to_entities[chunk_id].append({"name": name, "type": etype})

                for d in docs_list:
                    seen = set()
                    for c in d["chunks"]:
                        for ent in chunk_to_entities.get(c["chunk_id"], []):
                            key = (ent["name"], ent["type"])
                            if key not in seen:
                                seen.add(key)
                                entities_map[d["document_id"]].append({"name": ent["name"], "type": ent["type"]})

        # 8️⃣ Build final results
        results = []
        for d in docs_list:
            doc_id = d["document_id"]
            meta = meta_map.get(doc_id, {})
            results.append({
                "document_id": doc_id,
                "title": meta.get("title"),
                "source_url": meta.get("source_url"),
                "sha256": meta.get("sha256"),
                "avg_distance": d["avg_distance"],
                "chunks": d["chunks"],
                "entities": entities_map.get(doc_id, [])
            })

        return {"query": query, "top_docs": top_docs, "results": results}

    finally:
        cur.close()
        conn.close()


# -------------------------
#  Neo4j GRAPH FUNCTION
# -------------------------
_GRAPH_CYPHER = """
UNWIND $keys AS k
MATCH (d:Document {sha256: k.sha256})-[:HAS_CHUNK]->(c:Chunk {ord: toInteger(k.ord)})
OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity)
WITH d, c, collect(DISTINCT e)[..$maxEntPerChunk] AS ents

// Build node maps (string IDs for Cytoscape) with enhanced labels and metadata
WITH
  collect(DISTINCT {
    id: 'doc:' + coalesce(d.sha256, '(missing)'),
    label: coalesce(d.title, '(doc)'),
    type: 'doc',
    sha256: d.sha256,
    fullTitle: d.title,
    sourceUrl: d.source_url
  }) AS docNodes,
  collect(DISTINCT {
    id: 'chunk:' + coalesce(d.sha256, '(missing)') + ':' + toString(c.ord),
    label: substring(coalesce(c.text, ''), 0, 80) + CASE WHEN size(coalesce(c.text, '')) > 80 THEN '...' ELSE '' END,
    type: 'chunk',
    sha256: d.sha256,
    ord: toInteger(c.ord),
    preview: substring(coalesce(c.text, ''), 0, 200) + CASE WHEN size(coalesce(c.text, '')) > 200 THEN '...' ELSE '' END
  }) AS chunkNodes,
  apoc.coll.toSet(
    apoc.coll.flatten(
      collect(
        [x IN ents |
          {
            id: 'entity:' + coalesce(elementId(x), '(missing)'),
            label: x.name + ' (' + coalesce(x.type, 'unknown') + ')',
            type: 'entity',
            entityType: coalesce(x.type, 'unknown'),
            name: x.name
          }
        ]
      )
    )
  ) AS entNodes,
  collect(DISTINCT {
    s: 'doc:' + coalesce(d.sha256, '(missing)'),
    t: 'chunk:' + coalesce(d.sha256, '(missing)') + ':' + toString(c.ord),
    label: 'HAS_CHUNK'
  }) AS docChunkEdges,
  apoc.coll.flatten(
    collect(
      [x IN ents |
        {
          s: 'chunk:' + coalesce(d.sha256, '(missing)') + ':' + toString(c.ord),
          t: 'entity:' + coalesce(elementId(x), '(missing)'),
          label: 'MENTIONS'
        }
      ]
    )
  ) AS entChunkEdges

RETURN
  docNodes AS docs,
  chunkNodes AS chunks,
  entNodes AS entities,
  apoc.coll.toSet(docChunkEdges) AS docChunkEdges,
  apoc.coll.toSet(entChunkEdges) AS entChunkEdges
"""

def build_graph_for_chunks(
    chunk_keys: List[Dict[str, any]],
    max_ent_per_chunk: int = 4,
    max_com_edges: int = 150,
    neo_driver: Driver = None
):
    """
    Build a Cytoscape-compatible graph from chunk keys.
    
    Parameters:
    - chunk_keys: List of dicts with 'sha256' and 'ord' fields
    - max_ent_per_chunk: Maximum entities to include per chunk
    - max_com_edges: Unused (kept for backward compatibility)
    - neo_driver: Neo4j driver instance
    
    Returns:
    - dict: {"nodes": [...], "edges": [...]}
    """
    if not neo_driver:
        raise RuntimeError("Neo4j driver not provided to build_graph_for_chunks")

    elements = {"nodes": [], "edges": []}
    added_nodes, added_edges = set(), set()

    # Validate and clean chunk_keys
    valid_keys = []
    for key in chunk_keys:
        if key.get("sha256") and key.get("ord") is not None:
            try:
                valid_keys.append({
                    "sha256": str(key["sha256"]),
                    "ord": int(key["ord"])
                })
            except (ValueError, TypeError) as e:
                logging.warning(f"Invalid chunk key {key}: {e}")
                continue

    if not valid_keys:
        logging.warning("No valid chunk keys provided to build_graph_for_chunks")
        return elements

    try:
        with neo_driver.session() as s:
            rec = s.run(
                _GRAPH_CYPHER,
                keys=valid_keys,
                maxEntPerChunk=max_ent_per_chunk
            ).single()

        if not rec:
            logging.warning("No graph data returned from Neo4j")
            return elements

        docs = rec.get("docs") or []
        chunks = rec.get("chunks") or []
        ents = rec.get("entities") or []
        dce = rec.get("docChunkEdges") or []
        ece = rec.get("entChunkEdges") or []

        # Add nodes
        for n in (docs + chunks + ents):
            nid = n.get("id")
            if nid and nid not in added_nodes:
                node_data = {
                    "id": nid,
                    "label": n.get("label", ""),
                    "type": n.get("type", "")
                }
                
                # Add additional metadata based on node type
                if n.get("type") == "doc":
                    node_data["fullTitle"] = n.get("fullTitle")
                    node_data["sourceUrl"] = n.get("sourceUrl")
                elif n.get("type") == "chunk":
                    node_data["ord"] = n.get("ord")
                    node_data["preview"] = n.get("preview")
                    node_data["sha256"] = n.get("sha256")
                elif n.get("type") == "entity":
                    node_data["entityType"] = n.get("entityType")
                    node_data["name"] = n.get("name")
                
                elements["nodes"].append({"data": node_data})
                added_nodes.add(nid)

        # Add edges
        for e in (dce + ece):
            source = e.get("s")
            target = e.get("t")
            if source and target:
                eid = f"e:{source}->{target}:{e.get('label', '')}"
                if eid not in added_edges:
                    elements["edges"].append({
                        "data": {
                            "id": eid,
                            "source": source,
                            "target": target,
                            "label": e.get("label", "")
                        }
                    })
                    added_edges.add(eid)

        logging.info(f"Built graph with {len(elements['nodes'])} nodes and {len(elements['edges'])} edges")

    except Exception as e:
        logging.error(f"Error building graph: {e}")
        raise

    return elements
    