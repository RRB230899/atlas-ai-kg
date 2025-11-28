"""
Google Colab – Heavy PDF Ingestion Script
-----------------------------------------

This script:
1. Reads batches of PDFs (uploaded or unzipped in Colab)
2. Extracts text using PyMuPDF
3. Splits into 300-word chunks with 50-word overlap
4. Computes embeddings on T4 GPU using SentenceTransformers
5. Saves a single Parquet file containing all chunk-level rows

This file is intended for documentation + reproducibility.
"""

import os
import fitz  # PyMuPDF
import hashlib
import pandas as pd
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import torch


# -----------------------------
#  CONFIG
# -----------------------------

PDF_ROOT = "/content/atlas_work/pdfs"           # folder with unzipped PDFs
PARQUET_OUT = "/content/atlas_work/atlas_embeddings.parquet"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {DEVICE}")

model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device=DEVICE
)


# -----------------------------
#  TEXT CHUNKING
# -----------------------------

def chunk_text(text, size=300, overlap=50):
    """
    Splits text into overlapping word chunks.
    Example:
      size=300, overlap=50 → step = 250
    """
    words = text.split()
    chunks = []
    step = max(1, size - overlap)

    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + size]).strip()
        if chunk:
            chunks.append(chunk)

    return chunks


# -----------------------------
#  GPU BATCH EMBEDDINGS
# -----------------------------

def batch_encode(texts, batch_size=64):
    """
    Encodes list of texts using GPU batching.
    Much faster than per-chunk encoding on CPU.
    """
    all_embs = []

    for i in tqdm(range(0, len(texts), batch_size), desc="Embedding batches"):
        batch = texts[i:i + batch_size]
        embs = model.encode(
            batch,
            batch_size=len(batch),
            convert_to_numpy=True,
            device=DEVICE
        )
        all_embs.extend(embs)

    return all_embs


# -----------------------------
#  MAIN INGEST LOOP
# -----------------------------

records = []

# Collect only .pdf files
pdf_files = [f for f in os.listdir(PDF_ROOT) if f.lower().endswith(".pdf")]
print("Total PDFs detected:", len(pdf_files))

for fname in tqdm(pdf_files, desc="Processing PDFs"):
    path = os.path.join(PDF_ROOT, fname)

    # -------- PDF → TEXT --------
    try:
        doc = fitz.open(path)
        text = " ".join(page.get_text() for page in doc).strip()
    except Exception as e:
        print("⚠️ Failed to read:", fname, e)
        continue

    if not text:
        continue

    # Compute document SHA (dedupe-friendly)
    sha_doc = hashlib.sha256(text.encode()).hexdigest()

    # -------- CHUNKING --------
    chunks = chunk_text(text)
    if not chunks:
        continue

    # -------- EMBEDDINGS --------
    embeddings = batch_encode(chunks, batch_size=64)

    # -------- RECORD CHUNKS --------
    for ord_idx, chunk_text_val in enumerate(chunks):
        text_sha = hashlib.sha256(chunk_text_val.encode()).hexdigest()

        records.append({
            "filename": fname,
            "document_sha": sha_doc,
            "chunk_ord": ord_idx,
            "chunk_sha": text_sha,
            "text": chunk_text_val,
            "embedding": embeddings[ord_idx].tolist()
        })


# -----------------------------
#  SAVE PARQUET
# -----------------------------

df = pd.DataFrame(records)
print("Total chunk rows:", len(df))

df.to_parquet(PARQUET_OUT, index=False)
print(f"✅ Saved Parquet: {PARQUET_OUT}")
