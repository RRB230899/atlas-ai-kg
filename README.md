# 🧠 ATLAS — Graph-Aware RAG System

**ATLAS (AI-Driven Text & Link Analysis System)** is a **graph-aware Retrieval-Augmented Generation (RAG)** platform that fuses **PostgreSQL (pgvector)** with **Neo4j** to deliver **grounded, explainable answers** and **interactive knowledge graphs** from unstructured PDFs.

ATLAS demonstrates **semantic retrieval**, **entity-level reasoning**, and **graph visualization**, forming the same foundation used in enterprise knowledge systems and research intelligence engines.

---

## 🚀 Features

- ✅ **End-to-End Ingestion Pipeline**  
  PDF → Text → Chunks → Embeddings → NER → Graph Construction  

- ✅ **Hybrid Storage Design**  
  - **Postgres + pgvector** → Semantic embeddings & similarity search  
  - **Neo4j** → Entities, relationships, and visual knowledge graphs  

- ✅ **Search APIs**  
  - `/search` — Semantic vector search  
  - `/search_with_entities` — Hybrid retrieval with entity reasoning  

- ✅ **Interactive Graph Visualization**  
  - Explore entity relationships and co-occurrence graphs in Neo4j Browser or Cytoscape.js frontend  

- ✅ **Explainable Retrieval**  
  - Each answer chunk is citation-linked with `[DOC_ID:CHUNK_ID]`  

---

## 🧩 Tech Stack

| Layer | Tools / Libraries | Purpose |
|-------|-------------------|----------|
| **Backend** | FastAPI, Python, psycopg2, SentenceTransformers | Ingestion, Embedding, API |
| **Databases** | PostgreSQL + pgvector, Neo4j | Semantic & relational storage |
| **NLP** | spaCy (`en_core_web_lg`) | Named Entity Recognition |
| **Orchestration** | dotenv, logging, tenacity | Configs, retries, structured logs |
| **Frontend (planned)** | React + Tailwind + Cytoscape.js | Interactive graph visualization |

---

## 🏗️ System Architecture

```text
[User UI: React + Tailwind]
        |
        v
[FastAPI Backend]
        |
        +--> [Postgres + pgvector]   ←→  (Chunks, Embeddings, Metadata)
        |
        +--> [Neo4j Graph DB]        ←→  (Entities, Mentions, Relations)
        |
        +--> [MinIO (Raw PDFs)]      ←→  (File Storage)
```

## ⚙️ Setup Instructions
### 1️⃣ Clone the repository
git clone https://github.com/RRB230899/atlas-ai-kg.git
cd atlas-ai-kg

## 2️⃣ Create and activate virtual environment
python3 -m venv atlas
source atlas/bin/activate

## 3️⃣ Install dependencies
pip install -r requirements.txt

## 4️⃣ Configure environment variables

Create a .env file in the project root:

POSTGRES_DBNAME=your_dbname
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
NEO_URI=bolt://localhost:7687
NEO_USER=your_username
NEO_PASSWORD=your_password

## 5️⃣ Run FastAPI
cd backend/fastapi
uvicorn main:app --reload


Open API docs at → http://localhost:8000/docs

## 🧠 Database Setup
### PostgreSQL Schema
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT,
    mime_type TEXT,
    sha256 TEXT UNIQUE
);

CREATE TABLE chunk (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES document(id) ON DELETE CASCADE,
    ord INT,
    text TEXT,
    token_count INT,
    embedding VECTOR(384)
);

CREATE UNIQUE INDEX unique_chunk_per_doc ON chunk (document_id, ord);
CREATE INDEX idx_chunk_document_id ON chunk (document_id);
CREATE INDEX idx_chunk_embedding ON chunk USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

### Neo4j Constraints
CREATE CONSTRAINT entity_name_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.name IS UNIQUE;

CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS
FOR (c:Chunk) REQUIRE c.id IS UNIQUE;

## 🔍 Example Queries
### Semantic Search (pgvector)
SELECT id, text
FROM chunk
ORDER BY embedding <-> query_embedding
LIMIT 5;

### Graph Query (Neo4j)
MATCH (e:Entity)<-[:MENTIONS]-(c:Chunk)-[:MENTIONS]->(related:Entity)
RETURN e, c, related
LIMIT 50;

### Entity-Focused Subgraph
MATCH (e:Entity {name: "Quantum Computing"})<-[:MENTIONS]-(c:Chunk)
RETURN e, c
LIMIT 25;

## 💡 Example API Response
{
  "query": "quantum computing",
  "results": [
    {
      "chunk_id": "f4bbfea5-4218-4cdf-af9b-01965fff5442",
      "document_id": "4b1cb27c-8cdb-4b4f-9917-c4024ef4c7b3",
      "text": "Quantum computing leverages superposition and entanglement...",
      "entities": [
        {"name": "Quantum Computing", "label": "TECH"},
        {"name": "Superposition", "label": "PHYSICS"}
      ]
    }
  ]
}
