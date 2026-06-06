"""
Pydantic schemas for API requests and responses
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class QueryRequest(BaseModel):
    """Request model for data retrieval queries"""
    query: str = Field(..., min_length=1, max_length=1000, description="User query")
    use_rag: bool = Field(default=True, description="Enable RAG context injection")
    include_metadata: bool = Field(default=True, description="Include metadata in response")
    timeout: Optional[float] = Field(default=None, description="Custom timeout in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the benefits of machine learning?",
                "use_rag": True,
                "include_metadata": True
            }
        }


class DocumentChunk(BaseModel):
    """Document chunk for context injection"""
    content: str
    source: str
    relevance_score: float = Field(0.0, ge=0.0, le=1.0)
    chunk_index: int = 0


class RAGContext(BaseModel):
    """RAG context data"""
    documents: List[DocumentChunk]
    total_chunks: int
    retrieval_time_ms: float


class ResponseMetadata(BaseModel):
    """Metadata about the response"""
    model_used: str
    llm_provider: str
    execution_time_ms: float
    rag_used: bool
    context_chunks_used: int
    query_embedding_time_ms: float
    llm_execution_time_ms: float
    cache_hit: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QueryResponse(BaseModel):
    """Response model for queries"""
    query: str
    response: str = Field(..., description="AI-generated response")
    confidence_score: float = Field(0.0, ge=0.0, le=1.0, description="Confidence in response (0-1)")
    sources: List[str] = Field(default_factory=list, description="Source documents used")
    metadata: Optional[ResponseMetadata] = None
    rag_context: Optional[RAGContext] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the benefits of machine learning?",
                "response": "Machine learning offers numerous benefits including...",
                "confidence_score": 0.95,
                "sources": ["document1.pdf", "document2.pdf"],
                "metadata": {
                    "model_used": "gpt-4-turbo-preview",
                    "llm_provider": "openai",
                    "execution_time_ms": 450.5,
                    "rag_used": True,
                    "context_chunks_used": 3
                }
            }
        }


class DocumentUploadRequest(BaseModel):
    """Request for document upload"""
    document_name: str = Field(..., description="Name of the document")
    content: str = Field(..., description="Document content")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]


class LatencyMetrics(BaseModel):
    """Latency metrics for profiling"""
    query: str
    total_execution_ms: float
    embedding_time_ms: float
    retrieval_time_ms: float
    llm_call_time_ms: float
    response_parsing_time_ms: float
    cache_lookup_time_ms: float
    under_sla: bool = Field(..., description="Whether response time is under 800ms SLA")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "sample query",
                "total_execution_ms": 650.5,
                "embedding_time_ms": 50.2,
                "retrieval_time_ms": 100.3,
                "llm_call_time_ms": 450.0,
                "response_parsing_time_ms": 30.1,
                "cache_lookup_time_ms": 5.0,
                "under_sla": True
            }
        }


class BatchQueryRequest(BaseModel):
    """Batch query request"""
    queries: List[QueryRequest] = Field(..., min_items=1, max_items=10)


class BatchQueryResponse(BaseModel):
    """Batch query response"""
    results: List[QueryResponse]
    total_time_ms: float
    average_time_per_query_ms: float
    all_under_sla: bool


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: str
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
