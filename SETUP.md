# Setup & Installation Guide

Complete instructions for setting up the AI Data Retrieval Agent.

## 📋 Prerequisites

- **Python 3.9+** (3.11+ recommended)
- **pip** or **poetry** for dependency management
- **API Key**: OpenAI or Google Gemini
- **Optional**: Docker & Docker Compose for containerized deployment
- **Optional**: Redis for production caching

## 🔑 API Key Setup

### OpenAI Setup
1. Visit [OpenAI Platform](https://platform.openai.com)
2. Create account and navigate to API keys
3. Create new API key
4. Copy key to `.env` file

```bash
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4-turbo-preview
```

### Google Gemini Setup
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Copy key to `.env` file

```bash
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_MODEL=gemini-pro
LLM_PROVIDER=gemini
```

## 🐍 Local Installation

### 1. Clone Repository
```bash
cd AIDataRetrievalAgent
```

### 2. Create Virtual Environment
```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

### 5. Run Server
```bash
# Development mode (with auto-reload)
python -m uvicorn app.main:app --reload --port 8000

# Production mode
python -m uvicorn app.main:app --workers 4 --port 8000
```

**Expected Output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     ============================================================
INFO:     Starting AI Data Retrieval Agent
INFO:     ============================================================
INFO:     Configuration:
INFO:       - LLM Provider: openai
INFO:       - RAG Enabled: True
INFO:       - Cache Enabled: True
INFO:       - Target Latency: 800ms
INFO:       - Target Accuracy: 95%
INFO:     ✓ LLM service initialized (openai)
INFO:     ✓ Cache service initialized (disk)
INFO:     ✓ RAG system initialized
INFO:     All services started successfully!
INFO:     ============================================================
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 6. Test Installation
```bash
# Health check
curl http://localhost:8000/api/v1/health

# Expected response:
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "services": {
#     "llm": "operational",
#     "cache": "operational",
#     "rag": "ready"
#   }
# }
```

## 🐳 Docker Setup

### Using Docker

```bash
# Build image
docker build -t ai-data-retrieval-agent .

# Run container with environment
docker run \
  -e OPENAI_API_KEY=sk-... \
  -p 8000:8000 \
  ai-data-retrieval-agent

# Access server at http://localhost:8000
```

### Using Docker Compose

```bash
# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LLM_PROVIDER=openai
      - ENABLE_RAG=True
      - ENABLE_CACHE=True
      - CACHE_TYPE=disk
    volumes:
      - ./data:/app/data
      - ./profiles:/app/profiles
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
EOF

# Configure .env for Docker
cat > .env << 'EOF'
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
ENABLE_RAG=True
ENABLE_CACHE=True
CACHE_TYPE=redis
REDIS_URL=redis://redis:6379/0
EOF

# Start services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

## 🔧 Configuration Details

### Performance Settings

```env
# Query timeout - how long to wait for full response (seconds)
QUERY_TIMEOUT=0.8

# LLM timeout - how long to wait for LLM API (seconds)
LLM_TIMEOUT=25.0

# Connection pool size for concurrent requests
CONNECTION_POOL_SIZE=20

# Number of Uvicorn workers
WORKERS=4
```

### RAG Settings

```env
# Enable Retrieval-Augmented Generation
ENABLE_RAG=True

# Document chunk size (characters)
CHUNK_SIZE=500

# Overlap between chunks (characters)
CHUNK_OVERLAP=50

# Maximum number of context chunks to use
CONTEXT_WINDOW_SIZE=3

# Minimum similarity score (0-1)
SIMILARITY_THRESHOLD=0.5

# Maximum context length for LLM (tokens)
MAX_CONTEXT_LENGTH=2000
```

### Cache Settings

```env
# Enable response caching
ENABLE_CACHE=True

# Cache type: "disk" or "redis"
CACHE_TYPE=disk

# Redis URL (if using Redis)
REDIS_URL=redis://localhost:6379/0

# Cache TTL (seconds)
CACHE_TTL=3600

# Maximum cache size (MB, for disk)
CACHE_MAX_SIZE=1000
```

### Logging

```env
# Log level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO

# Enable structured logging
STRUCTURED_LOGGING=True

# Enable latency metric logging
LOG_LATENCY_METRICS=True
```

## 📊 Loading Sample Documents

### Upload Documents via API

```bash
# Create sample document file
cat > sample_doc.txt << 'EOF'
Machine Learning Fundamentals:

Machine learning is a subset of artificial intelligence that enables systems to learn
and improve from experience without being explicitly programmed. It focuses on developing
algorithms and models that can process data and make decisions based on patterns.

Key concepts include:
- Supervised Learning: Training on labeled data
- Unsupervised Learning: Finding patterns in unlabeled data
- Reinforcement Learning: Learning through rewards and penalties
- Deep Learning: Neural networks with multiple layers
EOF

# Upload via API
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Content-Type: application/json" \
  -d '{
    "document_name": "ml_fundamentals.txt",
    "content": "'"$(cat sample_doc.txt)"'"
  }'
```

### Batch Document Loading

Create `load_documents.py`:

```python
import asyncio
import httpx
from pathlib import Path

async def load_documents():
    async with httpx.AsyncClient() as client:
        # Load all .txt files from data directory
        for doc_file in Path("data").glob("*.txt"):
            content = doc_file.read_text()
            
            response = await client.post(
                "http://localhost:8000/api/v1/documents/upload",
                json={
                    "document_name": doc_file.name,
                    "content": content
                }
            )
            
            result = response.json()
            print(f"✓ Loaded {doc_file.name}: {result['chunks_created']} chunks")

if __name__ == "__main__":
    asyncio.run(load_documents())
```

Run it:
```bash
python load_documents.py
```

## 🧪 Running Tests

### Unit Tests
```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_components.py -v

# With coverage report
pytest tests/ --cov=app --cov-report=html
```

### Integration Tests
```bash
# Start server first
python -m uvicorn app.main:app --reload &

# Run integration tests
pytest tests/test_integration.py -v

# Stop server
kill %1
```

### Latency Tests
```bash
# Run latency benchmark
python latency_test.py

# Results saved to profiles/latency_test_results.json
```

## 🚀 Production Deployment

### Before Deployment

- [ ] Set strong API keys in environment variables
- [ ] Enable HTTPS/SSL
- [ ] Configure production Redis instance
- [ ] Set up monitoring and alerting
- [ ] Configure log aggregation
- [ ] Run full test suite
- [ ] Load test with realistic query volume
- [ ] Set up database backups (if using persistent storage)

### Deployment Options

#### Option 1: Cloud Run (Google Cloud)
```bash
# Build and push to Cloud Run
gcloud run deploy ai-data-retrieval-agent \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars "OPENAI_API_KEY=sk-..." \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600
```

#### Option 2: AWS Lambda + API Gateway
```bash
# Requires Mangum ASGI adapter
pip install mangum

# Create handler.py
from mangum import Mangum
from app.main import app

handler = Mangum(app)

# Deploy using AWS CLI or Serverless Framework
```

#### Option 3: Kubernetes
```bash
# Create deployment manifest
kubectl apply -f k8s/deployment.yaml

# Scale pods
kubectl scale deployment ai-agent --replicas=3

# Monitor
kubectl logs -f deployment/ai-agent
```

### Monitoring & Logging

```bash
# View real-time logs
docker-compose logs -f app

# Export profiling data
curl http://localhost:8000/api/v1/profile/export

# Monitor latency
watch -n 5 'curl -s http://localhost:8000/api/v1/stats | jq .'
```

## ❓ Troubleshooting

### Issue: API Key not found
**Solution:** Verify `.env` file exists and has correct format:
```bash
cat .env | grep OPENAI_API_KEY
```

### Issue: "Connection refused" to Redis
**Solution:** If using Redis, ensure it's running:
```bash
# Check if Redis is running
redis-cli ping

# Start Redis (Docker)
docker run -d -p 6379:6379 redis:7-alpine
```

### Issue: Slow response times
**Solution:** Check performance metrics:
```bash
curl http://localhost:8000/api/v1/latency-metrics?limit=10
```

### Issue: Out of memory
**Solution:** Reduce cache size or document count:
```env
CACHE_MAX_SIZE=500  # Reduce from 1000
```

### Issue: LLM API timeouts
**Solution:** Increase timeout or check API status:
```env
LLM_TIMEOUT=40.0  # Increase from 25
```

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Google Gemini API](https://ai.google.dev/docs)

## ✅ Verification Checklist

After setup, verify:
- [ ] Server starts without errors
- [ ] Health endpoint returns 200 OK
- [ ] Can upload documents
- [ ] Can process queries
- [ ] Latency under 800ms
- [ ] Cache is working (check /api/v1/stats)
- [ ] Tests pass
- [ ] Documentation is accessible at /api/v1/docs

---

**Questions?** Check [README.md](README.md) or [PERFORMANCE.md](PERFORMANCE.md)
