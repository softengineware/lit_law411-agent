"""Redis client and connection management for lit_law411-agent."""

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional, Union

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import ConnectionError, RedisError

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class RedisManager:
    """Redis connection and operation manager."""
    
    def __init__(self):
        """Initialize Redis manager."""
        self._client: Optional[Redis] = None
        self._connection_pool: Optional[redis.ConnectionPool] = None
    
    async def connect(self) -> None:
        """Establish Redis connection."""
        try:
            # Create connection pool
            self._connection_pool = redis.ConnectionPool.from_url(
                settings.get_redis_url(),
                max_connections=20,
                retry_on_timeout=True,
                decode_responses=True,
            )
            
            # Create Redis client
            self._client = Redis(connection_pool=self._connection_pool)
            
            # Test connection
            await self._client.ping()
            logger.info("Redis connection established", redis_url=settings.redis_url)
            
        except ConnectionError as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error connecting to Redis", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            logger.info("Redis connection closed")
        
        if self._connection_pool:
            await self._connection_pool.disconnect()
    
    @property
    def client(self) -> Redis:
        """Get Redis client."""
        if not self._client:
            raise RuntimeError("Redis client not initialized. Call connect() first.")
        return self._client
    
    async def health_check(self) -> bool:
        """Check Redis health."""
        try:
            if not self._client:
                return False
            
            await self._client.ping()
            return True
        except Exception:
            return False


class RedisCache:
    """Redis caching operations."""
    
    def __init__(self, redis_manager: RedisManager):
        """Initialize cache with Redis manager."""
        self.redis_manager = redis_manager
    
    @property
    def client(self) -> Redis:
        """Get Redis client."""
        return self.redis_manager.client
    
    async def get(
        self, 
        key: str, 
        default: Any = None,
        deserialize: bool = True
    ) -> Any:
        """Get value from cache."""
        try:
            value = await self.client.get(key)
            if value is None:
                return default
            
            if deserialize:
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            return value
            
        except RedisError as e:
            logger.error("Failed to get cache value", key=key, error=str(e))
            return default
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        serialize: bool = True
    ) -> bool:
        """Set value in cache."""
        try:
            if serialize and not isinstance(value, (str, bytes)):
                value = json.dumps(value, default=str)
            
            result = await self.client.set(key, value, ex=ttl)
            return bool(result)
            
        except RedisError as e:
            logger.error("Failed to set cache value", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            result = await self.client.delete(key)
            return bool(result)
        except RedisError as e:
            logger.error("Failed to delete cache key", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            result = await self.client.exists(key)
            return bool(result)
        except RedisError as e:
            logger.error("Failed to check key existence", key=key, error=str(e))
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for key."""
        try:
            result = await self.client.expire(key, ttl)
            return bool(result)
        except RedisError as e:
            logger.error("Failed to set key expiration", key=key, ttl=ttl, error=str(e))
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter value."""
        try:
            result = await self.client.incrby(key, amount)
            return result
        except RedisError as e:
            logger.error("Failed to increment counter", key=key, amount=amount, error=str(e))
            return None
    
    async def decrement(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement counter value."""
        try:
            result = await self.client.decrby(key, amount)
            return result
        except RedisError as e:
            logger.error("Failed to decrement counter", key=key, amount=amount, error=str(e))
            return None
    
    async def set_multiple(self, mapping: dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple key-value pairs."""
        try:
            # Serialize values if needed
            serialized_mapping = {}
            for k, v in mapping.items():
                if not isinstance(v, (str, bytes)):
                    serialized_mapping[k] = json.dumps(v, default=str)
                else:
                    serialized_mapping[k] = v
            
            # Set all values
            result = await self.client.mset(serialized_mapping)
            
            # Set TTL if specified
            if ttl and result:
                await self.client.expire(*serialized_mapping.keys(), ttl)
            
            return bool(result)
            
        except RedisError as e:
            logger.error("Failed to set multiple cache values", keys=list(mapping.keys()), error=str(e))
            return False
    
    async def get_multiple(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values from cache."""
        try:
            values = await self.client.mget(keys)
            result = {}
            
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        result[key] = value
                        
            return result
            
        except RedisError as e:
            logger.error("Failed to get multiple cache values", keys=keys, error=str(e))
            return {}
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await self.client.delete(*keys)
                logger.info("Cleared cache keys", pattern=pattern, count=deleted)
                return deleted
            
            return 0
            
        except RedisError as e:
            logger.error("Failed to clear cache pattern", pattern=pattern, error=str(e))
            return 0


# Global Redis manager and cache instances
redis_manager = RedisManager()
cache = RedisCache(redis_manager)


@asynccontextmanager
async def get_redis_client() -> AsyncGenerator[Redis, None]:
    """Get Redis client context manager."""
    yield redis_manager.client


async def get_cache() -> RedisCache:
    """Get cache instance."""
    return cache


# Cache key helpers
class CacheKeys:
    """Cache key patterns and generators."""
    
    @staticmethod
    def user(user_id: str) -> str:
        """Generate user cache key."""
        return f"user:{user_id}"
    
    @staticmethod
    def content(content_id: str) -> str:
        """Generate content cache key."""
        return f"content:{content_id}"
    
    @staticmethod
    def search_query(query_hash: str) -> str:
        """Generate search query cache key."""
        return f"search:{query_hash}"
    
    @staticmethod
    def api_rate_limit(identifier: str) -> str:
        """Generate rate limit cache key."""
        return f"rate_limit:{identifier}"
    
    @staticmethod
    def session(session_id: str) -> str:
        """Generate session cache key."""
        return f"session:{session_id}"
    
    @staticmethod
    def embedding(content_id: str) -> str:
        """Generate embedding cache key."""
        return f"embedding:{content_id}"
    
    @staticmethod
    def transcript(content_id: str) -> str:
        """Generate transcript cache key."""
        return f"transcript:{content_id}"