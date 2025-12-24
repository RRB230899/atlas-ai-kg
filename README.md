# 🌐 ATLAS — Graph-Aware RAG System

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.x-008CC1.svg)](https://neo4j.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**ATLAS (AI-Driven Text & Link Analysis System)** is a production-grade **graph-aware Retrieval-Augmented Generation (RAG)** platform that combines **semantic vector search** (PostgreSQL + pgvector) with **knowledge graph reasoning** (Neo4j) to deliver **grounded, explainable answers** from 10,000+ research papers.

Built for researchers, analysts, and knowledge workers who need to make sense of massive document collections across **AI/ML, Finance, Blockchain, Transportation, Healthcare, and Sports**.

📖 **[Documentation](./docs/SETUP.md)** |

---

## ✨ Key Features

### 🎯 **Intelligent Retrieval**
- **Semantic Search**: Natural language queries using `sentence-transformers/all-MiniLM-L6-v2` (384-dim embeddings)
- **Hybrid Retrieval**: Combines vector similarity, BM25 lexical search, and ColBERT late interaction
- **Sub-150ms Latency**: Optimized IVFFlat indexing on 200K+ chunks

### 🕸️ **Knowledge Graph Integration**
- **Entity Extraction**: Automatic NER using spaCy `en_core_web_lg` (50K+ unique entities)
- **Relationship Mapping**: Multi-hop reasoning across documents and entities
- **Interactive Visualization**: Cytoscape.js graphs with color-coded entity types

### 📊 **Explainable AI**
- **Citation Tracking**: Every answer includes `[DOC_ID:CHUNK_ID]` references
- **Visual Provenance**: See how entities connect across your corpus
- **Transparent Results**: No black-box retrieval

### 🚀 **Production-Ready**
- **Scalable Architecture**: Processes 10,000+ documents efficiently
- **Cloud-Native**: Neo4j Aura integration, PostgreSQL local/cloud
- **Docker Support**: One-command deployment with Docker Compose
- **Robust Pipeline**: Duplicate detection, error handling, batch processing

---

## 📈 System Stats

| Metric | Value |
|--------|-------|
| **Documents Processed** | 10,000+ research papers |
| **Text Chunks** | ~200,000 (300 tokens each, 50 overlap) |
| **Unique Entities** | ~50,000 (7+ types) |
| **Query Latency** | <150ms (vector search) |
| **Domains Covered** | AI/ML, Finance, Blockchain, Transportation, Healthcare, Sports |

---

## 🏗️ Architecture
```
┌─────────────────────────────────────────────────────────┐
│              ATLAS System Architecture                   │
└─────────────────────────────────────────────────────────┘
                            │
         ┌──────────────────┴──────────────────┐
         ▼                                     ▼
[Google Colab GPU]                [Samsung T7 SSD Storage]
 - Embedding generation            • 10,000+ PDFs
 - Batch: 64 chunks                • ~1000 MB/s I/O
 - all-MiniLM-L6-v2                • Parquet exports
         │                                     │
         └──────────────────┬──────────────────┘
                            ▼
                  [FastAPI Backend]
                  • /ingest
                  • /search_rag_plus_graph
                  • /search_with_entities
                            │
      ┌─────────────────────┼─────────────────────┐
      ▼                     ▼                     ▼
[PostgreSQL 16]      [Neo4j Cloud]        [React Frontend]
+ pgvector            Aura Instance         + Vite + Yarn
                                            + Cytoscape.js
- 200K chunks        • 50K entities         • Chat interface
- Vector index       • Relationships        • Graph viewer
- <150ms queries     • Visual graphs        • History sidebar
```

---

## 🧩 Tech Stack

### Backend
- **Framework**: FastAPI 0.104+
- **Language**: Python 3.11
- **Embeddings**: SentenceTransformers (`all-MiniLM-L6-v2`)
- **NER**: spaCy (`en_core_web_lg`)
- **Text Extraction**: PyMuPDF (fitz)
- **Search**: ColBERT, BM25, Vector similarity

### Databases
- **PostgreSQL 16** + **pgvector**: Semantic embeddings, vector search (IVFFlat indexing)
- **Neo4j 5.x** (Cloud/Aura): Entity graphs, relationship traversal

### Frontend
- **React 18** + **Vite**: Modern build tooling
- **Yarn**: Package management
- **Cytoscape.js**: Interactive graph visualization
- **Tailwind CSS**: Styling

### Infrastructure
- **Docker Compose**: Multi-container orchestration
- **Google Colab**: GPU-accelerated embedding generation
- **Samsung T7 SSD**: High-speed local PDF storage

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or 3.11
- PostgreSQL 16+ with pgvector extension
- Neo4j Cloud account (free tier available)
- Node.js 18+ and Yarn
- Docker & Docker Compose (optional)

### 1. Clone Repository
```bash
git clone https://github.com/RRB230899/atlas-ai-kg.git
cd atlas-ai-kg
```

### 2. Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Required environment variables:
```bash
# PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=atlas
DB_USER=atlas_user
DB_PASSWORD=your_password

# Neo4j Cloud (Aura)
NEO_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO_USER=neo4j
NEO_PASSWORD=your_neo4j_password
```

### 3. Install Dependencies
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Python packages
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_lg
```

### 4. Initialize Database
```bash
python init_db.py
```

### 5. Start Services

**Option A: Manual (Development)**
```bash
# Start backend
uvicorn backend.fastapi.main:app --reload --port 8000

# Start frontend (new terminal)
cd frontend
yarn install
yarn dev
```

**Option B: Docker (Production)**
```bash
docker-compose up -d
```

### 6. Access Application

- **Frontend**: http://localhost:5173
- **API Docs**: http://localhost:8000/docs
- **Neo4j Browser**: Your Aura console link

---

## 📊 Data Ingestion

ATLAS uses a two-stage pipeline optimized for scale:

### Stage 1: Generate Embeddings (Google Colab)
```python
# In Google Colab with GPU enabled
# Open: backend/ingestion/colab_bulk_ingestion.py

# Configure
PDF_DIR = "/content/drive/MyDrive/atlas_pdfs"
CHUNK_SIZE = 300  # tokens
OVERLAP = 50      # tokens
BATCH_SIZE = 64   # embeddings per batch

# Run
# Downloads embeddings.parquet
```

### Stage 2: Bulk Ingestion (Local)
```bash
# Ingest into PostgreSQL
python backend/ingestion/bulk_insert_parquet.py \
  --parquet_path embeddings.parquet

# Build Neo4j knowledge graph
python backend/ingestion/ingest_parquet_with_graph.py \
  --parquet_path embeddings.parquet
```

**Single File Ingestion** (for new documents):
```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "file=@paper.pdf"
```

---

## 🔍 API Usage

### Search with Graph (Primary Endpoint)
```bash
curl -X POST "http://localhost:8000/search_rag_plus_graph" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "transformer attention mechanisms",
    "top_k": 5,
    "with_graph": true
  }'
```

**Response:**
```json
{
  "hits": [
    {
      "text": "Attention mechanisms allow models to...",
      "score": 0.89,
      "chunk_id": "abc123",
      "document_id": "doc456",
      "sha256": "...",
      "title": "Attention Is All You Need"
    }
  ],
  "graph": {
    "nodes": [
      {"id": "doc456", "label": "Paper", "type": "doc"},
      {"id": "Attention", "label": "Attention", "type": "entity"}
    ],
    "edges": [
      {"source": "doc456", "target": "Attention", "label": "MENTIONS"}
    ]
  }
}
```

### Other Endpoints
```bash
# Basic semantic search
GET /search?q=neural+networks&k=10

# Search with entities
GET /search_with_entities?q=blockchain&k=5

# Document-level search
GET /search_docs?q=quantum+computing&top_k_docs=5
```

See full API documentation at `/docs` when running the server.

---

## 📂 Project Structure
```
atlas-ai-kg/
├── backend/
│   ├── fastapi/
│   │   ├── main.py              # FastAPI app & endpoints
│   │   └── utils.py             # DB connections, utilities
│   ├── ingestion/
│   │   ├── colab_bulk_ingestion.py      # Colab embedding script
│   │   ├── bulk_insert_parquet.py       # Postgres ingestion
│   │   ├── ingest_parquet_with_graph.py # Neo4j ingestion
│   │   └── ingest_with_graph.py         # Single file ingestion
│   ├── search/
│   │   ├── colbert_search.py            # ColBERT retrieval
│   │   ├── bm25_search.py               # Lexical search
│   │   └── colbert_indexing.py          # Index creation
│   └── indexes/                         # ColBERT index files
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatWindow.jsx           # Main chat UI
│   │   │   ├── GraphView.jsx            # Cytoscape visualization
│   │   │   ├── MessageBubble.jsx        # Result display
│   │   │   └── SideBar.jsx              # Chat history
│   │   └── App.jsx
│   └── package.json
├── docs/
│   ├── init_db.py               # Database initialization script
│   ├── SETUP.md                 # Detailed setup guide
│   └── screenshots/             
├── docker-compose.yml           # Container orchestration
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template
└── README.md
```

---

## 🗄️ Database Schema

### PostgreSQL
```sql
-- Documents table
CREATE TABLE document (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    mime_type TEXT DEFAULT 'application/pdf',
    sha256 TEXT UNIQUE NOT NULL,
    source_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chunks table with vector embeddings
CREATE TABLE chunk (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES document(id) ON DELETE CASCADE,
    ord INT NOT NULL,
    text TEXT NOT NULL,
    token_count INT NOT NULL,
    embedding VECTOR(384),  -- all-MiniLM-L6-v2
    UNIQUE(document_id, ord)
);

-- Vector similarity index (IVFFlat)
CREATE INDEX idx_chunk_embedding 
ON chunk USING ivfflat (embedding vector_l2_ops) 
WITH (lists = 100);

-- Entities table
CREATE TABLE entity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,  -- PERSON, ORG, GPE, TECH, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many: chunks ↔ entities
CREATE TABLE chunk_entity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID REFERENCES chunk(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES entity(id) ON DELETE CASCADE,
    UNIQUE(chunk_id, entity_id)
);
```

### Neo4j
```cypher
-- Node labels
(:Document)  // Document metadata
(:Chunk)     // Chunk content
(:Entity)    // Extracted entities (PERSON, ORG, TECH, etc.)

-- Relationships
(Document)-[:CONTAINS]->(Chunk)
(Chunk)-[:MENTIONS]->(Entity)
(Entity)-[:RELATED_TO]->(Entity)
(Entity)-[:CO_OCCURS_IN]->(Chunk)

-- Constraints
CREATE CONSTRAINT entity_name_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.name IS UNIQUE;

CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS
FOR (c:Chunk) REQUIRE c.id IS UNIQUE;
```

---

## 🎨 Frontend Features

### Chat Interface
- Natural language query input
- Streaming responses (if enabled)
- Citation links to source documents
- Chat history sidebar

### Knowledge Graph Visualization
- **Color-coded entities**:
  - 🔵 Documents (blue)
  - ⚪ Chunks (gray)
  - 🟢 Persons (green)
  - 🟠 Organizations (orange)
  - 🟣 Technologies (purple)
  - 🔴 Locations (red)
  - 🟡 Concepts (yellow)

- **Interactive legend** with node type descriptions
- **Double-click actions**:
  - Documents → Open PDF
  - Chunks → Show preview

---

## ⚙️ Configuration

### Chunking Strategy

Edit in `backend/ingestion/colab_bulk_ingestion.py`:
```python
CHUNK_SIZE = 300        # Tokens per chunk
CHUNK_OVERLAP = 50      # Overlapping tokens
BATCH_SIZE = 64         # Embedding batch size
```

### Vector Index Tuning

Adjust for corpus size in `init_db.py`:
```sql
-- 100K-500K chunks → lists = 100
-- 500K-1M chunks   → lists = 200
-- 1M+ chunks       → lists = 500

CREATE INDEX idx_chunk_embedding 
ON chunk USING ivfflat (embedding vector_l2_ops) 
WITH (lists = 100);
```

---

## 🧪 Testing

### Verify Connections
```bash
# PostgreSQL
python -c "from backend.fastapi.utils import get_conn; \
conn = get_conn(); print('✓ PostgreSQL connected'); conn.close()"

# Neo4j Cloud
python -c "
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
load_dotenv()
driver = GraphDatabase.driver(
    os.getenv('NEO_URI'), 
    auth=(os.getenv('NEO_USER'), os.getenv('NEO_PASSWORD'))
)
with driver.session() as session:
    session.run('RETURN 1')
print('✓ Neo4j Cloud connected')
driver.close()
"
```

### Test API
```bash
# Health check
curl http://localhost:8000/

# Search test
curl "http://localhost:8000/search?q=machine+learning&k=3"
```

---

## 📚 Documentation

- **[Setup Guide](./docs/SETUP.md)**: Detailed installation and configuration
- **[API Documentation](http://localhost:8000/docs)**: Interactive Swagger UI (when running)
- **[Docker Guide](./docs/docker-compose.yml)**: Container deployment

---

## 📊 Performance

| Operation | Latency | Throughput |
|-----------|---------|------------|
| Vector Search (k=10) | <150ms | ~7 queries/sec |
| Entity Extraction | ~2s/document | Batch processing |
| Graph Query | 50-200ms | Depends on depth |
| End-to-End Ingestion | ~3s/document | GPU accelerated |

**Optimizations:**
- IVFFlat indexing for approximate nearest neighbor search
- Batch processing for embeddings (64 at a time)
- Connection pooling for database access
- Cypher query optimization with indexes

---

## 🛣️ Roadmap

- [ ] LLM-powered answer generation (OpenAI, Anthropic)
- [ ] Multi-language support (extend beyond English)
- [ ] Advanced graph algorithms (community detection, centrality)
- [ ] Fine-tuned embedding models for domain specificity
- [ ] Distributed deployment (Kubernetes)
- [ ] Real-time document updates
- [ ] User authentication and multi-tenancy

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **SentenceTransformers** for embedding models
- **spaCy** for NER capabilities
- **Neo4j** for graph database technology
- **PostgreSQL** and **pgvector** for vector search
- **FastAPI** for modern Python APIs
- **React** and **Cytoscape.js** for frontend visualization

---

## 📧 Contact

**Raghav Bajaj**
- GitHub: [@RRB230899](https://github.com/RRB230899)
- Project Link: [https://github.com/RRB230899/atlas-ai-kg](https://github.com/RRB230899/atlas-ai-kg)

---

## 📸 Screenshots

### Chat Interface with Graph Visualization
![Chat Interface](docs/screenshots/Chat%20Interface.png)

### Knowledge Graph Explorer
![Knowledge Graph](docs/screenshots/Knowledge%20Graph.png)

### API Documentation (Swagger)
![API Docs](docs/screenshots/API%20Docs.png)

---

<div align="center">

**Built with ❤️ for the research community**

⭐ **Star this repo** if you find it useful!

</div>
