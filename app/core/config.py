"""
Configuration management for AI Data Retrieval Agent
Supports environment-based configuration with sensible defaults
"""

from pydantic_settings import BaseSettings
from typing import Optional
import logging


class Settings(BaseSettings):
    """Application configuration settings"""
    
    # API Configuration
    API_TITLE: str = "AI Data Retrieval Agent"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "High-performance AI-powered data retrieval with sub-800ms latency"
    DEBUG: bool = False
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    LOG_LEVEL: str = "INFO"
    
    # LLM Configuration
    LLM_PROVIDER: str = "openai"  # "openai" or "gemini"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-pro"
    LLM_TIMEOUT: float = 25.0  # Total timeout for LLM call
    LLM_TEMPERATURE: float = 0.3  # Lower = more deterministic
    
    # RAG Configuration
    ENABLE_RAG: bool = True
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # Lightweight, fast embeddings
    CONTEXT_WINDOW_SIZE: int = 3  # Number of top documents to retrieve
    SIMILARITY_THRESHOLD: float = 0.5
    MAX_CONTEXT_LENGTH: int = 2000  # Max tokens for context injection
    
    # Caching Configuration
    ENABLE_CACHE: bool = True
    CACHE_TYPE: str = "redis"  # "redis" or "disk"
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 3600  # 1 hour
    CACHE_MAX_SIZE: int = 1000
    
    # Performance Configuration
    MAX_BATCH_SIZE: int = 10
    CONNECTION_POOL_SIZE: int = 20
    QUERY_TIMEOUT: float = 0.8  # Target latency in seconds
    ASYNC_TIMEOUT: float = 20.0  # Async operation timeout
    
    # Document Processing
    CHUNK_SIZE: int = 500  # Characters per chunk
    CHUNK_OVERLAP: int = 50
    
    # Profiling Configuration
    ENABLE_PROFILING: bool = False
    PROFILE_OUTPUT_DIR: str = "./profiles"
    LOG_LATENCY_METRICS: bool = True
    
    # Accuracy Configuration
    TARGET_ACCURACY: float = 0.95
    VALIDATION_ENABLED: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()


def setup_logging():
    """Configure logging with structured output"""
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set noisy library loggers to WARNING
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)


logger = setup_logging()
