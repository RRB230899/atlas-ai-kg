import fitz  # pymupdf
from sentence_transformers import SentenceTransformer
import psycopg2
import hashlib

# 1. Connect to Postgres
conn = psycopg2.connect(
    dbname="atlas_db",
    user="atlas_user",
    password="atlas_pass",
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

def ingest_pdf(path):
    doc = fitz.open(path)
    text = " ".join([page.get_text() for page in doc])
    sha = hashlib.sha256(text.encode()).hexdigest()

    # Insert into document table
    cur.execute(
        "INSERT INTO document (title, mime_type, sha256) VALUES (%s,%s,%s) RETURNING id",
        (path, "application/pdf", sha)
    )
    document_id = cur.fetchone()[0]

    # Chunk + embed
    chunks = chunk_text(text)
    for i, c in enumerate(chunks):
        emb = model.encode(c).tolist()
        cur.execute(
            "INSERT INTO chunk (document_id, ord, text, token_count, embedding) VALUES (%s,%s,%s,%s,%s)",
            (document_id, i, c, len(c.split()), emb)
        )

    conn.commit()
    print(f"Ingested {len(chunks)} chunks from {path}")

if __name__ == "__main__":
    ingest_pdf("atlas-ai-kg/sample.pdf")
