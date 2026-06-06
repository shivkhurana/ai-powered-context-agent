# Performance Optimization Guide

Detailed performance tuning and optimization strategies for the AI Data Retrieval Agent.

## 🎯 Performance Targets

| Metric | Target | P95 | P99 |
|--------|--------|-----|-----|
| Response Time | < 800ms | < 790ms | < 800ms |
| Accuracy | 95%+ | N/A | N/A |
| Cache Hit Rate | 40%+ | N/A | N/A |
| Throughput | 100+ QPS | N/A | N/A |
| CPU Usage | < 80% | N/A | N/A |
| Memory Usage | < 2GB | N/A | N/A |

## ⏱️ Latency Breakdown

### Typical Query Execution Timeline
```
Total Time Budget: 800ms

1. Cache Lookup              5-10ms    (0.6-1.2%)
2. Embedding Generation     20-50ms    (2.5-6.2%)
3. Document Retrieval      30-100ms    (3.7-12.5%)
4. LLM API Call           400-600ms    (50-75%)
5. Response Parsing         5-20ms    (0.6-2.5%)
6. Overhead/Network        10-20ms    (1.2-2.5%)
───────────────────────────────────
   TOTAL               470-800ms     (100%)
```

### Component Breakdown

#### Cache Lookup (5-10ms)
- **MD5 key hashing**: ~1ms
- **Disk/Redis lookup**: ~3-7ms
- **JSON deserialization**: ~1-2ms

**Optimization:**
```env
# Use Redis for < 2ms lookups (vs 5-7ms for disk)
CACHE_TYPE=redis
CACHE_TTL=7200  # Increase cache duration

# For frequently accessed queries, cache hit rate can reduce total time to < 50ms
```

#### Embedding Generation (20-50ms)
- **Model loading**: Amortized to ~0
- **Text encoding**: ~15-40ms
- **Normalization**: ~2-5ms

**Optimization:**
```env
# Use GPU acceleration if available
EMBEDDING_DEVICE=cuda  # or cpu

# Batch embeddings if processing multiple queries
# Use sentence-transformers batch inference
```

#### Document Retrieval (30-100ms)
- **Vector similarity computation**: ~20-60ms
- **Index search**: ~5-20ms
- **Result formatting**: ~5-20ms

**Optimization:**
```env
# Reduce number of documents to search
# Keep 5-10 documents maximum
DOCUMENT_LIMIT=10

# Increase similarity threshold to reduce candidates
SIMILARITY_THRESHOLD=0.6  # Default 0.5

# Use smaller chunk size for faster search
CHUNK_SIZE=300  # Default 500

# Reduce context window
CONTEXT_WINDOW_SIZE=2  # Default 3
```

#### LLM API Call (400-600ms)
- **Network latency**: ~50-150ms
- **LLM processing**: ~200-400ms
- **Token generation**: ~50-100ms

**Optimization:**
```env
# Use faster model
OPENAI_MODEL=gpt-4-turbo-preview  # Faster than gpt-4

# Or use Gemini which may be faster
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-pro

# Reduce token context for faster processing
MAX_CONTEXT_LENGTH=1500  # Default 2000

# Use connection pooling
CONNECTION_POOL_SIZE=50  # Default 20

# Set appropriate timeout
LLM_TIMEOUT=20.0  # Default 25
```

#### Response Parsing (5-20ms)
- **JSON parsing**: ~2-5ms
- **Confidence calculation**: ~1-3ms
- **Result formatting**: ~2-10ms

**Optimization:**
```python
# Minimize response formatting
# Use streaming responses for large results (future feature)
```

## 📊 Performance Monitoring

### Real-time Monitoring

```bash
# Get current latency statistics
curl http://localhost:8000/api/v1/stats | jq '.latency_statistics'

# Expected output:
{
  "total_queries": 1250,
  "average_latency_ms": 678.45,
  "min_latency_ms": 456.23,
  "max_latency_ms": 798.90,
  "sla_compliance": 98.5,
  "p50_ms": 678.45,
  "p95_ms": 765.34,
  "p99_ms": 798.90
}
```

### Detailed Latency Metrics

```bash
# Get per-query latency breakdown
curl "http://localhost:8000/api/v1/latency-metrics?limit=100" | jq '.[] | {
  query: .query[0:30],
  total: .total_execution_ms,
  cache: .cache_lookup_time_ms,
  embedding: .embedding_time_ms,
  retrieval: .retrieval_time_ms,
  llm: .llm_call_time_ms
}'
```

### Export Profiling Data

```bash
# Export to JSON for analysis
curl -X POST http://localhost:8000/api/v1/profile/export

# Analyze with external tools
python analyze_latency.py profiles/latency_test_results.json
```

## 🔍 Identifying Bottlenecks

### Query is slow (> 800ms)?

1. **Check LLM time**
   ```bash
   curl "http://localhost:8000/api/v1/latency-metrics?limit=1" | jq '.[0].llm_call_time_ms'
   ```
   - If > 500ms: LLM provider is slow
     - Switch provider: `LLM_PROVIDER=gemini`
     - Use faster model: `gpt-3.5-turbo` instead of `gpt-4`

2. **Check RAG retrieval time**
   ```bash
   curl "http://localhost:8000/api/v1/latency-metrics?limit=1" | jq '.[0].retrieval_time_ms'
   ```
   - If > 100ms: Too many documents or chunks
     - Reduce `DOCUMENT_LIMIT`
     - Increase `SIMILARITY_THRESHOLD`
     - Reduce `CHUNK_SIZE`

3. **Check cache hit rate**
   ```bash
   curl "http://localhost:8000/api/v1/stats" | jq '.rag_statistics'
   ```
   - If low: Similar queries not cached
     - Increase `CACHE_TTL`
     - Implement query normalization (future)

4. **Check system resources**
   ```bash
   # Monitor CPU and memory
   top -p $(pgrep -f "uvicorn")
   
   # Check disk I/O (if using disk cache)
   iostat -x 1
   ```

## 🚀 Optimization Strategies

### Strategy 1: Aggressive Caching

```env
# Increase cache TTL
CACHE_TTL=86400  # 24 hours

# Use Redis (faster)
CACHE_TYPE=redis
REDIS_URL=redis://localhost:6379/0

# Implement query normalization
NORMALIZE_QUERIES=True
```

**Expected improvement:** 30-40% of queries cached, reducing response time to < 50ms

### Strategy 2: Minimal RAG Context

```env
# Reduce context complexity
CHUNK_SIZE=300  # Smaller chunks
CHUNK_OVERLAP=25  # Less overlap
CONTEXT_WINDOW_SIZE=2  # Only top 2 chunks
MAX_CONTEXT_LENGTH=1000  # Shorter context

# Higher similarity threshold
SIMILARITY_THRESHOLD=0.7  # Only most relevant
```

**Expected improvement:** 50-70ms faster retrieval, 10-20% better accuracy

### Strategy 3: Faster LLM Provider

```env
# Option A: Gemini (often faster for simple queries)
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-pro

# Option B: Faster OpenAI model
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-3.5-turbo  # Much faster, good accuracy

# Option C: Local LLM (requires setup)
LLM_PROVIDER=local
LOCAL_MODEL_PATH=/path/to/model
```

**Expected improvement:** 100-200ms reduction in LLM time

### Strategy 4: Connection Pooling & Concurrency

```env
# Increase connection pool
CONNECTION_POOL_SIZE=100

# Use multiple Uvicorn workers
WORKERS=8  # For 4-core CPU: 2*cores

# Enable connection reuse
KEEP_ALIVE=60  # seconds
```

**Expected improvement:** 5-15% improvement in throughput

### Strategy 5: Batch Processing

Use batch endpoint for multiple queries:

```bash
curl -X POST "http://localhost:8000/api/v1/batch-query" \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [
      {"query": "Query 1"},
      {"query": "Query 2"},
      {"query": "Query 3"}
    ]
  }'
```

**Expected improvement:** 3x faster per-query processing for batches

## 📈 Load Testing

### Using Apache Bench

```bash
# Single endpoint test
ab -n 100 -c 10 -p query.json -T application/json \
  http://localhost:8000/api/v1/query

# Parse results
# - Time per request: Target < 800ms
# - Requests per second: Target > 100
```

### Using Locust

Create `locustfile.py`:

```python
from locust import HttpUser, task, between

class QueryUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def query(self):
        self.client.post(
            "/api/v1/query",
            json={
                "query": "What is machine learning?",
                "use_rag": True
            }
        )

if __name__ == "__main__":
    from locust.main import main
    import sys
    sys.argv += ["-H", "http://localhost:8000"]
    main()
```

Run:
```bash
locust -f locustfile.py --users 100 --spawn-rate 10 --run-time 5m
```

## 🔧 Advanced Tuning

### Database Query Optimization

```python
# Use async operations exclusively
# Avoid blocking I/O

# Optimize embedding model
# all-MiniLM-L6-v2 is already optimal (384 dims, fast)

# Consider distilled models for even faster inference
# sentence-transformers/msmarco-distilbert-base-v4 (66 dims)
```

### Memory Optimization

```env
# Reduce embedding model precision
EMBEDDING_PRECISION=fp16  # Instead of fp32

# Limit document cache size
CACHE_MAX_DOCUMENTS=10

# Reduce profiling history
PROFILING_MAX_HISTORY=1000  # Default 10000
```

### Network Optimization

```bash
# Enable HTTP/2
# Use compression
# Minimize payload size
```

## 📊 Performance Testing Script

```python
# benchmark.py
import asyncio
import httpx
import time
import statistics

async def benchmark():
    queries = [
        "What is machine learning?",
        "Explain deep learning",
        "How do transformers work?"
    ]
    
    times = []
    
    async with httpx.AsyncClient() as client:
        for _ in range(100):
            for query in queries:
                start = time.time()
                
                response = await client.post(
                    "http://localhost:8000/api/v1/query",
                    json={"query": query, "use_rag": True},
                    timeout=10
                )
                
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
    
    print(f"Latency Statistics:")
    print(f"  Mean: {statistics.mean(times):.2f}ms")
    print(f"  Median: {statistics.median(times):.2f}ms")
    print(f"  P95: {sorted(times)[int(len(times)*0.95)]:.2f}ms")
    print(f"  P99: {sorted(times)[int(len(times)*0.99)]:.2f}ms")
    print(f"  SLA Compliance: {sum(1 for t in times if t < 800) / len(times) * 100:.1f}%")

if __name__ == "__main__":
    asyncio.run(benchmark())
```

## ✅ Performance Checklist

- [ ] P95 latency < 790ms
- [ ] P99 latency < 800ms
- [ ] Cache hit rate > 40%
- [ ] Accuracy score > 0.95
- [ ] CPU usage < 80%
- [ ] Memory usage < 2GB
- [ ] Throughput > 100 QPS
- [ ] All latency metrics exported
- [ ] Load testing completed
- [ ] Documentation updated

---

**Performance is a feature. Monitor, measure, optimize.**
