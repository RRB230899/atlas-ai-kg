import logging
import pandas as pd
import numpy as np
from backend.fastapi.utils import get_conn
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO)


def bulk_insert(parquet_path):
    logging.info("Loading parquet file…")
    df = pd.read_parquet(parquet_path)
    logging.info(f"Loaded {len(df)} chunk rows")

    conn = get_conn()
    cur = conn.cursor()

    # ---- Insert Documents ----
    docs = df[["filename", "document_sha"]].drop_duplicates()

    logging.info(f"Inserting {len(docs)} document rows…")

    execute_values(cur, """
        INSERT INTO document (title, sha256, mime_type)
        VALUES %s
        ON CONFLICT (sha256) DO NOTHING
    """, [
        (row.filename, row.document_sha, "application/pdf")
        for row in docs.itertuples()
    ])

    conn.commit()

    # Fetch doc_id mapping
    cur.execute("SELECT id, sha256 FROM document")
    doc_map = {sha: doc_id for doc_id, sha in cur.fetchall()}

    # ---- Insert chunks ----
    logging.info("Preparing chunks for insert…")

    chunk_rows = []
    for row in df.itertuples():
        if row.document_sha not in doc_map:
            continue

        clean_text = row.text.replace("\x00", "").replace("\u0000", "").strip()

        emb = row.embedding
        if isinstance(emb, np.ndarray):
            emb = emb.tolist()

        chunk_rows.append((
            doc_map[row.document_sha],
            row.chunk_ord,
            clean_text,
            len(clean_text.split()),
            emb
        ))
    logging.info(f"Inserting {len(chunk_rows)} chunks…")

    execute_values(cur, """
        INSERT INTO chunk (document_id, ord, text, token_count, embedding)
        VALUES %s
        ON CONFLICT (document_id, ord) DO NOTHING
    """, chunk_rows, page_size=500)

    conn.commit()
    cur.close()
    conn.close()

    logging.info("🔥 Bulk insert complete!")


if __name__ == "__main__":
    bulk_insert("atlas_embeddings.parquet")
