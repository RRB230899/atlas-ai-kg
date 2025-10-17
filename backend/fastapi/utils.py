import psycopg2
from sentence_transformers import SentenceTransformer

# Load model once
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def get_conn():
    return psycopg2.connect(
        dbname="atlas_db",
        user="atlas_user",
        password="atlas_pass",
        host="localhost",
        port=5432
    )
