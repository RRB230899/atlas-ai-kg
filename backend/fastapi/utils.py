import os
import psycopg2
import torch
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Load environment variables
load_dotenv()

if torch.backends.mps.is_available():
    DEVICE = "mps"
    print("FastAPI: Using Apple Silicon MPS GPU for embeddings")
else:
    DEVICE = "cpu"
    print("FastAPI: Using CPU for embeddings")

model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device=DEVICE
)

# -------------------------
#  DATABASE CONNECTION
# -------------------------
def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DBNAME"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host="localhost",
        port=5432
    )
