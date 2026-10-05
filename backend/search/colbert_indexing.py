"""Build a ColBERT v2 index over every chunk stored in Postgres.

Runs on CPU or GPU: the number of ranks follows the number of CUDA devices.
"""
import logging
import os
import shutil
import sys

import torch
from colbert import Indexer
from colbert.infra import Run, RunConfig, ColBERTConfig

from backend.db import get_conn

# -----------------------------
# Logging and paths
# -----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
INDEX_NAME = "colbert_index_new"
INDEX_ROOT = "backend/search/colbert_index"
# The passage collection is written here before indexing.
COLLECTION_PATH = os.getenv("ATLAS_COLLECTION_PATH", os.path.join(INDEX_ROOT, "collection.tsv"))

# -----------------------------
# Fetch chunks from Postgres
# -----------------------------
def fetch_chunks():
    logging.info("Fetching chunks from Postgres…")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id::text as chunk_id, text FROM chunk")
    rows = cur.fetchall()
    conn.close()
    logging.info(f"Fetched {len(rows)} chunks.")
    return [{"chunk_id": r[0], "text": r[1]} for r in rows]


# -----------------------------
# Write collection to TSV
# -----------------------------
def write_collection(chunks, output_path):
    logging.info(f"Writing {len(chunks)} chunks to {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Create mapping file: integer_id -> uuid
    mapping_path = output_path.replace('.tsv', '_mapping.tsv')
    
    with open(output_path, 'w', encoding='utf-8') as f, \
         open(mapping_path, 'w', encoding='utf-8') as m:
        
        # Write mapping header
        m.write("integer_id\tuuid\n")
        
        for i, chunk in enumerate(chunks):
            # ColBERT v2 expects integer passage IDs starting from 0
            integer_id = i
            uuid = chunk['chunk_id']
            text = chunk['text'].replace('\n', ' ').replace('\t', ' ')
            
            # Write to collection file (integer_id\ttext)
            f.write(f"{integer_id}\t{text}\n")
            
            # Write to mapping file
            m.write(f"{integer_id}\t{uuid}\n")
    
    logging.info(f"Collection written to {output_path}")
    logging.info(f"UUID mapping written to {mapping_path}")


# -----------------------------
# Build ColBERT index using v2 API
# -----------------------------
def build_colbert_index():
    # Step 1: Fetch chunks and write collection
    chunks = fetch_chunks()
    write_collection(chunks, COLLECTION_PATH)
    
    # Step 2: Remove old index if exists
    full_index_path = os.path.join(INDEX_ROOT, INDEX_NAME)
    if os.path.exists(full_index_path):
        logging.info(f"Removing existing index folder at {full_index_path}")
        shutil.rmtree(full_index_path)
    
    # Step 3: Configure ColBERT v2
    # Use Run context manager for proper experiment tracking
    nranks = torch.cuda.device_count() if torch.cuda.is_available() else 1
    logging.info(f"Indexing with {nranks} rank(s)")
    with Run().context(RunConfig(nranks=nranks, experiment="atlas")):
        
        config = ColBERTConfig(
            nbits=2,  # Number of bits for compression (2 or 4)
            doc_maxlen=180,  # Max document length
            kmeans_niters=4,  # K-means iterations for clustering
            checkpoint="colbert-ir/colbertv2.0",  # Pretrained checkpoint
        )
        
        logging.info("Creating Indexer...")
        indexer = Indexer(
            checkpoint=config.checkpoint,
            config=config
        )
        
        logging.info("Starting indexing process...")
        indexer.index(
            name=INDEX_NAME,
            collection=COLLECTION_PATH,
            overwrite=True  # Important: allows overwriting existing index
        )
        
        logging.info(f"ColBERT index built successfully at: {full_index_path}")
        
        # Verify index files
        if os.path.exists(full_index_path):
            files = os.listdir(full_index_path)
            logging.info(f"Index directory contains {len(files)} files")
            logging.info(f"Files: {files[:10]}...")  # Show first 10 files
        else:
            logging.error(f"Index directory not found at {full_index_path}")


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    try:
        logging.info("Starting ColBERT v2 indexing...")
        build_colbert_index()
        logging.info("✅ Indexing completed successfully!")
        
    except Exception as e:
        logging.error(f"❌ Indexing failed: {e}", exc_info=True)
        sys.exit(1)
