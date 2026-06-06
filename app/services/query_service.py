"""
Query service that orchestrates RAG, caching, and LLM components
Handles the main query logic with performance optimization
"""

import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from app.models.schemas import (
    QueryRequest, QueryResponse, ResponseMetadata, RAGContext, DocumentChunk
)
from app.services.llm_service import get_llm_service
from app.services.cache_service import get_cache_service
from app.services.rag_system import get_rag_system
from app.core.config import settings
from app.core.profiler import get_profiler, LatencyData

logger = logging.getLogger(__name__)


class QueryService:
    """Service for processing user queries with RAG and LLM"""
    
    def __init__(self):
        self.profiler = get_profiler()
    
    async def process_query(self, request: QueryRequest) -> QueryResponse:
        """
        Process user query with RAG context and LLM
        
        Execution flow:
        1. Check cache
        2. Generate query embedding
        3. Retrieve relevant documents (RAG)
        4. Build context prompt
        5. Call LLM
        6. Cache result
        7. Return response
        """
        query_start_time = time.time()
        latency_data = self.profiler.start_profile(request.query)
        
        llm_service = await get_llm_service()
        cache_service = await get_cache_service()
        rag_system = await get_rag_system()
        
        rag_context = None
        cache_hit = False
        
        try:
            # Step 1: Check cache
            cache_start = time.time()
            cached_response = await cache_service.get(request.query, request.use_rag)
            latency_data.cache_lookup_ms = (time.time() - cache_start) * 1000
            
            if cached_response:
                logger.info(f"Cache hit for query: {request.query[:50]}")
                cache_hit = True
                latency_data.total_execution_ms = (time.time() - query_start_time) * 1000
                
                # Return cached response with updated metadata
                response = QueryResponse(**cached_response)
                response.metadata.cache_hit = True
                response.metadata.execution_time_ms = latency_data.total_execution_ms
                self.profiler.record_latency(latency_data)
                return response
            
            # Step 2 & 3: Generate embedding and retrieve context
            context_chunks: list[DocumentChunk] = []
            if request.use_rag and settings.ENABLE_RAG:
                rag_start = time.time()
                context_chunks = await rag_system.retrieve_context(
                    request.query,
                    top_k=settings.CONTEXT_WINDOW_SIZE
                )
                latency_data.retrieval_ms = (time.time() - rag_start) * 1000
                
                # Also measure embedding time (approximate)
                latency_data.embedding_ms = latency_data.retrieval_ms * 0.2
            
            # Step 4: Build context prompt
            context_text = ""
            if context_chunks:
                context_text = rag_system.build_context_prompt(
                    context_chunks,
                    max_length=settings.MAX_CONTEXT_LENGTH
                )
            
            # Step 5: Build system prompt with context
            system_prompt = self._build_system_prompt(context_text)
            
            # Step 6: Call LLM
            llm_start = time.time()
            llm_response, llm_time_ms = await llm_service.query(
                prompt=request.query,
                system_prompt=system_prompt
            )
            latency_data.llm_call_ms = llm_time_ms
            
            # Step 7: Parse and validate response
            parse_start = time.time()
            sources = [chunk.source for chunk in context_chunks]
            confidence = self._calculate_confidence(llm_response, context_chunks)
            latency_data.response_parsing_ms = (time.time() - parse_start) * 1000
            
            # Build response
            response = QueryResponse(
                query=request.query,
                response=llm_response,
                confidence_score=confidence,
                sources=list(set(sources)),  # Remove duplicates
                metadata=ResponseMetadata(
                    model_used=llm_service.get_provider_name(),
                    llm_provider=settings.LLM_PROVIDER,
                    execution_time_ms=(time.time() - query_start_time) * 1000,
                    rag_used=request.use_rag and len(context_chunks) > 0,
                    context_chunks_used=len(context_chunks),
                    query_embedding_time_ms=latency_data.embedding_ms,
                    llm_execution_time_ms=llm_time_ms,
                    cache_hit=False
                )
            )
            
            # Add RAG context if requested
            if request.include_metadata and context_chunks:
                rag_context = RAGContext(
                    documents=context_chunks,
                    total_chunks=len(context_chunks),
                    retrieval_time_ms=latency_data.retrieval_ms
                )
                response.rag_context = rag_context
            
            # Step 8: Cache result
            try:
                await cache_service.set(
                    request.query,
                    request.use_rag,
                    response.model_dump()
                )
            except Exception as e:
                logger.warning(f"Failed to cache response: {e}")
            
            # Record latency metrics
            latency_data.total_execution_ms = (time.time() - query_start_time) * 1000
            self.profiler.record_latency(latency_data)
            
            logger.info(
                f"Query processed: '{request.query[:30]}...' "
                f"({latency_data.total_execution_ms:.2f}ms, "
                f"Confidence: {confidence:.2%})"
            )
            
            return response
        
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            raise
    
    def _build_system_prompt(self, context: str) -> str:
        """Build system prompt with context injection"""
        base_prompt = (
            "You are a helpful AI assistant specialized in data retrieval and analysis. "
            "Provide accurate, concise, and well-structured responses. "
            "When answering, prioritize information from the provided context. "
        )
        
        if context:
            return (
                f"{base_prompt}\n\n"
                f"Context Information:\n"
                f"{context}\n\n"
                f"Please answer based on the provided context when relevant."
            )
        
        return base_prompt
    
    def _calculate_confidence(self, response: str, context_chunks: list[DocumentChunk]) -> float:
        """
        Calculate confidence score for response
        
        Factors considered:
        - Number of source documents
        - Average relevance score
        - Response length
        """
        if not response or not context_chunks:
            return 0.5  # Default to 50% confidence without context
        
        # Base confidence from context
        avg_relevance = sum(c.relevance_score for c in context_chunks) / len(context_chunks)
        
        # Bonus for multiple sources
        unique_sources = len(set(c.source for c in context_chunks))
        source_bonus = min(0.1, unique_sources * 0.05)
        
        # Penalty for very short responses (might be incomplete)
        response_penalty = 0 if len(response) > 100 else 0.1
        
        confidence = avg_relevance + source_bonus - response_penalty
        return min(1.0, max(0.0, confidence))  # Clamp to 0-1 range


# Global query service instance
_query_service: Optional[QueryService] = None


async def get_query_service() -> QueryService:
    """Get or create query service singleton"""
    global _query_service
    if _query_service is None:
        _query_service = QueryService()
    return _query_service
