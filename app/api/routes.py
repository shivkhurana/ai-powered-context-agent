"""
FastAPI routes for AI Data Retrieval Agent
Main API endpoints for queries, documents, and monitoring
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import Optional, List
import logging

from app.models.schemas import (
    QueryRequest, QueryResponse, DocumentUploadRequest,
    HealthResponse, LatencyMetrics, BatchQueryRequest, BatchQueryResponse
)
from app.services.query_service import get_query_service
from app.services.rag_system import get_rag_system
from app.services.cache_service import get_cache_service
from app.services.llm_service import get_llm_service
from app.core.config import settings
from app.core.profiler import get_profiler
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["queries"])


# Health and Status Endpoints

@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint
    Verifies all services are operational
    """
    services = {}
    
    try:
        llm_service = await get_llm_service()
        llm_ok = await llm_service.validate_connection()
        services["llm"] = "operational" if llm_ok else "degraded"
    except Exception as e:
        logger.error(f"LLM health check failed: {e}")
        services["llm"] = "down"
    
    try:
        cache_service = await get_cache_service()
        services["cache"] = "operational" if cache_service.backend else "disabled"
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        services["cache"] = "down"
    
    try:
        rag_system = await get_rag_system()
        stats = rag_system.get_stats()
        services["rag"] = "operational" if stats["total_documents"] > 0 else "ready"
    except Exception as e:
        logger.error(f"RAG health check failed: {e}")
        services["rag"] = "down"
    
    # Overall status
    status = "healthy" if all(v in ["operational", "ready"] for v in services.values()) else "degraded"
    
    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        version=settings.API_VERSION,
        services=services
    )


@router.get("/stats", tags=["monitoring"])
async def get_statistics():
    """Get system statistics"""
    profiler = get_profiler()
    rag_system = await get_rag_system()
    
    return {
        "rag_statistics": rag_system.get_stats(),
        "latency_statistics": profiler.get_statistics(),
        "cache_enabled": settings.ENABLE_CACHE,
        "rag_enabled": settings.ENABLE_RAG
    }


# Query Endpoints

@router.post("/query", response_model=QueryResponse, tags=["queries"])
async def process_query(request: QueryRequest) -> QueryResponse:
    """
    Process user query with RAG context injection and LLM response
    
    **Performance Target**: < 800ms response time
    
    Request body:
    - `query`: User question (required)
    - `use_rag`: Enable context injection (default: true)
    - `include_metadata`: Include response metadata (default: true)
    """
    try:
        query_service = await get_query_service()
        response = await query_service.process_query(request)
        return response
    except TimeoutError as e:
        logger.error(f"Query timeout: {e}")
        raise HTTPException(
            status_code=504,
            detail="Query processing exceeded timeout (800ms SLA)"
        )
    except Exception as e:
        logger.error(f"Query processing error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


@router.post("/batch-query", response_model=BatchQueryResponse, tags=["queries"])
async def process_batch_queries(request: BatchQueryRequest) -> BatchQueryResponse:
    """
    Process multiple queries in parallel
    
    Maximum 10 queries per request
    """
    import asyncio
    
    if len(request.queries) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 queries per batch request"
        )
    
    try:
        import time
        batch_start = time.time()
        
        query_service = await get_query_service()
        
        # Process queries in parallel
        results = await asyncio.gather(
            *[query_service.process_query(q) for q in request.queries],
            return_exceptions=True
        )
        
        # Handle exceptions
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch query error: {result}")
                raise result
            processed_results.append(result)
        
        total_time = (time.time() - batch_start) * 1000
        avg_time = total_time / len(processed_results)
        
        return BatchQueryResponse(
            results=processed_results,
            total_time_ms=total_time,
            average_time_per_query_ms=avg_time,
            all_under_sla=all(
                (r.metadata.execution_time_ms if r.metadata else 0) <= 800
                for r in processed_results
            )
        )
    
    except Exception as e:
        logger.error(f"Batch query error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing batch: {str(e)}"
        )


@router.get("/latency-metrics", response_model=List[LatencyMetrics], tags=["monitoring"])
async def get_latency_metrics(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get recent latency metrics
    
    Returns recorded query execution times and component timings
    """
    profiler = get_profiler()
    
    latencies = profiler.latencies[offset:offset + limit]
    
    return [
        LatencyMetrics(
            query=l.query,
            total_execution_ms=l.total_execution_ms,
            embedding_time_ms=l.embedding_ms,
            retrieval_time_ms=l.retrieval_ms,
            llm_call_time_ms=l.llm_call_ms,
            response_parsing_time_ms=l.response_parsing_ms,
            cache_lookup_time_ms=l.cache_lookup_ms,
            under_sla=l.under_sla
        )
        for l in latencies
    ]


# Document Management Endpoints

@router.post("/documents/upload", tags=["documents"])
async def upload_document(request: DocumentUploadRequest):
    """
    Upload document for RAG context
    
    Documents are chunked and indexed for semantic search
    """
    try:
        rag_system = await get_rag_system()
        
        chunk_count = await rag_system.add_document(
            content=request.content,
            source=request.document_name
        )
        
        return {
            "status": "success",
            "document_name": request.document_name,
            "chunks_created": chunk_count,
            "message": f"Document uploaded with {chunk_count} chunks"
        }
    except Exception as e:
        logger.error(f"Document upload error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading document: {str(e)}"
        )


@router.get("/documents", tags=["documents"])
async def list_documents():
    """Get list of loaded documents"""
    try:
        rag_system = await get_rag_system()
        stats = rag_system.get_stats()
        
        return {
            "documents": list(rag_system.documents.keys()),
            "total_documents": stats["total_documents"],
            "total_chunks": stats["total_chunks"],
            "embedding_dimension": stats["embedding_dimension"]
        }
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing documents: {str(e)}"
        )


@router.delete("/documents/{document_name}", tags=["documents"])
async def delete_document(document_name: str):
    """Delete document from RAG system"""
    try:
        rag_system = await get_rag_system()
        
        if document_name in rag_system.documents:
            del rag_system.documents[document_name]
            rag_system._rebuild_index()
            
            return {
                "status": "success",
                "document_name": document_name,
                "message": "Document deleted"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{document_name}' not found"
            )
    except Exception as e:
        logger.error(f"Document delete error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting document: {str(e)}"
        )


@router.delete("/documents", tags=["documents"])
async def clear_documents():
    """Clear all documents from RAG system"""
    try:
        rag_system = await get_rag_system()
        await rag_system.clear()
        
        return {
            "status": "success",
            "message": "All documents cleared"
        }
    except Exception as e:
        logger.error(f"Error clearing documents: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing documents: {str(e)}"
        )


# Cache Management Endpoints

@router.post("/cache/clear", tags=["cache"])
async def clear_cache():
    """Clear response cache"""
    try:
        cache_service = await get_cache_service()
        cleared = await cache_service.clear()
        
        return {
            "status": "success",
            "cache_cleared": cleared,
            "message": "Cache cleared" if cleared else "Cache not enabled"
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing cache: {str(e)}"
        )


# Profiling Endpoints

@router.get("/profile/export", tags=["profiling"])
async def export_profile(background_tasks: BackgroundTasks):
    """
    Export profiling data to file
    
    Returns download link to profiling report
    """
    try:
        profiler = get_profiler()
        output_file = f"{settings.PROFILE_OUTPUT_DIR}/latency_report.json"
        
        def export_in_background():
            profiler.export_latencies(output_file)
        
        background_tasks.add_task(export_in_background)
        
        return {
            "status": "exporting",
            "message": "Profiling data export started",
            "output_file": output_file
        }
    except Exception as e:
        logger.error(f"Error exporting profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error exporting profile: {str(e)}"
        )
