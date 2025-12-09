# backend/ingestion/ingest_parquet_to_neo4j.py
import os
import math
import logging
import pandas as pd
import numpy as np
import ast
from typing import List, Any, Iterable, Optional
from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv

# ---------- config ----------
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

NEO4J_URI = os.getenv("NEO_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO_PASSWORD", "test")

EMB_DIM = 384                 # all-MiniLM-L6-v2 default
BATCH_SIZE = 500              # tune as needed
CREATE_VECTOR_INDEX = True    # set False if your Neo4j doesn't support vector indexes
NORMALIZE = False             # set True to L2-normalize embeddings for cosine

# ---------- driver ----------
def get_driver() -> Driver:
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# ---------- schema ----------
CONSTRAINTS = [
    """
    CREATE CONSTRAINT doc_sha_unique IF NOT EXISTS
    FOR (d:Document) REQUIRE d.sha256 IS UNIQUE
    """,
    """
    CREATE CONSTRAINT chunk_doc_ord_unique IF NOT EXISTS
    FOR (c:Chunk) REQUIRE (c.doc_sha, c.ord) IS UNIQUE
    """,
]
VECTOR_INDEX = f"""
CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS {{
  indexConfig: {{
    `vector.dimensions`: {EMB_DIM},
    `vector.similarity_function`: 'cosine'
  }}
}}
"""

def init_schema(driver: Driver) -> None:
    with driver.session() as sess:
        for stmt in CONSTRAINTS:
            try:
                sess.run(stmt).consume()
                logging.info("Applied schema: %s", stmt.splitlines()[1].strip())
            except Exception as e:
                logging.warning("Schema step (constraint) warning: %s", e)

        if CREATE_VECTOR_INDEX:
            try:
                sess.run(VECTOR_INDEX).consume()
                logging.info("Vector index ensured: chunk_embedding")
            except Exception as e:
                logging.warning("Vector index not created (continuing): %s", e)

# ---------- helpers ----------
def as_float_list(x: Any) -> List[float]:
    if isinstance(x, list):
        arr = x
    elif isinstance(x, np.ndarray):
        arr = x.tolist()
    elif isinstance(x, str):
        try:
            arr = ast.literal_eval(x)
        except Exception as e:
            raise ValueError(f"Cannot parse embedding string: {e}")
    else:
        raise ValueError(f"Unsupported embedding type: {type(x)}")
    # validate numbers & non-NaN
    out = []
    for v in arr:
        fv = float(v)
        if math.isnan(fv) or math.isinf(fv):
            raise ValueError("Embedding contains NaN/Inf")
        out.append(fv)
    return out

def l2_normalize(vec: List[float]) -> List[float]:
    norm = math.sqrt(sum(v*v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]

def clean_text(s: Any) -> str:
    s = "" if not isinstance(s, str) else s
    return s.replace("\x00", "").replace("\u0000", "").strip()

def chunk_iter(df: pd.DataFrame, size: int) -> Iterable[pd.DataFrame]:
    n = len(df)
    for i in range(0, n, size):
        yield df.iloc[i:i+size]

# ---------- cypher ----------
DOC_MERGE_CYPHER = """
UNWIND $rows AS row
MERGE (d:Document {sha256: row.sha256})
ON CREATE SET
  d.title = row.title,
  d.mime_type = row.mime_type
"""

CHUNK_MERGE_CYPHER = """
UNWIND $rows AS row
MERGE (d:Document {sha256: row.sha256})
MERGE (c:Chunk {doc_sha: row.sha256, ord: row.ord})
ON CREATE SET
  c.text = row.text,
  c.token_count = row.token_count,
  c.embedding = row.embedding
ON MATCH SET
  c.text = coalesce(row.text, c.text),
  c.token_count = coalesce(row.token_count, c.token_count)
MERGE (d)-[:HAS_CHUNK]->(c)
"""

KNN_QUERY = """
CALL db.index.vector.queryNodes('chunk_embedding', $k, $query) YIELD node, score
RETURN node.doc_sha AS doc_sha, node.ord AS ord, score, node.text AS text
LIMIT $k
"""

# ---------- tx functions ----------
def _tx_merge_docs(tx, rows):
    tx.run(DOC_MERGE_CYPHER, rows=rows)

def _tx_merge_chunks(tx, rows):
    tx.run(CHUNK_MERGE_CYPHER, rows=rows)

# ---------- main ----------
def ingest_parquet_to_neo4j(parquet_path: str, limit: Optional[int] = None, dry_run: bool = False) -> None:
    logging.info("Loading parquet: %s", parquet_path)
    df = pd.read_parquet(parquet_path)
    if limit:
        df = df.head(limit)
    logging.info("Loaded %d rows", len(df))

    required = {"filename", "document_sha", "chunk_ord", "text", "embedding"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in parquet: {missing}")

    # preprocess
    df = df.copy()
    df["text"] = df["text"].map(clean_text)
    df["token_count"] = df["text"].map(lambda t: int(len(t.split())))
    df["embedding"] = df["embedding"].map(as_float_list)
    if NORMALIZE:
        df["embedding"] = df["embedding"].map(l2_normalize)

    bad_dim = df["embedding"].map(len) != EMB_DIM
    if bad_dim.any():
        idx = bad_dim[bad_dim].index[:5].tolist()
        raise ValueError(f"Embeddings with wrong dim (expected {EMB_DIM}); rows like: {idx}")

    docs = (
        df[["filename", "document_sha"]]
        .drop_duplicates()
        .rename(columns={"filename": "title", "document_sha": "sha256"})
    )
    docs["mime_type"] = "application/pdf"

    chunks = df.rename(columns={"document_sha": "sha256", "chunk_ord": "ord"})[
        ["sha256", "ord", "text", "token_count", "embedding"]
    ]

    driver = get_driver()
    init_schema(driver)

    if dry_run:
        logging.info("[DRY RUN] Would merge %d documents, %d chunks", len(docs), len(chunks))
        return

    # documents
    logging.info("Merging %d Document nodes…", len(docs))
    with driver.session() as sess:
        for batch in chunk_iter(docs, BATCH_SIZE):
            rows = batch.to_dict("records")
            sess.execute_write(_tx_merge_docs, rows)

    # chunks
    logging.info("Merging %d Chunk nodes…", len(chunks))
    with driver.session() as sess:
        for batch in chunk_iter(chunks, BATCH_SIZE):
            rows = batch.to_dict("records")
            sess.execute_write(_tx_merge_chunks, rows)

    logging.info("🔥 Neo4j ingestion complete!")

def knn_example(query_vec: List[float], k: int = 5):
    driver = get_driver()
    with driver.session() as sess:
        res = sess.run(KNN_QUERY, k=k, query=query_vec).data()
    return res

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("parquet", help="Path to parquet file, e.g., atlas_embeddings.parquet")
    p.add_argument("--limit", type=int, default=None, help="Limit rows for a quick test")
    p.add_argument("--dry-run", action="store_true", help="Load and validate only; don't write")
    p.add_argument("--normalize", action="store_true", help="L2-normalize embeddings (overrides NORMALIZE)")
    p.add_argument("--no-vector-index", action="store_true", help="Skip creating vector index")
    args = p.parse_args()

    if args.normalize:
        NORMALIZE = True
    if args.no_vector_index:
        CREATE_VECTOR_INDEX = False

    ingest_parquet_to_neo4j(args.parquet, limit=args.limit, dry_run=args.dry_run)
