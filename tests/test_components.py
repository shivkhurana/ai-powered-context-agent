"""
Comprehensive test suite for AI Data Retrieval Agent
Tests all components including LLM integration, RAG, and latency optimization
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import numpy as np

from app.services.llm_service import OpenAIProvider, GeminiProvider, LLMService
from app.services.rag_system import RAGSystem, EmbeddingService, DocumentChunker
from app.services.cache_service import CacheService, DiskCache
from app.services.query_service import QueryService
from app.models.schemas import QueryRequest
from app.core.profiler import LatencyProfiler


class TestEmbeddingService:
    """Tests for embedding service"""
    
    @pytest_asyncio.fixture
    async def embedding_service(self):
        return EmbeddingService()
    
    @pytest.mark.asyncio
    async def test_embed_text(self, embedding_service):
        """Test single text embedding"""
        text = "This is a test query"
        embedding = await embedding_service.embed_text(text)
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape[0] == embedding_service.dimension
        assert not np.isnan(embedding).any()
    
    @pytest.mark.asyncio
    async def test_embed_texts_batch(self, embedding_service):
        """Test batch text embedding"""
        texts = ["Query 1", "Query 2", "Query 3"]
        embeddings = await embedding_service.embed_texts(texts)
        
        assert embeddings.shape == (3, embedding_service.dimension)
        assert not np.isnan(embeddings).any()
    
    @pytest.mark.asyncio
    async def test_embedding_normalization(self, embedding_service):
        """Test that embeddings are normalized"""
        text = "Test query"
        embedding = await embedding_service.embed_text(text)
        
        # Check L2 norm is approximately 1
        norm = np.linalg.norm(embedding)
        assert abs(norm - 1.0) < 0.01


class TestDocumentChunker:
    """Tests for document chunking"""
    
    def test_chunk_text_basic(self):
        """Test basic text chunking"""
        text = "a" * 1000
        chunks = DocumentChunker.chunk_text(text, chunk_size=300, overlap=50)
        
        assert len(chunks) > 1
        assert all(len(chunk) <= 300 for chunk in chunks)
    
    def test_chunk_text_small(self):
        """Test chunking of small text"""
        text = "small"
        chunks = DocumentChunker.chunk_text(text)
        
        assert len(chunks) == 1
        assert chunks[0] == text
    
    def test_chunk_overlap(self):
        """Test chunk overlap"""
        text = "a" * 500
        chunks = DocumentChunker.chunk_text(text, chunk_size=200, overlap=50)
        
        # Check overlap between consecutive chunks
        for i in range(len(chunks) - 1):
            # Last 50 chars of chunk i should overlap with first 50 of chunk i+1
            assert chunks[i][-50:] == chunks[i + 1][:50]


class TestRAGSystem:
    """Tests for RAG system"""
    
    @pytest_asyncio.fixture
    async def rag_system(self):
        system = RAGSystem()
        yield system
        await system.clear()
    
    @pytest.mark.asyncio
    async def test_add_document(self, rag_system):
        """Test document addition"""
        content = "This is test content for RAG system testing"
        chunks = await rag_system.add_document(content, "test_doc.txt")
        
        assert chunks > 0
        assert "test_doc.txt" in rag_system.documents
    
    @pytest.mark.asyncio
    async def test_retrieve_context(self, rag_system):
        """Test context retrieval"""
        doc1 = "Machine learning is a subset of artificial intelligence"
        doc2 = "Neural networks are inspired by biological neurons"
        
        await rag_system.add_document(doc1, "ai.txt")
        await rag_system.add_document(doc2, "nn.txt")
        
        # Query related to first document
        chunks = await rag_system.retrieve_context("What is machine learning?", top_k=2)
        
        assert len(chunks) > 0
        assert chunks[0].relevance_score > 0
    
    @pytest.mark.asyncio
    async def test_build_context_prompt(self, rag_system):
        """Test context prompt building"""
        from app.models.schemas import DocumentChunk
        
        chunks = [
            DocumentChunk(content="Content 1", source="doc1.txt", relevance_score=0.9),
            DocumentChunk(content="Content 2", source="doc2.txt", relevance_score=0.8)
        ]
        
        prompt = rag_system.build_context_prompt(chunks)
        
        assert "Content 1" in prompt
        assert "Content 2" in prompt
        assert "doc1.txt" in prompt
    
    @pytest.mark.asyncio
    async def test_rag_statistics(self, rag_system):
        """Test RAG statistics"""
        await rag_system.add_document("Test content", "test1.txt")
        await rag_system.add_document("More test content", "test2.txt")
        
        stats = rag_system.get_stats()
        
        assert stats["total_documents"] == 2
        assert stats["total_chunks"] > 0


class TestCacheService:
    """Tests for cache service"""
    
    @pytest_asyncio.fixture
    async def cache_service(self):
        service = CacheService()
        if service.backend:
            await service.backend.clear()
        yield service
        if service.backend:
            await service.close()
    
    @pytest.mark.asyncio
    async def test_cache_set_get(self, cache_service):
        """Test cache set and get"""
        if not cache_service.backend:
            pytest.skip("Cache backend not available")
        
        data = {"response": "test response", "metadata": {"key": "value"}}
        
        # Set cache
        await cache_service.set("test_query", True, data)
        
        # Get from cache
        cached = await cache_service.get("test_query", True)
        
        assert cached is not None
        assert cached["response"] == "test response"
    
    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_service):
        """Test cache miss"""
        if not cache_service.backend:
            pytest.skip("Cache backend not available")
        
        result = await cache_service.get("nonexistent_query", True)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_clear(self, cache_service):
        """Test cache clearing"""
        if not cache_service.backend:
            pytest.skip("Cache backend not available")
        
        data = {"response": "test"}
        await cache_service.set("test_query", True, data)
        
        # Clear cache
        await cache_service.clear()
        
        # Verify cleared
        result = await cache_service.get("test_query", True)
        assert result is None


class TestLatencyProfiler:
    """Tests for latency profiler"""
    
    def test_profiler_creation(self):
        """Test profiler creation"""
        profiler = LatencyProfiler(sla_ms=800)
        
        assert profiler.sla_ms == 800
        assert len(profiler.latencies) == 0
    
    def test_record_latency_under_sla(self):
        """Test recording latency under SLA"""
        profiler = LatencyProfiler(sla_ms=800)
        
        latency_data = profiler.start_profile("test query")
        latency_data.total_execution_ms = 500.0
        latency_data.embedding_ms = 100.0
        latency_data.llm_call_ms = 400.0
        
        profiler.record_latency(latency_data)
        
        assert latency_data.under_sla == True
        assert len(profiler.latencies) == 1
    
    def test_record_latency_over_sla(self):
        """Test recording latency over SLA"""
        profiler = LatencyProfiler(sla_ms=800)
        
        latency_data = profiler.start_profile("test query")
        latency_data.total_execution_ms = 1000.0
        
        profiler.record_latency(latency_data)
        
        assert latency_data.under_sla == False
    
    def test_statistics(self):
        """Test latency statistics calculation"""
        profiler = LatencyProfiler(sla_ms=800)
        
        # Record multiple latencies
        for i in range(10):
            latency_data = profiler.start_profile(f"query_{i}")
            latency_data.total_execution_ms = 400.0 + (i * 10)
            profiler.record_latency(latency_data)
        
        stats = profiler.get_statistics()
        
        assert stats["total_queries"] == 10
        assert stats["average_latency_ms"] > 0
        assert stats["sla_compliance"] > 0


class TestQueryService:
    """Tests for query service"""
    
    @pytest_asyncio.fixture
    async def query_service(self):
        service = QueryService()
        return service
    
    def test_build_system_prompt_with_context(self, query_service):
        """Test system prompt building"""
        context = "Context information here"
        prompt = query_service._build_system_prompt(context)
        
        assert "Context information here" in prompt
        assert "helpful AI assistant" in prompt
    
    def test_build_system_prompt_without_context(self, query_service):
        """Test system prompt without context"""
        prompt = query_service._build_system_prompt("")
        
        assert "helpful AI assistant" in prompt
    
    def test_calculate_confidence(self, query_service):
        """Test confidence calculation"""
        from app.models.schemas import DocumentChunk
        
        chunks = [
            DocumentChunk(content="Content 1", source="doc1.txt", relevance_score=0.9),
            DocumentChunk(content="Content 2", source="doc2.txt", relevance_score=0.85)
        ]
        
        response = "This is a detailed response with multiple sentences"
        confidence = query_service._calculate_confidence(response, chunks)
        
        assert 0 <= confidence <= 1
        assert confidence > 0.5


class TestLLMService:
    """Tests for LLM service"""
    
    @pytest.mark.asyncio
    async def test_llm_service_initialization(self):
        """Test LLM service can be initialized"""
        # This test just checks initialization doesn't crash
        # Actual API testing requires valid credentials
        try:
            service = LLMService()
            assert service.provider is not None
        except ValueError as e:
            # Expected if no API key configured
            assert "API_KEY" in str(e) or "not set" in str(e)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
