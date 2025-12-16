"""
Database Initialization Script for ATLAS
Creates necessary tables, indexes, and extensions in PostgreSQL.
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "atlas")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


def create_database():
    """Create the database if it doesn't exist."""
    try:
        # Connect to postgres database to create atlas database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database="postgres",
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'")
        exists = cur.fetchone()
        
        if not exists:
            cur.execute(f"CREATE DATABASE {DB_NAME}")
            logger.info(f"✓ Database '{DB_NAME}' created successfully")
        else:
            logger.info(f"✓ Database '{DB_NAME}' already exists")
        
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        raise


def init_schema():
    """Initialize database schema with tables, extensions, and indexes."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        # Enable pgvector extension
        logger.info("Enabling pgvector extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        logger.info("✓ pgvector extension enabled")
        
        # Create document table
        logger.info("Creating document table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS document (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title TEXT NOT NULL,
                mime_type TEXT DEFAULT 'application/pdf',
                sha256 TEXT UNIQUE NOT NULL,
                source_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("✓ document table created")
        
        # Create chunk table with vector embeddings
        logger.info("Creating chunk table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chunk (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE,
                ord INT NOT NULL,
                text TEXT NOT NULL,
                token_count INT NOT NULL,
                embedding vector(384),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(document_id, ord)
            );
        """)
        logger.info("✓ chunk table created")
        
        # Create entity table
        logger.info("Creating entity table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS entity (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("✓ entity table created")
        
        # Create chunk_entity junction table
        logger.info("Creating chunk_entity junction table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chunk_entity (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                chunk_id UUID NOT NULL REFERENCES chunk(id) ON DELETE CASCADE,
                entity_id UUID NOT NULL REFERENCES entity(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chunk_id, entity_id)
            );
        """)
        logger.info("✓ chunk_entity junction table created")
        
        # Create indexes
        logger.info("Creating indexes...")
        
        # Index on document sha256 for duplicate detection
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_sha256 
            ON document(sha256);
        """)
        
        # Index on chunk document_id for fast lookups
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunk_document_id 
            ON chunk(document_id);
        """)
        
        # Vector similarity index (IVFFlat)
        logger.info("Creating vector index (this may take a while)...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunk_embedding 
            ON chunk USING ivfflat (embedding vector_l2_ops) 
            WITH (lists = 100);
        """)
        
        # Index on entity name for deduplication
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_entity_name 
            ON entity(name);
        """)
        
        # Index on entity type for filtering
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_entity_type 
            ON entity(type);
        """)
        
        # Indexes on chunk_entity for efficient joins
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunk_entity_chunk_id 
            ON chunk_entity(chunk_id);
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunk_entity_entity_id 
            ON chunk_entity(entity_id);
        """)
        
        logger.info("✓ All indexes created successfully")
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info("=" * 50)
        logger.info("✓ Database initialization completed successfully!")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Error initializing schema: {e}")
        raise


def verify_setup():
    """Verify that all tables and indexes were created correctly."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        # Check tables
        cur.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('document', 'chunk', 'entity', 'chunk_entity')
            ORDER BY tablename;
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        logger.info("\nVerifying setup:")
        logger.info(f"  Tables created: {', '.join(tables)}")
        
        # Check pgvector extension
        cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
        if cur.fetchone():
            logger.info("  ✓ pgvector extension installed")
        else:
            logger.warning("  ✗ pgvector extension NOT found")
        
        # Check indexes
        cur.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename IN ('document', 'chunk', 'entity', 'chunk_entity')
            ORDER BY indexname;
        """)
        indexes = [row[0] for row in cur.fetchall()]
        logger.info(f"  Indexes created: {len(indexes)}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error verifying setup: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("ATLAS Database Initialization")
    print("=" * 50)
    print()
    
    try:
        create_database()
        init_schema()
        verify_setup()
        
        print()
        print("=" * 50)
        print("✓ Setup complete! You can now:")
        print("  1. Run bulk ingestion: python backend/ingestion/bulk_insert_parquet.py")
        print("  2. Start the API: uvicorn backend.fastapi.main:app --reload")
        print("=" * 50)
        
    except Exception as e:
        print()
        print("=" * 50)
        print(f"✗ Setup failed: {e}")
        print("=" * 50)
        exit(1)
