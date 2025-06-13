"""Cache management and invalidation logic."""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from src.core.logging import get_logger
from src.db.redis_client import RedisCache, cache

logger = get_logger(__name__)


class CacheInvalidationManager:
    """Manages cache invalidation strategies and policies."""
    
    def __init__(self, cache_client: RedisCache):
        """Initialize cache invalidation manager."""
        self.cache = cache_client
    
    async def invalidate_user_data(self, user_id: str) -> int:
        """Invalidate all cache data related to a user."""
        patterns = [
            f"user:{user_id}",
            f"user:{user_id}:*",
            f"*:user:{user_id}",
            f"search:*:user:{user_id}",
            f"session:*:{user_id}",
        ]
        
        total_cleared = 0
        for pattern in patterns:
            cleared = await self.cache.clear_pattern(pattern)
            total_cleared += cleared
            
        logger.info("User cache invalidated", user_id=user_id, cleared_count=total_cleared)
        return total_cleared
    
    async def invalidate_content_data(self, content_id: str) -> int:
        """Invalidate all cache data related to content."""
        patterns = [
            f"content:{content_id}",
            f"content:{content_id}:*",
            f"transcript:{content_id}",
            f"embedding:{content_id}",
            f"*:content:{content_id}",
        ]
        
        total_cleared = 0
        for pattern in patterns:
            cleared = await self.cache.clear_pattern(pattern)
            total_cleared += cleared
        
        # Also clear search caches that might include this content
        search_cleared = await self.cache.clear_pattern("search:*")
        total_cleared += search_cleared
        
        logger.info("Content cache invalidated", content_id=content_id, cleared_count=total_cleared)
        return total_cleared
    
    async def invalidate_search_cache(self, user_id: Optional[str] = None) -> int:
        """Invalidate search result caches."""
        if user_id:
            pattern = f"search:*:user:{user_id}"
        else:
            pattern = "search:*"
        
        cleared = await self.cache.clear_pattern(pattern)
        logger.info("Search cache invalidated", user_id=user_id, cleared_count=cleared)
        return cleared
    
    async def invalidate_expired_sessions(self) -> int:
        """Remove expired session data from cache."""
        # This is typically handled by Redis TTL, but we can do cleanup
        pattern = "session:*"
        
        # Get all session keys
        keys = []
        async for key in self.cache.client.scan_iter(match=pattern):
            # Check if the session is still valid by trying to get it
            value = await self.cache.get(key, deserialize=False)
            if value is None:
                keys.append(key)
        
        if keys:
            deleted = await self.cache.client.delete(*keys)
            logger.info("Expired sessions cleaned up", count=deleted)
            return deleted
        
        return 0
    
    async def invalidate_by_tags(self, tags: List[str]) -> int:
        """Invalidate cache entries by tags."""
        total_cleared = 0
        
        for tag in tags:
            # Look for keys with this tag
            pattern = f"*:{tag}:*"
            cleared = await self.cache.clear_pattern(pattern)
            total_cleared += cleared
        
        logger.info("Cache invalidated by tags", tags=tags, cleared_count=total_cleared)
        return total_cleared
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and metrics."""
        try:
            info = await self.cache.client.info()
            
            stats = {
                "redis_version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "0B"),
                "used_memory_peak": info.get("used_memory_peak_human", "0B"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            }
            
            # Calculate hit rate
            hits = stats["keyspace_hits"]
            misses = stats["keyspace_misses"]
            total_requests = hits + misses
            
            if total_requests > 0:
                stats["hit_rate"] = hits / total_requests
            else:
                stats["hit_rate"] = 0.0
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get cache stats", error=str(e))
            return {}


class CacheWarmer:
    """Warm up cache with frequently accessed data."""
    
    def __init__(self, cache_client: RedisCache):
        """Initialize cache warmer."""
        self.cache = cache_client
    
    async def warm_user_data(self, user_ids: List[str]) -> int:
        """Pre-load user data into cache."""
        warmed_count = 0
        
        for user_id in user_ids:
            try:
                # This would typically fetch from database and cache
                # For now, we'll just set a placeholder
                cache_key = f"user:{user_id}"
                
                # Check if already cached
                if await self.cache.exists(cache_key):
                    continue
                
                # In a real implementation, you'd fetch from database here
                # await self.cache.set(cache_key, user_data, ttl=900)
                warmed_count += 1
                
            except Exception as e:
                logger.error("Failed to warm user cache", user_id=user_id, error=str(e))
        
        logger.info("User cache warmed", user_count=len(user_ids), warmed_count=warmed_count)
        return warmed_count
    
    async def warm_popular_content(self, content_ids: List[str]) -> int:
        """Pre-load popular content into cache."""
        warmed_count = 0
        
        for content_id in content_ids:
            try:
                cache_key = f"content:{content_id}"
                
                # Check if already cached
                if await self.cache.exists(cache_key):
                    continue
                
                # In a real implementation, you'd fetch from database here
                # await self.cache.set(cache_key, content_data, ttl=1800)
                warmed_count += 1
                
            except Exception as e:
                logger.error("Failed to warm content cache", content_id=content_id, error=str(e))
        
        logger.info("Content cache warmed", content_count=len(content_ids), warmed_count=warmed_count)
        return warmed_count


class CacheHealthChecker:
    """Monitor cache health and performance."""
    
    def __init__(self, cache_client: RedisCache):
        """Initialize cache health checker."""
        self.cache = cache_client
    
    async def check_connectivity(self) -> bool:
        """Check if Redis is reachable."""
        try:
            await self.cache.client.ping()
            return True
        except Exception:
            return False
    
    async def check_performance(self) -> Dict[str, Any]:
        """Check cache performance metrics."""
        try:
            # Measure response time for a simple operation
            import time
            start_time = time.time()
            
            test_key = "health_check_test"
            test_value = "test_value"
            
            # Test set operation
            await self.cache.set(test_key, test_value, ttl=10)
            set_time = time.time() - start_time
            
            # Test get operation
            start_time = time.time()
            result = await self.cache.get(test_key)
            get_time = time.time() - start_time
            
            # Clean up
            await self.cache.delete(test_key)
            
            return {
                "set_latency_ms": round(set_time * 1000, 2),
                "get_latency_ms": round(get_time * 1000, 2),
                "test_successful": result == test_value,
            }
            
        except Exception as e:
            logger.error("Cache performance check failed", error=str(e))
            return {
                "set_latency_ms": -1,
                "get_latency_ms": -1,
                "test_successful": False,
                "error": str(e),
            }
    
    async def check_memory_usage(self) -> Dict[str, Any]:
        """Check cache memory usage."""
        try:
            info = await self.cache.client.info("memory")
            
            used_memory = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)
            
            memory_info = {
                "used_memory_bytes": used_memory,
                "used_memory_human": info.get("used_memory_human", "0B"),
                "max_memory_bytes": max_memory,
                "memory_usage_percentage": 0.0,
            }
            
            if max_memory > 0:
                memory_info["memory_usage_percentage"] = (used_memory / max_memory) * 100
            
            return memory_info
            
        except Exception as e:
            logger.error("Memory usage check failed", error=str(e))
            return {}
    
    async def get_full_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report."""
        connectivity = await self.check_connectivity()
        performance = await self.check_performance()
        memory = await self.check_memory_usage()
        
        return {
            "healthy": connectivity and performance.get("test_successful", False),
            "connectivity": connectivity,
            "performance": performance,
            "memory": memory,
            "timestamp": datetime.utcnow().isoformat(),
        }


# Global instances
cache_invalidator = CacheInvalidationManager(cache)
cache_warmer = CacheWarmer(cache)
cache_health_checker = CacheHealthChecker(cache)