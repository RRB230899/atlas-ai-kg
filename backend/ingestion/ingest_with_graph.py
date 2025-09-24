import spacy
import psycopg2
import os
from neo4j import GraphDatabase
from ingest import ingest_pdf
from dotenv import load_dotenv

# --- Load spaCy model ---
nlp = spacy.load("en_core_web_sm")

# --- Neo4j Aura connection ---
load_dotenv()

URI = os.getenv("NEO_URI")
USER = os.getenv("NEO_USER")
PASSWORD = os.getenv("NEO_PASSWORD")
driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))


def upsert_entity(tx, name, etype):
    tx.run("""
    MERGE (e:Entity {name: $name})
    SET e.label = $etype
    """, name=name, etype=etype)


def upsert_chunk(tx, chunk_id, text):
    tx.run("""
    MERGE (c:Chunk {id: $chunk_id})
    SET c.text = $text
    """, chunk_id=chunk_id, text=text)


def upsert_mention(tx, chunk_id, entity_name):
    tx.run("""
    MERGE (c:Chunk {id: $chunk_id})
    MERGE (e:Entity {name: $entity_name})
    MERGE (c)-[:MENTIONS]->(e)
    """, chunk_id=chunk_id, entity_name=entity_name)


def ingest_pdf_with_graph(path):
    # --- Connect to Postgres ---
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DBNAME"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host="localhost",
            port=5432
        )
        cur = conn.cursor()
    except psycopg2.OperationalError as e:
        print("❌ Postgres connection failed:", e)
        return

    # --- Ingest into Postgres ---
    document_id, chunks = ingest_pdf(path, conn, cur)
    conn.commit()

    # --- NER + Neo4j ---
    with driver.session() as session:
        for i, chunk in enumerate(chunks):
            doc_id, text = chunk
            print(f"\nProcessing chunk {i} (doc_id={doc_id})...")
            if not text.strip():
                print(f"  Skipping empty chunk {i}")
                continue

            # Upsert chunk
            session.execute_write(upsert_chunk, f"{document_id}_{i}", text)
            print(f"  Upserted chunk {i}")

            doc = nlp(text)
            if not doc.ents:
                print(f"  No entities found in chunk {i}")
            else:
                print(f"  Found {len(doc.ents)} entities in chunk {i}")

            for ent in doc.ents:
                # Upsert entity node
                session.execute_write(upsert_entity, ent.text, ent.label_)
                print(f"    Upserted entity: '{ent.text}' (label={ent.label_})")

                # Link chunk -> entity
                session.execute_write(upsert_mention, f"{document_id}_{i}", ent.text)
                print(f"    Linked chunk {i} -> entity '{ent.text}'")

    conn.close()
    driver.close()
    print(f"Also inserted entities/relations from {path} into Neo4j")


if __name__ == "__main__":
    ingest_pdf_with_graph("atlas-ai-kg/sample.pdf")
