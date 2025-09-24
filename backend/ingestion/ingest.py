import fitz  # pymupdf
import os
import psycopg2
import hashlib
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# 1. Connect to Postgres
load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DBNAME"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    host="localhost",
    port=5432
)
cur = conn.cursor()

# 2. Load embedding model
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def chunk_text(text, size=300, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunk = " ".join(words[i:i+size])
        chunks.append(chunk)
    return chunks

def ingest_pdf(path, conn, cur):
    doc = fitz.open(path)
    text = " ".join([page.get_text() for page in doc])
    sha = hashlib.sha256(text.encode()).hexdigest()

    # Insert into document table
    cur.execute(
        "INSERT INTO document (title, mime_type, sha256) VALUES (%s,%s,%s) ON CONFLICT (sha256) DO UPDATE SET title = EXCLUDED.title RETURNING id",
        (path, "application/pdf", sha)
    )
    document_id = cur.fetchone()[0]

    # Chunk + embed
    chunks = chunk_text(text)  # assume you already have this helper
    inserted_chunks = []

    for i, c in enumerate(chunks):
        emb = model.encode(c).tolist()
        cur.execute(
            "INSERT INTO chunk (document_id, ord, text, token_count, embedding) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (document_id, i, c, len(c.split()), emb)
        )
        chunk_id = cur.fetchone()[0]
        inserted_chunks.append((chunk_id, c))

    conn.commit()
    print(f"Ingested {len(inserted_chunks)} chunks from {path}")
    return document_id, inserted_chunks

if __name__ == "__main__":
    ingest_pdf("atlas-ai-kg/sample.pdf")
