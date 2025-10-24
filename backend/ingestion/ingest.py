import fitz  # PyMuPDF
import os
import psycopg2
import hashlib
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import logging

# --- Setup logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Load environment variables
load_dotenv()

# Connect to Postgres
def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DBNAME"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host="localhost",
        port=5432
    )

# Load embedding model
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# Split text into overlapping chunks
def chunk_text(text, size=300, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunk = " ".join(words[i:i+size])
        chunks.append(chunk)
    return chunks

def ingest_pdf(path):
    logging.info(f"Starting ingestion for: {path}")
    try:
        doc = fitz.open(path)
    except Exception as e:
        logging.error(f"Failed to open PDF '{path}': {e}")
        return None, []

    # Extract text
    text = " ".join([page.get_text() for page in doc]).strip()
    if not text:
        logging.warning(f"No text found in PDF '{path}', skipping ingestion.")
        return None, []

    # Compute SHA
    sha = hashlib.sha256(text.encode()).hexdigest()

    # Connect to DB
    conn = get_conn()
    cur = conn.cursor()

    # Insert document
    try:
        cur.execute(
            """
            INSERT INTO document (title, mime_type, sha256)
            VALUES (%s, %s, %s)
            ON CONFLICT (sha256) DO UPDATE SET title = EXCLUDED.title
            RETURNING id
            """,
            (path, "application/pdf", sha)
        )
        document_id = cur.fetchone()[0]
        logging.info(f"Document inserted with ID: {document_id}")
    except Exception as e:
        logging.error(f"Failed to insert document '{path}': {e}")
        conn.close()
        return None, []

    # Chunk + embed
    chunks = chunk_text(text)
    inserted_chunks = []

    for i, c in enumerate(chunks):
        if not c.strip():
            logging.info(f"Skipping empty chunk {i}")
            continue

        try:
            emb = model.encode(c).tolist()
            if len(emb) == 0:
                logging.warning(f"Empty embedding for chunk {i}, skipping")
                continue

            cur.execute(
                """
                INSERT INTO chunk (document_id, ord, text, token_count, embedding)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (document_id, ord) DO NOTHING
                RETURNING id
                """,
                (document_id, i, c, len(c.split()), emb)
            )
            result = cur.fetchone()
            if result:
                chunk_id = result[0]
                inserted_chunks.append((chunk_id, c))
                logging.info(f"Inserted chunk {i} with ID: {chunk_id}")
        except Exception as e:
            logging.error(f"Failed to insert chunk {i}: {e}")
            continue

    conn.commit()
    cur.close()
    conn.close()

    logging.info(f"Finished ingestion for '{path}', {len(inserted_chunks)} chunks inserted.")
    return document_id, inserted_chunks
