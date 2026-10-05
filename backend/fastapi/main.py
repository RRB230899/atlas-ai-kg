from fastapi import FastAPI, UploadFile, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from backend.ingestion.ingest_with_graph import ingest_pdf_with_graph
from backend.fastapi.utils import get_conn, model, build_graph_for_chunks, search_rag as rag_search
# from backend.routes.ask_openai import router as ask_openai
from dotenv import load_dotenv
from neo4j import GraphDatabase
from pydantic import BaseModel
import os
import logging
import tempfile

# --- Setup logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("uvicorn.error")

# --- Load Neo4j env ---
load_dotenv()
NEO_URI = os.getenv("NEO_URI")
NEO_USER = os.getenv("NEO_USER")
NEO_PASSWORD = os.getenv("NEO_PASSWORD")

app = FastAPI(title="ATLAS API", version="0.3")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,           # if you ever need cookies/Authorization with fetch(..., credentials:'include')
    allow_methods=["*"],
    allow_headers=["*"],
)
# app.include_router(ask_openai)


class SearchBody(BaseModel):
    q: str
    top_k: int = 5
    use_colbert: bool = False
    with_graph: bool = True


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("REQ %s %s", request.method, request.url.path)
    resp = await call_next(request)
    logger.info("RES %s %s -> %s", request.method, request.url.path, resp.status_code)
    return resp


# --- Neo4j Driver ---
logger.info("Neo4j URI in backend: %s", NEO_URI)
neo_driver = GraphDatabase.driver(NEO_URI, auth=(NEO_USER, NEO_PASSWORD))


@app.on_event("shutdown")
def _close_neo():
    try:
        neo_driver.close()
    except Exception:
        pass


# --- Ingestion endpoint ---
@app.post("/ingest")
async def ingest_file(file: UploadFile):
    # The client controls file.filename, so only its last path component is
    # used, and the upload is written inside a fresh temporary directory.
    safe_name = os.path.basename(file.filename or "") or "upload.pdf"
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_path = os.path.join(tmp_dir, safe_name)
        try:
            with open(temp_path, "wb") as f:
                f.write(await file.read())
            logging.info(f"Received file '{safe_name}', saved to {temp_path}")

            document_id = ingest_pdf_with_graph(temp_path, neo_driver, title=safe_name)
            if document_id is None:
                raise HTTPException(status_code=400, detail="Failed to ingest document. Check logs.")
            logging.info(f"Ingestion successful, document_id={document_id}")
            return {"status": "success", "document_id": document_id, "filename": safe_name}

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Ingestion error: {e}")
            raise HTTPException(status_code=500, detail=f"Ingestion error: {e}")


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
    try:
        with conn.cursor() as cur, neo_driver.session() as session:
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
        with neo_driver.session() as session:
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
    result = rag_search(
        query=q,
        top_docs=top_docs,
        top_chunks=top_chunks,
        chunk_pool=chunk_pool,
        include_entities=include_entities,
    )
    if not result["results"]:
        raise HTTPException(status_code=404, detail="No chunks found in corpus")
    return result


@app.post("/search_rag_plus_graph")
def search_rag_plus_graph(body: SearchBody):
    """
    Combined RAG search + graph visualization endpoint.
    Returns both search hits and a graph of relationships.
    """
    try:
        rag = rag_search(
            query=body.q,           # ✅ Fixed: use 'query' parameter
            top_docs=body.top_k,    # ✅ Number of documents
            top_chunks=3,           # Chunks per document
            chunk_pool=200,         # Initial pool of chunks to consider
            include_entities=True   # Include entity information
        )
    except Exception as e:
        logger.exception("search_rag failed")
        rag = {"results": []}

    # ---- Flatten RAG results to "hits" that the UI understands ----
    hits = []
    for d in rag.get("results", []):
        sha = d.get("sha256")
        title = d.get("title")
        doc_id = d.get("document_id")
        
        for c in d.get("chunks", []):
            hits.append({
                "text": c.get("text", ""),
                "score": -c.get("distance", 0.0),  # Invert distance (smaller = better)
                "sha256": sha,
                "ord": c.get("ord"),
                "chunk_id": c.get("chunk_id"),
                "title": title,
                "document_id": doc_id
            })
    
    # Sort by score (descending) and limit results
    hits = sorted(hits, key=lambda h: h["score"], reverse=True)[: body.top_k * 3]

    # ---- Build knowledge graph if requested ----
    # Graph structure returned:
    # - Document nodes: { id, label (title), type: "doc", fullTitle, sourceUrl }
    # - Chunk nodes: { id, label (80-char preview), type: "chunk", ord, preview (200 chars), sha256 }
    # - Entity nodes: { id, label (name + type), type: "entity", entityType, name }
    # - Edges: { id, source, target, label (relationship type) }
    graph = {"nodes": [], "edges": []}
    if body.with_graph and hits:
        # Build chunk keys for graph construction
        keys = []
        for h in hits:
            sha = h.get("sha256")
            ord_val = h.get("ord")
            
            # Only include if we have both sha256 and ord
            if sha and ord_val is not None:
                try:
                    keys.append({
                        "sha256": str(sha),
                        "ord": int(ord_val)
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid key sha256={sha} ord={ord_val}: {e}")
                    continue

        logger.info(f"Building graph with {len(keys)} chunk keys (sample: {keys[:3]})")

        if keys:
            try:
                graph = build_graph_for_chunks(
                    chunk_keys=keys,
                    max_ent_per_chunk=4,  # Limit entities per chunk to avoid clutter
                    max_com_edges=120,     # Unused but kept for compatibility
                    neo_driver=neo_driver
                )
                logger.info(f"Graph built successfully with enhanced metadata")
            except Exception as e:
                logger.exception("build_graph_for_chunks failed")
                graph = {"nodes": [], "edges": []}

    logger.info(
        f"search_rag_plus_graph: query='{body.q}' hits={len(hits)} "
        f"graph_nodes={len(graph.get('nodes', []))} graph_edges={len(graph.get('edges', []))}"
    )
    
    return {"hits": hits, "graph": graph}
