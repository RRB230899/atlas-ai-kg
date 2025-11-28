from fastapi import FastAPI, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from backend.ingestion.ingest_with_graph import ingest_pdf_with_graph
from backend.fastapi.utils import get_conn, model
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_fixed
from neo4j import GraphDatabase
from collections import defaultdict
import os
import logging

# --- Setup logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- Load Neo4j env ---
load_dotenv()
NEO_URI = os.getenv("NEO_URI")
NEO_USER = os.getenv("NEO_USER")
NEO_PASSWORD = os.getenv("NEO_PASSWORD")

app = FastAPI(title="ATLAS API", version="0.3")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Neo4j Driver with Retries ---
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def get_neo4j_driver():
    return GraphDatabase.driver(NEO_URI, auth=(NEO_USER, NEO_PASSWORD))


# --- Ingestion endpoint ---
@app.post("/ingest")
async def ingest_file(file: UploadFile):
    temp_path = f"/tmp/{file.filename}"
    try:
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        logging.info(f"Received file '{file.filename}', saved to {temp_path}")

        driver = get_neo4j_driver()
        document_id = ingest_pdf_with_graph(temp_path, driver)
        if document_id is None:
            raise HTTPException(status_code=400, detail="Failed to ingest document. Check logs.")
        logging.info(f"Ingestion successful, document_id={document_id}")
        return {"status": "success", "document_id": document_id, "filename": file.filename}

    except Exception as e:
        logging.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion error: {e}")

    finally:
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except Exception: pass
        try: driver.close()
        except Exception: pass


# --- Search endpoint (simple vector search) ---
@app.get("/search")
async def search(q: str = Query(..., min_length=1), k: int = 5):
    logging.info(f"Search query received: {q} | top_k={k}")
    
    emb = model.encode(q).tolist()
    if len(emb) != 384:
        raise HTTPException(status_code=400, detail=f"Embedding dimension mismatch: got {len(emb)}")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, text, embedding <-> %s::vector AS distance
                FROM chunk
                ORDER BY embedding <-> %s::vector
                LIMIT %s
                """,
                (emb, emb, k)
            )
            rows = cur.fetchall()
            results = [{"chunk_id": r[0], "text": r[1], "distance": r[2]} for r in rows]

        if not results:
            raise HTTPException(status_code=404, detail="No similar chunks found")
        return {"query": q, "top_k": k, "results": results}

    finally:
        conn.close()


# --- Search + entities endpoint ---
@app.get("/search_with_entities")
async def search_with_entities(q: str = Query(..., min_length=1), k: int = 5):
    logging.info(f"Search + Entities query received: {q} | top_k={k}")

    emb = model.encode(q).tolist()
    if len(emb) != 384:
        raise HTTPException(status_code=400, detail=f"Embedding dimension mismatch: got {len(emb)}")

    conn = get_conn()
    driver = get_neo4j_driver()
    try:
        with conn.cursor() as cur, driver.session() as session:
            # 1️⃣ Get top-k chunks
            cur.execute(
                """
                SELECT id, document_id, text
                FROM chunk
                ORDER BY embedding <-> %s::vector
                LIMIT %s
                """,
                (emb, k)
            )
            chunks = cur.fetchall()
            if not chunks:
                raise HTTPException(status_code=404, detail="No similar chunks found")

            # 2️⃣ For each chunk, fetch linked entities in Neo4j
            results = []
            for chunk_id, doc_id, text in chunks:
                ents = session.run(
                    """
                    MATCH (c:Chunk {id:$chunk_id})-[:MENTIONS]->(e:Entity)
                    RETURN e.name AS entity_name, e.label AS label
                    """,
                    chunk_id=str(chunk_id)
                )
                entities = [{"name": r["entity_name"], "label": r["label"]} for r in ents]
                results.append({
                    "chunk_id": str(chunk_id),
                    "document_id": str(doc_id),
                    "text": text,
                    "entities": entities
                })

        return {"query": q, "top_k": k, "results": results}

    finally:
        conn.close()
        driver.close()


@app.get("/search_docs")
async def search_docs(q: str = Query(..., min_length=1), top_k_docs: int = 5, top_k_chunks: int = 3):
    """
    Search documents using vector embeddings.
    Returns top documents with their top-k chunks and optional entities.
    """
    emb = model.encode(q).tolist()
    if len(emb) != 384:
        raise HTTPException(status_code=400, detail=f"Embedding dimension mismatch: got {len(emb)}")

    conn = get_conn()
    driver = get_neo4j_driver()
    try:
        with conn.cursor() as cur:
            # Step 1: retrieve top 50 chunks to have a good doc-level aggregation
            cur.execute(
                """
                SELECT document_id, id AS chunk_id, text, embedding <-> %s::vector AS distance
                FROM chunk
                ORDER BY embedding <-> %s::vector
                LIMIT 50
                """,
                (emb, emb)
            )
            rows = cur.fetchall()

        # Step 2: Aggregate by document_id
        doc_map = {}
        for doc_id, chunk_id, text, distance in rows:
            if doc_id not in doc_map:
                doc_map[doc_id] = {"chunks": [], "score_sum": 0}
            doc_map[doc_id]["chunks"].append({"chunk_id": str(chunk_id), "text": text, "distance": distance})
            doc_map[doc_id]["score_sum"] += distance

        # Step 3: Compute avg distance per doc and sort
        docs = []
        for doc_id, info in doc_map.items():
            chunks_sorted = sorted(info["chunks"], key=lambda x: x["distance"])[:top_k_chunks]
            avg_distance = sum(c["distance"] for c in chunks_sorted) / len(chunks_sorted)
            docs.append({"document_id": str(doc_id), "avg_distance": avg_distance, "chunks": chunks_sorted})

        docs_sorted = sorted(docs, key=lambda x: x["avg_distance"])[:top_k_docs]

        # Step 4: Optionally fetch entities per document
        with driver.session() as session:
            for doc in docs_sorted:
                ents = session.run(
                    """
                    MATCH (c:Chunk {document_id:$doc_id})-[:MENTIONS]->(e:Entity)
                    RETURN DISTINCT e.name AS name, e.label AS label
                    """,
                    doc_id=doc["document_id"]
                )
                doc["entities"] = [{"name": r["name"], "label": r["label"]} for r in ents]

        return {"query": q, "top_docs": top_k_docs, "results": docs_sorted}

    finally:
        conn.close()
        driver.close()


@app.get("/search_rag")
def search_rag(
    q: str = Query(..., min_length=1),
    top_docs: int = Query(5, ge=1, le=50),
    top_chunks: int = Query(3, ge=1, le=20),
    chunk_pool: int = Query(200, ge=10, le=2000),
    include_entities: bool = Query(True),
):
    """
    Document-level RAG-ready search.
    - q: query text
    - top_docs: how many documents to return
    - top_chunks: top chunks kept per document (for RAG context)
    - chunk_pool: initial number of top chunks to fetch and aggregate by document (larger pool -> better doc ranking)
    - include_entities: whether to return entity lists per document
    """
    logging.info(f"[search_rag] q='{q}' top_docs={top_docs} top_chunks={top_chunks} chunk_pool={chunk_pool} include_entities={include_entities}")

    # 1) Embed & sanity-check
    emb = model.encode(q).tolist()
    if len(emb) != 384:
        raise HTTPException(status_code=400, detail=f"Embedding dimension mismatch: expected 384, got {len(emb)}")

    conn = get_conn()
    cur = conn.cursor()
    try:
        # 2) Get top chunk_pool chunks (document_id, chunk_id, text, distance)
        cur.execute(
            """
            SELECT c.id::text AS chunk_id,
                   c.document_id::text AS document_id,
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
            raise HTTPException(status_code=404, detail="No chunks found in corpus")

        # 3) Aggregate chunks by document
        docs_tmp = defaultdict(lambda: {"chunks": [], "agg_scores": []})
        chunk_ids = []
        for chunk_id, document_id, text, distance in rows:
            docs_tmp[document_id]["chunks"].append({"chunk_id": chunk_id, "text": text, "distance": float(distance)})
            docs_tmp[document_id]["agg_scores"].append(float(distance))
            chunk_ids.append(chunk_id)

        # 4) For each document, keep the best top_chunks by distance, compute average distance
        docs_list = []
        for doc_id, info in docs_tmp.items():
            # sort ascending by distance (smaller = closer)
            sorted_chunks = sorted(info["chunks"], key=lambda x: x["distance"])[:top_chunks]
            avg_distance = sum(c["distance"] for c in sorted_chunks) / len(sorted_chunks)
            docs_list.append({
                "document_id": doc_id,
                "avg_distance": avg_distance,
                "chunks": sorted_chunks
            })

        # 5) Sort documents by avg_distance and keep top_docs
        docs_list = sorted(docs_list, key=lambda x: x["avg_distance"])[:top_docs]
        selected_doc_ids = [d["document_id"] for d in docs_list]

        # 6) Fetch document metadata (title, source_url, sha256)
        cur.execute(
            """
            SELECT id::text, title, source_url, sha256
            FROM document
            WHERE id::text = ANY(%s)
            """,
            (selected_doc_ids,)
        )
        doc_meta_rows = cur.fetchall()
        meta_map = {r[0]: {"title": r[1], "source_url": r[2], "sha256": r[3]} for r in doc_meta_rows}

        # 7) Optionally, fetch entities from Postgres for the chunks belonging to these documents
        entities_map = defaultdict(list)  # document_id -> list of {name,type,count}
        if include_entities:
            # collect all chunk_ids for selected documents
            sel_chunk_ids = []
            for d in docs_list:
                sel_chunk_ids.extend([c["chunk_id"] for c in d["chunks"]])

            if sel_chunk_ids:
                # fetch entity names/types grouped by chunk_id
                # join chunk_entity -> entity
                cur.execute(
                    """
                    SELECT ce.chunk_id::text, e.name, e.type
                    FROM chunk_entity ce
                    JOIN entity e ON e.id = ce.entity_id
                    WHERE ce.chunk_id::text = ANY(%s)
                    """,
                    (sel_chunk_ids,)
                )
                ent_rows = cur.fetchall()
                # Map chunk -> entities, then aggregate into document level
                chunk_to_entities = defaultdict(list)
                for chunk_id, name, etype in ent_rows:
                    chunk_to_entities[chunk_id].append({"name": name, "type": etype})

                # attach to docs (document level aggregation, uniqueness)
                for d in docs_list:
                    seen = set()
                    for c in d["chunks"]:
                        for ent in chunk_to_entities.get(c["chunk_id"], []):
                            key = (ent["name"], ent["type"])
                            if key in seen:
                                continue
                            seen.add(key)
                            entities_map[d["document_id"]].append({"name": ent["name"], "type": ent["type"]})

        # 8) Build response combining metadata + chunks + entities
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

        return {"query": q, "top_docs": top_docs, "results": results}

    finally:
        cur.close()
        conn.close()
