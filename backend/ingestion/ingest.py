import os
import hashlib
import logging

import fitz  # PyMuPDF
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

import torch
from sentence_transformers import SentenceTransformer

# --- Setup logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Load environment variables
load_dotenv()

if torch.backends.mps.is_available():
    DEVICE = "mps"
    logging.info("Using Apple Silicon MPS GPU for embeddings")
else:
    DEVICE = "cpu"
    logging.info("Using CPU for embeddings")

# -----------------------------
#  LOAD EMBEDDING MODEL (ONCE)
# -----------------------------
model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device=DEVICE,
)

# -----------------------------
#  DATABASE CONNECTION
# -----------------------------
def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DBNAME"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host="localhost",
        port=5432,
    )


# -----------------------------
#  TEXT CHUNKING
# -----------------------------
def chunk_text(text, size=300, overlap=50):
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(1, size - overlap)
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + size]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


# -----------------------------
#  MAIN INGEST FUNCTION
# -----------------------------
def ingest_pdf(path):
    """
    Mac version:
    - No large GPU batching (offloaded to Colab later)
    - Stable with Apple's MPS backend
    """

    logging.info(f"Starting ingestion for: {path}")

    # --- Extract PDF text ---
    try:
        doc = fitz.open(path)
    except Exception as e:
        logging.error(f"Failed to open PDF '{path}': {e}")
        return None, []

    text = " ".join(page.get_text() for page in doc).strip()
    if not text:
        logging.warning(f"No text found in '{path}', skipping")
        return None, []

    # Compute SHA
    sha = hashlib.sha256(text.encode()).hexdigest()

    # --- Insert document record ---
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO document (title, mime_type, sha256)
            VALUES (%s, %s, %s)
            ON CONFLICT (sha256) DO UPDATE SET title = EXCLUDED.title
            RETURNING id
            """,
            (path, "application/pdf", sha),
        )
        document_id = cur.fetchone()[0]
        logging.info(f"Inserted document → ID: {document_id}")

    except Exception as e:
        logging.error(f"Failed inserting document: {e}")
        conn.close()
        return None, []

    # --- Chunk text ---
    chunks = chunk_text(text)
    if not chunks:
        logging.warning(f"No chunks generated for '{path}'")
        conn.close()
        return document_id, []

    logging.info(f"Created {len(chunks)} chunks. Starting MPS/CPU embedding…")

    # --- Encode chunks (one by one on Mac for stability) ---
    inserted_chunks = []

    for i, ctext in enumerate(chunks):
        try:
            emb = model.encode([ctext])[0].tolist()

            cur.execute(
                """
                INSERT INTO chunk (document_id, ord, text, token_count, embedding)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (document_id, ord) DO NOTHING
                RETURNING id
                """,
                (document_id, i, ctext, len(ctext.split()), emb),
            )

            row = cur.fetchone()
            if row:
                chunk_id = row[0]
                inserted_chunks.append((chunk_id, ctext))
                logging.info(f"Inserted chunk {i} → ID: {chunk_id}")

        except Exception as e:
            logging.error(f"Failed to insert chunk {i}: {e}")
            continue

    conn.commit()
    cur.close()
    conn.close()

    logging.info(
        f"Finished ingestion for '{path}' --> {len(inserted_chunks)} / {len(chunks)} chunks stored."
    )
    return document_id, inserted_chunks
