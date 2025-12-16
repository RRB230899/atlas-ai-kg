# ATLAS Setup Guide

Complete guide to setting up and running the ATLAS Graph-Aware RAG system locally with Neo4j Cloud.

## 📋 Prerequisites

### System Requirements
- **OS**: Linux, macOS, or Windows with WSL2
- **RAM**: 16GB+ recommended (for embedding generation and vector search)
- **Storage**: 50GB+ free space (for PDFs, embeddings, and databases)
- **GPU**: Optional but highly recommended for embedding generation on Colab

### Software Dependencies
- **Python**: 3.10 or 3.11
- **PostgreSQL**: 16+ with pgvector extension
- **Neo4j**: Cloud instance (Neo4j Aura)
- **Node.js**: 18+ (for frontend)
- **Yarn**: 1.22+

---

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/RRB230899/atlas-ai-kg.git
cd atlas-ai-kg
```

### 2. Set Up Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Install and Configure Databases

#### PostgreSQL with pgvector

**On Ubuntu/Debian:**
```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Install pgvector
sudo apt install postgresql-16-pgvector

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**On macOS (using Homebrew):**
```bash
brew install postgresql@16
brew install pgvector
brew services start postgresql@16
```

**Create Database User:**
```bash
sudo -u postgres psql
```
```sql
CREATE USER atlas_user WITH PASSWORD 'your_password';
CREATE DATABASE atlas OWNER atlas_user;
GRANT ALL PRIVILEGES ON DATABASE atlas TO atlas_user;
\q
```

#### Neo4j Cloud (Aura)

**Create Cloud Instance:**

1. **Sign up for Neo4j Aura:**
   - Go to https://neo4j.com/cloud/aura/
   - Create a free account or sign in
   - Click "Create Instance"

2. **Configure Instance:**
   - **Instance Type**: Free tier or Professional (based on your needs)
   - **Region**: Choose closest to your location
   - **Instance Name**: `atlas-knowledge-graph`
   - **Database Version**: 5.x (latest)

3. **Save Credentials:**
   - **IMPORTANT**: Download and save the credentials immediately
   - You'll receive:
     - Connection URI (e.g., `neo4j+s://xxxxx.databases.neo4j.io`)
     - Username (usually `neo4j`)
     - Generated password
   - ⚠️ **You cannot retrieve the password later!**

4. **Wait for Instance:**
   - Instance creation takes 1-2 minutes
   - Status will change from "Creating" to "Running"

5. **Whitelist Your IP (Optional):**
   - In Aura console, go to "Connection" tab
   - Add your IP address to allowed connections
   - Or select "Allow from anywhere" for development (⚠️ not recommended for production)

6. **Test Connection:**
   - Click "Open with Neo4j Browser" in Aura console
   - Enter your credentials
   - Run test query: `RETURN 1`

### 4. Configure Environment Variables

Create a `.env` file in the project root:
```bash
# PostgreSQL Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=atlas
DB_USER=atlas_user
DB_PASSWORD=your_secure_password

# Neo4j Cloud Configuration (Aura)
NEO_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO_USER=neo4j
NEO_PASSWORD=your_neo4j_cloud_password

# Model Configuration
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
SPACY_MODEL=en_core_web_lg

# API Configuration (optional)
OPENAI_API_KEY=your_openai_key_if_needed
```

**IMPORTANT:** 
- Add `.env` to `.gitignore` to avoid committing credentials
- Use `.env.example` as a template (without real credentials)

### 5. Initialize Database

Run the initialization script to create PostgreSQL tables and indexes:
```bash
python init_db.py
```

Expected output:
```
==================================================
ATLAS Database Initialization
==================================================

✓ Database 'atlas' created successfully
Enabling pgvector extension...
✓ pgvector extension enabled
Creating document table...
✓ document table created
Creating chunk table...
✓ chunk table created
Creating entity table...
✓ entity table created
Creating chunk_entity junction table...
✓ chunk_entity junction table created
Creating indexes...
✓ All indexes created successfully
==================================================
✓ Database initialization completed successfully!
==================================================
```

### 6. Install spaCy Language Model
```bash
python -m spacy download en_core_web_lg
```

---

## 📊 Data Ingestion Workflow

ATLAS uses a two-stage ingestion process optimized for large-scale document processing:

### Stage 1: Generate Embeddings (Google Colab)

**Why Colab?** Free GPU access for fast embedding generation.

1. **Upload PDFs to Google Drive:**
   - Create a folder (e.g., `/My Drive/atlas_pdfs/`)
   - Upload your research PDFs

2. **Run Embedding Generation Script:**
```bash
   # Open colab_bulk_ingestion.py in Google Colab
   # Update the PDF_DIR path to your Drive folder
   # Run all cells
```

3. **Script Workflow:**
   - Extracts text from PDFs using PyMuPDF (fitz)
   - Chunks text (300 tokens, 50 overlap)
   - Generates embeddings using `all-MiniLM-L6-v2`
   - Processes in batches of 64 for efficiency
   - Saves to `embeddings.parquet` file

4. **Download Parquet File:**
   - Download `embeddings.parquet` from Colab
   - Place in project root or a data directory

### Stage 2: Ingest into Databases (Local)

**Option A: Bulk Ingestion (Recommended for large datasets)**
```bash
# Ingest embeddings into PostgreSQL
python backend/ingestion/bulk_insert_parquet.py --parquet_path embeddings.parquet

# Build Neo4j Cloud knowledge graph
python backend/ingestion/ingest_parquet_with_graph.py --parquet_path embeddings.parquet
```

**Expected Process:**
- Reads parquet file with pre-computed embeddings
- Extracts entities using spaCy `en_core_web_lg`
- Inserts documents, chunks, entities into PostgreSQL
- Creates graph relationships in Neo4j Cloud
- ~200K chunks + ~50K entities in ~10-15 minutes

**Note:** Neo4j Cloud ingestion may be slower than local due to network latency. Consider batching writes for optimal performance.

**Option B: Single File Ingestion (For testing or new documents)**
```bash
# Start the API server first
uvicorn backend.fastapi.main:app --reload

# Use the /ingest endpoint
curl -X POST "http://localhost:8000/ingest" \
  -F "file=@path/to/document.pdf"
```

---

## 🖥️ Running the Application

### Backend (FastAPI Server)
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Start FastAPI server
uvicorn backend.fastapi.main:app --reload --port 8000

# Server will be available at:
# - API: http://localhost:8000
# - API Docs (Swagger): http://localhost:8000/docs
```

### Frontend (React + Vite)
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies (first time only)
yarn install

# Start development server
yarn dev

# Frontend will be available at:
# http://localhost:5173
```

---

## 🔧 Docker Setup (Alternative)

If you prefer containerized deployment, use Docker Compose:

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- Neo4j Cloud instance (already created)

### Setup .env File

Create `.env` file with your credentials:
```bash
# PostgreSQL (will run in Docker)
DB_NAME=atlas
DB_USER=atlas_user
DB_PASSWORD=your_secure_password
DB_PORT=5432

# Neo4j Cloud (your existing instance)
NEO_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO_USER=neo4j
NEO_PASSWORD=your_neo4j_cloud_password

# Optional: OpenAI API
OPENAI_API_KEY=your_api_key_here
```

### Run with Docker Compose
```bash
# Build and start services (PostgreSQL + Backend + Frontend)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes (⚠️ destroys PostgreSQL data)
docker-compose down -v
```

**Services exposed:**
- PostgreSQL: `localhost:5432`
- Neo4j: Your cloud instance (accessible via browser link from Aura console)
- FastAPI: `http://localhost:8000`
- FastAPI Docs: `http://localhost:8000/docs`
- React Frontend: `http://localhost:5173`

**Note:** Docker Compose only runs PostgreSQL, Backend, and Frontend. Neo4j runs in the cloud.

---

## 📂 Project Structure
```
atlas-ai-kg/
├── backend/
│   ├── fastapi/
│   │   ├── main.py              # FastAPI application entry
│   │   └── utils.py             # Database connection and utilities
│   ├── ingestion/
│   │   ├── colab_bulk_ingestion.py      # Colab embedding generation
│   │   ├── bulk_insert_parquet.py       # Bulk PostgreSQL ingestion
│   │   ├── ingest_parquet_with_graph.py # Bulk Neo4j ingestion
│   │   ├── ingest_with_graph.py         # Single file ingestion (with graph)
│   │   └── ingest.py                    # Single file ingestion (basic)
│   ├── search/
│   │   ├── colbert_search.py            # ColBERT retrieval
│   │   ├── bm25_search.py               # Lexical search
│   │   └── colbert_indexing.py          # ColBERT index creation
│   └── indexes/
│       ├── plan.json                    # ColBERT index metadata
│       └── [colbert index files]
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatWindow.jsx           # Main chat interface
│   │   │   ├── GraphView.jsx            # Knowledge graph visualization
│   │   │   ├── MessageBubble.jsx        # Chat message display
│   │   │   └── SideBar.jsx              # Chat history sidebar
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── init_db.py                   # Database initialization script
├── requirements.txt             # Python dependencies
├── docker-compose.yml           # Docker orchestration
├── .env                         # Environment variables (create this)
├── .env.example                 # Template for .env (commit this)
├── .gitignore                   # Git ignore rules
└── README.md
```

---

## 🧪 Verification & Testing

### Test PostgreSQL Connection
```bash
python -c "from backend.fastapi.utils import get_conn; conn = get_conn(); print('✓ PostgreSQL connected'); conn.close()"
```

### Test Neo4j Cloud Connection
```bash
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
    result = session.run('RETURN 1')
    print('✓ Neo4j Cloud connected')
driver.close()
"
```

### Test API Endpoints
```bash
# Search endpoint
curl "http://localhost:8000/search?q=machine+learning&k=3"

# RAG + Graph endpoint (most important)
curl -X POST "http://localhost:8000/search_rag_plus_graph" \
  -H "Content-Type: application/json" \
  -d '{"q": "transformer architecture", "top_k": 5, "with_graph": true}'
```

### Test Frontend

1. Open http://localhost:5173
2. Type a query (e.g., "What are attention mechanisms?")
3. Verify search results appear
4. Check knowledge graph visualization renders

---

## ⚙️ Configuration Options

### Chunking Parameters

Edit in `backend/ingestion/colab_bulk_ingestion.py`:
```python
CHUNK_SIZE = 300        # Tokens per chunk
CHUNK_OVERLAP = 50      # Overlapping tokens
BATCH_SIZE = 64         # Embedding batch size
```

### Vector Index Tuning

For different corpus sizes, adjust IVFFlat parameters in `init_db.py`:
```sql
-- For 100K-500K chunks, use lists = 100
-- For 500K-1M chunks, use lists = 200
-- For 1M+ chunks, use lists = 500

CREATE INDEX idx_chunk_embedding 
ON chunk USING ivfflat (embedding vector_l2_ops) 
WITH (lists = 100);
```

### Neo4j Cloud Performance

**For large ingestion operations:**
1. Use batch writes (combine multiple Cypher statements)
2. Consider using `UNWIND` for bulk operations
3. Monitor query performance in Aura console

**Example batch write:**
```python
# Instead of individual writes
for entity in entities:
    session.run("CREATE (e:Entity {name: $name})", name=entity)

# Use batch
session.run("""
    UNWIND $entities AS entity
    CREATE (e:Entity {name: entity.name, type: entity.type})
""", entities=entities)
```

---

## 🐛 Troubleshooting

### Issue: pgvector extension not found
```bash
# Install pgvector
sudo apt install postgresql-16-pgvector

# Verify installation
psql -d atlas -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Issue: Neo4j Cloud connection refused

**Check 1: Verify credentials**
- Make sure URI includes `neo4j+s://` (with the `+s` for SSL)
- Confirm password is correct (check saved credentials file)
- Username is usually `neo4j`

**Check 2: IP Whitelist**
- Log into Neo4j Aura console
- Go to your instance → "Connection" tab
- Check if your IP is whitelisted
- Add current IP or use "Allow from anywhere" for testing

**Check 3: Instance Status**
- Verify instance is "Running" in Aura console
- If paused, resume the instance

**Check 4: Test with Neo4j Browser**
- Click "Open with Neo4j Browser" in Aura
- If browser connection works but Python doesn't, check firewall

### Issue: spaCy model not found
```bash
# Download the model
python -m spacy download en_core_web_lg

# Verify installation
python -c "import spacy; nlp = spacy.load('en_core_web_lg'); print('✓ Model loaded')"
```

### Issue: Port already in use
```bash
# Find process using port 8000
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows

# Kill process and restart
kill -9 <PID>
```

### Issue: Frontend cannot connect to backend
- Check CORS settings in `backend/fastapi/main.py`
- Verify backend is running on port 8000
- Check browser console for errors

### Issue: Slow Neo4j Cloud ingestion
- **Solution 1**: Use batch writes with `UNWIND`
- **Solution 2**: Increase connection timeout
- **Solution 3**: Consider upgrading to larger Aura instance
- **Solution 4**: Ingest during off-peak hours

### Issue: Neo4j Cloud free tier limits
- Free tier: 50K nodes, 175K relationships
- If exceeded, upgrade to Professional tier
- Monitor usage in Aura console

---

## 📈 Performance Optimization

### For Large Datasets (1M+ chunks)

**PostgreSQL:**
1. **Increase shared_buffers:**
```
   # In postgresql.conf
   shared_buffers = 2GB
   effective_cache_size = 8GB
```

2. **Create partial indexes:**
```sql
   CREATE INDEX idx_chunk_recent 
   ON chunk(created_at) 
   WHERE created_at > NOW() - INTERVAL '30 days';
```

3. **Use connection pooling:**
```python
   # In backend/fastapi/utils.py
   from psycopg2.pool import SimpleConnectionPool
   pool = SimpleConnectionPool(minconn=1, maxconn=20, ...)
```

**Neo4j Cloud:**
1. **Batch operations** with `UNWIND`
2. **Create indexes** on frequently queried properties:
```cypher
   CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)
```
3. **Monitor performance** in Aura console
4. **Upgrade instance** if hitting limits

### For Faster Embedding Generation

- Use GPU on Colab (Runtime → Change runtime type → GPU)
- Increase batch size if GPU memory allows (64 → 128)
- Use `fp16` precision for faster inference

---

## 💰 Cost Considerations

### Neo4j Aura Pricing (as of 2024)

**Free Tier:**
- 50,000 nodes
- 175,000 relationships
- Suitable for: Testing, small projects

**Professional Tier:**
- Starts at ~$65/month
- Unlimited nodes/relationships
- Better performance
- Suitable for: Production use, large graphs

**Recommendation:** Start with free tier, upgrade when needed.

---

## 🎯 Next Steps

After setup:
1. ✅ Ingest your document corpus
2. ✅ Test search and graph visualization
3. ✅ Customize frontend styling
4. ✅ Add domain-specific entity types
5. ✅ Fine-tune chunking strategy
6. ✅ Monitor Neo4j Cloud usage
7. ✅ Optimize batch operations for cloud
8. ✅ Deploy to production

---

## 🆘 Getting Help

- **Issues**: https://github.com/RRB230899/atlas-ai-kg/issues
- **Discussions**: https://github.com/RRB230899/atlas-ai-kg/discussions
- **Documentation**: https://github.com/RRB230899/atlas-ai-kg/wiki
- **Neo4j Community**: https://community.neo4j.com/

---

## 📝 License

MIT License - See LICENSE file for details