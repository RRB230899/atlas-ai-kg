from fastapi import FastAPI
import psycopg2
from sentence_transformers import SentenceTransformer

app = FastAPI()
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def get_conn():
    return psycopg2.connect(
        dbname="atlas_db",
        user="atlas_user",
        password="atlas_pass",
        host="localhost",
        port=5432
    )

@app.get("/search")
def search(q: str, k: int = 5):
    conn = get_conn()
    cur = conn.cursor()
    emb = model.encode(q).tolist()
    cur.execute(
        "SELECT text FROM chunk ORDER BY embedding <-> %s::vector LIMIT %s",
        (emb, k)
    )
    results = [r[0] for r in cur.fetchall()]
    return {"query": q, "results": results}
