"""
Main FastAPI application
Initializes the AI Data Retrieval Agent server
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings, logger
from app.api.routes import router
from app.services.llm_service import get_llm_service
from app.services.cache_service import get_cache_service
from app.services.rag_system import get_rag_system


# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management
    Handles startup and shutdown events
    """
    # Startup
    logger.info("=" * 60)
    logger.info("Starting AI Data Retrieval Agent")
    logger.info("=" * 60)
    logger.info(f"Configuration:")
    logger.info(f"  - LLM Provider: {settings.LLM_PROVIDER}")
    logger.info(f"  - RAG Enabled: {settings.ENABLE_RAG}")
    logger.info(f"  - Cache Enabled: {settings.ENABLE_CACHE}")
    logger.info(f"  - Target Latency: {settings.QUERY_TIMEOUT * 1000:.0f}ms")
    logger.info(f"  - Target Accuracy: {settings.TARGET_ACCURACY * 100:.0f}%")
    
    try:
        # Initialize services
        llm_service = await get_llm_service()
        logger.info(f"✓ LLM service initialized ({settings.LLM_PROVIDER})")
        
        cache_service = await get_cache_service()
        logger.info(f"✓ Cache service initialized ({settings.CACHE_TYPE})")
        
        rag_system = await get_rag_system()
        logger.info(f"✓ RAG system initialized")
        
        logger.info("All services started successfully!")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("Shutting down AI Data Retrieval Agent")
    logger.info("=" * 60)
    
    try:
        cache_service = await get_cache_service()
        await cache_service.close()
        logger.info("✓ Cache service closed")
    except Exception as e:
        logger.warning(f"Error closing cache: {e}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title=settings.API_TITLE,
        description=settings.API_DESCRIPTION,
        version=settings.API_VERSION,
        lifespan=lifespan,
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add security middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "0.0.0.0"]
    )
    
    # Include routers
    app.include_router(router)
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "application": settings.API_TITLE,
            "version": settings.API_VERSION,
            "status": "online",
            "docs": "/api/v1/docs",
            "health": "/api/v1/health",
            "stats": "/api/v1/stats"
        }
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower()
    )
