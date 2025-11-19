import spacy
import psycopg2
import os
import logging
from psycopg2.extras import execute_values
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
        logging.info("Connected to PostgreSQL successfully.")
    except psycopg2.OperationalError as e:
        logging.error(f"Postgres connection failed: {e}")
        return None

    # --- Ingest into Postgres ---
    try:
        document_id, chunks = ingest_pdf(path)
        if not document_id or not chunks:
            logging.warning(f"No chunks inserted for '{path}', skipping Neo4j ingestion.")
            conn.close()
            return None
    except Exception as e:
        logging.error(f"Error during PDF ingestion: {e}")
        conn.close()
        return None

    # --- Prepare entity insert buffer ---
    entity_records = []
    chunk_entity_records = []

    # --- NER + Neo4j ---
    with driver.session() as session:
        for i, (chunk_id, text) in enumerate(chunks):
            if not text.strip():
                logging.info(f"Skipping empty chunk {i}")
                continue

            try:
                # Upsert chunk node in Neo4j
                session.execute_write(upsert_chunk, f"{document_id}_{i}", text)

                # Apply NER
                doc = nlp(text)
                if not doc.ents:
                    continue

                logging.info(f"Found {len(doc.ents)} entities in chunk {i}")

                for ent in doc.ents:
                    name, etype = ent.text.strip(), ent.label_

                    # Skip short or junk entities
                    if len(name) < 2:
                        continue

                    # Collect for Postgres
                    entity_records.append((name, etype))
                    chunk_entity_records.append((chunk_id, name))

                    # Upsert into Neo4j
                    session.execute_write(upsert_entity, name, etype)
                    session.execute_write(upsert_mention, f"{document_id}_{i}", name)

            except Exception as e:
                logging.error(f"Failed processing chunk {i}: {e}")
                continue

    # --- Insert into Postgres tables ---
    try:
        # --- Insert entities ---
        if entity_records:
            # Deduplicate by entity name
            unique_entities = {e[0]: e for e in entity_records}.values()
            execute_values(cur, """
                INSERT INTO entity (name, type)
                VALUES %s
                ON CONFLICT (name) DO UPDATE SET type = EXCLUDED.type
            """, list(unique_entities))
            logging.info(f"Inserted {len(unique_entities)} unique entities into PostgreSQL.")

        # --- Insert chunk-entity relations ---
        if chunk_entity_records:
            # Fetch existing chunk UUIDs from Postgres
            cur.execute("SELECT id::text FROM chunk")
            existing_chunks = set(r[0] for r in cur.fetchall())

            # Map Neo4j chunk IDs to actual UUIDs
            mapped_relations = []
            for chunk_id, entity_name in chunk_entity_records:
                actual_uuid = chunk_id.split("_")[0]  # Extract the UUID part
                if actual_uuid in existing_chunks:
                    mapped_relations.append((actual_uuid, entity_name))

            if mapped_relations:
                execute_values(cur, """
                    INSERT INTO chunk_entity (chunk_id, entity_id)
                    SELECT ce.chunk_id::uuid, e.id
                    FROM (VALUES %s) AS ce(chunk_id, entity_name)
                    JOIN entity e ON e.name = ce.entity_name
                    ON CONFLICT DO NOTHING
                """, mapped_relations)
                logging.info(f"Inserted {len(mapped_relations)} chunk-entity links into PostgreSQL.")

        conn.commit()
        logging.info("Successfully committed all entity and chunk-entity inserts.")

    except Exception as e:
        logging.error(f"Postgres insert error: {e}")
        conn.rollback()

    finally:
        conn.close()
        driver.close()

    logging.info(f"Finished ingestion with graph for '{path}'")
    return document_id
