import psycopg2
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Load model once
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


load_dotenv()
def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DBNAME"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host="localhost",
        port=5432
    )
