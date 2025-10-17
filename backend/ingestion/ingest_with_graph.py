import spacy
import psycopg2
import os
import logging
from .ingest import ingest_pdf

# --- Setup logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- Load spaCy model ---
try:
    nlp = spacy.load("en_core_web_lg")
except Exception as e:
    logging.error(f"Failed to load spaCy model: {e}")
    raise

# --- Neo4j helper functions ---
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


def ingest_pdf_with_graph(path, driver):
    logging.info(f"Starting ingestion with graph for '{path}'")

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
        logging.error(f"Postgres connection failed: {e}")
        return None

    # --- Ingest into Postgres ---
    document_id, chunks = ingest_pdf(path)
    if not document_id or not chunks:
        logging.warning(f"No chunks inserted for '{path}', skipping Neo4j ingestion.")
        conn.close()
        return None

    # --- NER + Neo4j ---
    with driver.session() as session:
        for i, chunk in enumerate(chunks):
            chunk_id, text = chunk
            if not text.strip():
                logging.info(f"Skipping empty chunk {i}")
                continue

            try:
                # Upsert chunk node
                session.execute_write(upsert_chunk, f"{document_id}_{i}", text)
                logging.info(f"Upserted chunk node {i} (ID={document_id}_{i})")

                # Apply NER
                doc = nlp(text)
                if not doc.ents:
                    logging.info(f"No entities found in chunk {i}")
                    continue

                logging.info(f"Found {len(doc.ents)} entities in chunk {i}")
                for ent in doc.ents:
                    # Upsert entity node
                    session.execute_write(upsert_entity, ent.text, ent.label_)
                    logging.info(f"Upserted entity '{ent.text}' (label={ent.label_})")

                    # Link chunk -> entity
                    session.execute_write(upsert_mention, f"{document_id}_{i}", ent.text)
                    logging.info(f"Linked chunk {i} -> entity '{ent.text}'")

            except Exception as e:
                logging.error(f"Failed processing chunk {i}: {e}")
                continue

    conn.close()
    driver.close()
    logging.info(f"Finished ingestion with graph for '{path}'")
    return document_id
