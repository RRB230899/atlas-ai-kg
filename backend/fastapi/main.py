from fastapi import FastAPI, UploadFile, HTTPException, Query
from backend.ingestion.ingest_with_graph import ingest_pdf_with_graph
from backend.fastapi.utils import get_conn, model
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_fixed
from neo4j import GraphDatabase
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
def search(q: str = Query(..., min_length=1), k: int = 5):
    conn = get_conn()
    cur = conn.cursor()
    try:
        emb = model.encode(q).tolist()
        cur.execute(
            "SELECT id, text FROM chunk ORDER BY embedding <-> %s::vector LIMIT %s",
            (emb, k)
        )
        rows = cur.fetchall()
        results = [{"chunk_id": r[0], "text": r[1]} for r in rows]
        if not results:
            raise HTTPException(status_code=404, detail="No similar chunks found")
        return {"query": q, "top_k": k, "results": results}
    finally:
        cur.close()
        conn.close()


# --- Search + entities endpoint ---
@app.get("/search_with_entities")
def search_with_entities(q: str = Query(..., min_length=1), k: int = 5):
    conn = get_conn()
    cur = conn.cursor()
    try:
        emb = model.encode(q).tolist()
        cur.execute(
            "SELECT id, document_id, text FROM chunk ORDER BY embedding <-> %s::vector LIMIT %s",
            (emb, k)
        )
        chunks = cur.fetchall()
        if not chunks:
            raise HTTPException(status_code=404, detail="No similar chunks found")

        driver = get_neo4j_driver()
        try:
            results = []
            with driver.session() as session:
                for chunk_id, doc_id, text in chunks:
                    ents = session.run(
                        "MATCH (c:Chunk {id:$chunk_id})-[:MENTIONS]->(e:Entity) "
                        "RETURN e.name AS entity_name, e.label AS label",
                        chunk_id=str(chunk_id)
                    )
                    entities = [{"name": r["entity_name"], "label": r["label"]} for r in ents]
                    results.append({"chunk_id": str(chunk_id), "document_id": str(doc_id), "text": text, "entities": entities})
            return {"query": q, "top_k": k, "results": results}
        finally:
            driver.close()
    finally:
        cur.close()
        conn.close()
