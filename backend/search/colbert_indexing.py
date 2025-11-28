"""
    Keep the following code commented while running on GPU.
"""

# import logging
# import os
# import sys
# import shutil

# # -----------------------------
# # Ensure local ColBERT repo is used
# # -----------------------------
# PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

# from colbert import Indexer
# from colbert.infra import Run, RunConfig, ColBERTConfig
# from backend.fastapi.utils import get_conn

# # -----------------------------
# # Logging and paths
# # -----------------------------
# logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# INDEX_NAME = "colbert_index_new"
# INDEX_ROOT = "backend/search/colbert_index"
# COLLECTION_PATH = "/Users/stupefy/Desktop/Docs/Rutgers/Fall_2025/Data_Management/Course_Project_ATLAS/atlas-ai-kg/collection.tsv"

# # -----------------------------
# # Fetch chunks from Postgres
# # -----------------------------
# def fetch_chunks():
#     logging.info("Fetching chunks from Postgres…")
#     conn = get_conn()
#     cur = conn.cursor()
#     cur.execute("SELECT id::text as chunk_id, text FROM chunk")
#     rows = cur.fetchall()
#     conn.close()
#     logging.info(f"Fetched {len(rows)} chunks.")
#     return [{"chunk_id": r[0], "text": r[1]} for r in rows]


# # -----------------------------
# # Write collection to TSV
# # -----------------------------
# def write_collection(chunks, output_path):
#     logging.info(f"Writing {len(chunks)} chunks to {output_path}")
#     os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
#     # Create mapping file: integer_id -> uuid
#     mapping_path = output_path.replace('.tsv', '_mapping.tsv')
    
#     with open(output_path, 'w', encoding='utf-8') as f, \
#          open(mapping_path, 'w', encoding='utf-8') as m:
        
#         # Write mapping header
#         m.write("integer_id\tuuid\n")
        
#         for i, chunk in enumerate(chunks):
#             # ColBERT v2 expects integer passage IDs starting from 0
#             integer_id = i
#             uuid = chunk['chunk_id']
#             text = chunk['text'].replace('\n', ' ').replace('\t', ' ')
            
#             # Write to collection file (integer_id\ttext)
#             f.write(f"{integer_id}\t{text}\n")
            
#             # Write to mapping file
#             m.write(f"{integer_id}\t{uuid}\n")
    
#     logging.info(f"Collection written to {output_path}")
#     logging.info(f"UUID mapping written to {mapping_path}")


# # -----------------------------
# # Build ColBERT index using v2 API
# # -----------------------------
# def build_colbert_index():
#     # Step 1: Fetch chunks and write collection
#     chunks = fetch_chunks()
#     write_collection(chunks, COLLECTION_PATH)
    
#     # Step 2: Remove old index if exists
#     full_index_path = os.path.join(INDEX_ROOT, INDEX_NAME)
#     if os.path.exists(full_index_path):
#         logging.info(f"Removing existing index folder at {full_index_path}")
#         shutil.rmtree(full_index_path)
    
#     # Step 3: Configure ColBERT v2
#     # Use Run context manager for proper experiment tracking
#     with Run().context(RunConfig(nranks=1, experiment="atlas")):
        
#         config = ColBERTConfig(
#             nbits=2,  # Number of bits for compression (2 or 4)
#             doc_maxlen=180,  # Max document length
#             kmeans_niters=4,  # K-means iterations for clustering
#             checkpoint="colbert-ir/colbertv2.0",  # Pretrained checkpoint
#         )
        
#         logging.info("Creating Indexer...")
#         indexer = Indexer(
#             checkpoint=config.checkpoint,
#             config=config
#         )
        
#         logging.info("Starting indexing process...")
#         indexer.index(
#             name=INDEX_NAME,
#             collection=COLLECTION_PATH,
#             overwrite=True  # Important: allows overwriting existing index
#         )
        
#         logging.info(f"ColBERT index built successfully at: {full_index_path}")
        
#         # Verify index files
#         if os.path.exists(full_index_path):
#             files = os.listdir(full_index_path)
#             logging.info(f"Index directory contains {len(files)} files")
#             logging.info(f"Files: {files[:10]}...")  # Show first 10 files
#         else:
#             logging.error(f"Index directory not found at {full_index_path}")


# # -----------------------------
# # Main
# # -----------------------------
# if __name__ == "__main__":
#     try:
#         logging.info("Starting ColBERT v2 indexing...")
#         build_colbert_index()
#         logging.info("✅ Indexing completed successfully!")
        
#     except Exception as e:
#         logging.error(f"❌ Indexing failed: {e}", exc_info=True)
#         sys.exit(1)


import logging
import os
import sys
import shutil
import torch

# -----------------------------
# Ensure local ColBERT repo is used
# -----------------------------
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

from colbert import Indexer
from colbert.infra import Run, RunConfig, ColBERTConfig
from backend.fastapi.utils import get_conn

# -----------------------------
# Logging and paths
# -----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
INDEX_NAME = "colbert_index_new"
INDEX_ROOT = "backend/search/colbert_index"
COLLECTION_PATH = "/Users/stupefy/Desktop/Docs/Rutgers/Fall_2025/Data_Management/Course_Project_ATLAS/atlas-ai-kg/collection.tsv"

# -----------------------------
# Check CUDA availability
# -----------------------------
def check_cuda():
    """Check if CUDA is available and print GPU info"""
    if torch.cuda.is_available():
        gpu_count = torch.cuda.device_count()
        gpu_name = torch.cuda.get_device_name(0)
        cuda_version = torch.version.cuda
        
        logging.info("="*60)
        logging.info("🚀 CUDA IS AVAILABLE!")
        logging.info("="*60)
        logging.info(f"GPU Count: {gpu_count}")
        logging.info(f"GPU Name: {gpu_name}")
        logging.info(f"CUDA Version: {cuda_version}")
        logging.info(f"PyTorch Version: {torch.__version__}")
        
        # Print memory info
        for i in range(gpu_count):
            mem_allocated = torch.cuda.memory_allocated(i) / 1024**3
            mem_reserved = torch.cuda.memory_reserved(i) / 1024**3
            mem_total = torch.cuda.get_device_properties(i).total_memory / 1024**3
            logging.info(f"GPU {i} Memory: {mem_allocated:.2f}GB / {mem_total:.2f}GB")
        
        logging.info("="*60)
        return True, gpu_count
    else:
        logging.warning("="*60)
        logging.warning("⚠️  CUDA NOT AVAILABLE - Running on CPU")
        logging.warning("="*60)
        logging.warning("This will be significantly slower.")
        logging.warning("To use GPU:")
        logging.warning("  1. Ensure you have an NVIDIA GPU")
        logging.warning("  2. Install CUDA toolkit")
        logging.warning("  3. Install PyTorch with CUDA: pip install torch --index-url https://download.pytorch.org/whl/cu118")
        logging.warning("="*60)
        return False, 0

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
    # Step 0: Check CUDA availability
    has_cuda, gpu_count = check_cuda()
    
    # Step 1: Fetch chunks and write collection
    chunks = fetch_chunks()
    write_collection(chunks, COLLECTION_PATH)
    
    # Step 2: Remove old index if exists
    full_index_path = os.path.join(INDEX_ROOT, INDEX_NAME)
    if os.path.exists(full_index_path):
        logging.info(f"Removing existing index folder at {full_index_path}")
        shutil.rmtree(full_index_path)
    
    # Step 3: Configure ColBERT v2
    # Adjust nranks based on available GPUs
    nranks = gpu_count if has_cuda and gpu_count > 0 else 1
    
    logging.info(f"Configuring ColBERT with {nranks} rank(s)...")
    
    # Use Run context manager for proper experiment tracking
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
        
        # Track GPU memory if CUDA is available
        if has_cuda:
            torch.cuda.reset_peak_memory_stats()
            start_mem = torch.cuda.memory_allocated() / 1024**3
            logging.info(f"GPU memory before indexing: {start_mem:.2f}GB")
        
        indexer.index(
            name=INDEX_NAME,
            collection=COLLECTION_PATH,
            overwrite=True  # Important: allows overwriting existing index
        )
        
        if has_cuda:
            end_mem = torch.cuda.memory_allocated() / 1024**3
            peak_mem = torch.cuda.max_memory_allocated() / 1024**3
            logging.info(f"GPU memory after indexing: {end_mem:.2f}GB")
            logging.info(f"Peak GPU memory used: {peak_mem:.2f}GB")
        
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
