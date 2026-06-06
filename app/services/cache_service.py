"""
Caching layer for responses and embeddings
Supports Redis and disk-based caching with TTL
"""

import json
import hashlib
import time
import logging
import asyncio
from typing import Optional, Any, Dict
from abc import ABC, abstractmethod
import diskcache

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract cache backend"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """Clear entire cache"""
        pass
    
    @abstractmethod
    async def close(self):
        """Close cache connection"""
        pass


class RedisCache(CacheBackend):
    """Redis-based cache"""
    
    def __init__(self, url: str = settings.REDIS_URL):
        self.url = url
        self.redis: Optional[redis.Redis] = None
        self.ttl = settings.CACHE_TTL
    
    async def connect(self):
        """Establish Redis connection"""
        if redis is None:
            raise ImportError("redis package not installed")
        
        try:
            self.redis = await redis.from_url(self.url, decode_responses=True)
            await self.redis.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        if not self.redis:
            await self.connect()
        
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in Redis"""
        if not self.redis:
            await self.connect()
        
        try:
            ttl = ttl or self.ttl
            await self.redis.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from Redis"""
        if not self.redis:
            return False
        
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False
    
    async def clear(self) -> bool:
        """Clear Redis cache"""
        if not self.redis:
            return False
        
        try:
            await self.redis.flushdb()
            return True
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")
            return False
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()


class DiskCache(CacheBackend):
    """Disk-based cache using diskcache"""
    
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = cache_dir
        self.cache = diskcache.Cache(cache_dir, size_limit=settings.CACHE_MAX_SIZE * 1024 * 1024)
        self.ttl = settings.CACHE_TTL
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from disk cache"""
        try:
            return self.cache.get(key)
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in disk cache"""
        try:
            ttl = ttl or self.ttl
            self.cache.set(key, value, expire=ttl)
            return True
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from disk cache"""
        try:
            del self.cache[key]
            return True
        except KeyError:
            return False
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False
    
    async def clear(self) -> bool:
        """Clear disk cache"""
        try:
            self.cache.clear()
            return True
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")
            return False
    
    async def close(self):
        """Close disk cache"""
        try:
            self.cache.close()
        except Exception as e:
            logger.warning(f"Cache close error: {e}")


class CacheService:
    """Unified cache service"""
    
    def __init__(self):
        self.backend: Optional[CacheBackend] = None
        self._initialize_backend()
    
    def _initialize_backend(self):
        """Initialize cache backend"""
        if not settings.ENABLE_CACHE:
            logger.info("Caching disabled")
            return
        
        try:
            if settings.CACHE_TYPE.lower() == "redis":
                self.backend = RedisCache()
                logger.info("Initialized Redis cache")
            elif settings.CACHE_TYPE.lower() == "disk":
                self.backend = DiskCache()
                logger.info("Initialized disk cache")
            else:
                logger.warning(f"Unknown cache type: {settings.CACHE_TYPE}")
        except Exception as e:
            logger.warning(f"Cache initialization failed: {e}, continuing without cache")
    
    def _get_cache_key(self, query: str, use_rag: bool) -> str:
        """Generate cache key from query"""
        key_str = f"{query}:{use_rag}"
        return f"query:{hashlib.md5(key_str.encode()).hexdigest()}"
    
    async def get(self, query: str, use_rag: bool) -> Optional[Dict]:
        """Get cached response"""
        if not self.backend or not settings.ENABLE_CACHE:
            return None
        
        cache_key = self._get_cache_key(query, use_rag)
        
        try:
            return await self.backend.get(cache_key)
        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")
            return None
    
    async def set(self, query: str, use_rag: bool, response: Dict, ttl: Optional[int] = None) -> bool:
        """Cache response"""
        if not self.backend or not settings.ENABLE_CACHE:
            return False
        
        cache_key = self._get_cache_key(query, use_rag)
        
        try:
            return await self.backend.set(cache_key, response, ttl)
        except Exception as e:
            logger.warning(f"Cache storage error: {e}")
            return False
    
    async def clear(self) -> bool:
        """Clear cache"""
        if not self.backend:
            return False
        
        try:
            return await self.backend.clear()
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")
            return False
    
    async def close(self):
        """Close cache connection"""
        if self.backend:
            try:
                await self.backend.close()
            except Exception as e:
                logger.warning(f"Cache close error: {e}")


# Global cache service instance
_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """Get or create cache service singleton"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
