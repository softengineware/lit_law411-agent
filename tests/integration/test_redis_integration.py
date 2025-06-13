"""Integration tests for Redis functionality."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from src.core.config import settings
from src.db.redis_client import RedisManager, RedisCache, cache, redis_manager
from src.db.cache_manager import CacheInvalidationManager, CacheWarmer, CacheHealthChecker
from src.utils.cache_decorators import cached, cache_invalidate, rate_limit


@pytest.fixture
async def redis_client():
    """Provide Redis client for testing."""
    manager = RedisManager()
    try:
        await manager.connect()
        yield manager
    finally:
        await manager.disconnect()


@pytest.fixture
async def cache_client(redis_client):
    """Provide cache client for testing."""
    return RedisCache(redis_client)


class TestRedisManager:
    """Test Redis connection manager."""
    
    @pytest.mark.asyncio
    async def test_redis_connection(self):
        """Test Redis connection establishment."""
        manager = RedisManager()
        
        # Test connection
        await manager.connect()
        assert manager._client is not None
        
        # Test health check
        is_healthy = await manager.health_check()
        assert is_healthy is True
        
        # Test disconnection
        await manager.disconnect()
    
    @pytest.mark.asyncio
    async def test_connection_failure_handling(self):
        """Test handling of connection failures."""
        manager = RedisManager()
        
        # Mock connection failure
        with patch('redis.asyncio.ConnectionPool.from_url') as mock_pool:
            mock_pool.side_effect = ConnectionError("Redis unavailable")
            
            with pytest.raises(ConnectionError):
                await manager.connect()
    
    @pytest.mark.asyncio
    async def test_client_access_before_connection(self):
        """Test accessing client before connection raises error."""
        manager = RedisManager()
        
        with pytest.raises(RuntimeError, match="Redis client not initialized"):
            _ = manager.client


class TestRedisCache:
    """Test Redis cache operations."""
    
    @pytest.mark.asyncio
    async def test_basic_cache_operations(self, cache_client):
        """Test basic get/set/delete operations."""
        key = "test_key"
        value = {"data": "test_value", "number": 42}
        
        # Test set
        success = await cache_client.set(key, value, ttl=60)
        assert success is True
        
        # Test get
        retrieved = await cache_client.get(key)
        assert retrieved == value
        
        # Test exists
        exists = await cache_client.exists(key)
        assert exists is True
        
        # Test delete
        deleted = await cache_client.delete(key)
        assert deleted is True
        
        # Verify deletion
        retrieved_after_delete = await cache_client.get(key)
        assert retrieved_after_delete is None
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache_client):
        """Test cache TTL functionality."""
        key = "expiring_key"
        value = "expiring_value"
        
        # Set with 1 second TTL
        await cache_client.set(key, value, ttl=1)
        
        # Should exist immediately
        assert await cache_client.exists(key) is True
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        assert await cache_client.get(key) is None
    
    @pytest.mark.asyncio
    async def test_counter_operations(self, cache_client):
        """Test increment/decrement operations."""
        key = "counter_key"
        
        # Test increment
        result = await cache_client.increment(key, 5)
        assert result == 5
        
        result = await cache_client.increment(key, 3)
        assert result == 8
        
        # Test decrement
        result = await cache_client.decrement(key, 2)
        assert result == 6
        
        # Clean up
        await cache_client.delete(key)
    
    @pytest.mark.asyncio
    async def test_multiple_operations(self, cache_client):
        """Test batch get/set operations."""
        data = {
            "key1": {"value": 1},
            "key2": {"value": 2},
            "key3": {"value": 3},
        }
        
        # Test set multiple
        success = await cache_client.set_multiple(data, ttl=60)
        assert success is True
        
        # Test get multiple
        retrieved = await cache_client.get_multiple(list(data.keys()))
        assert retrieved == data
        
        # Clean up
        for key in data.keys():
            await cache_client.delete(key)
    
    @pytest.mark.asyncio
    async def test_pattern_clearing(self, cache_client):
        """Test clearing keys by pattern."""
        # Set test keys
        test_keys = {
            "test:user:1": "data1",
            "test:user:2": "data2", 
            "test:content:1": "data3",
            "other:key": "data4",
        }
        
        for key, value in test_keys.items():
            await cache_client.set(key, value)
        
        # Clear user pattern
        cleared = await cache_client.clear_pattern("test:user:*")
        assert cleared == 2
        
        # Verify only user keys were cleared
        assert await cache_client.get("test:user:1") is None
        assert await cache_client.get("test:user:2") is None
        assert await cache_client.get("test:content:1") == "data3"
        assert await cache_client.get("other:key") == "data4"
        
        # Clean up remaining keys
        await cache_client.delete("test:content:1")
        await cache_client.delete("other:key")


class TestCacheDecorators:
    """Test cache decorators."""
    
    @pytest.mark.asyncio
    async def test_cached_decorator(self, cache_client):
        """Test @cached decorator functionality."""
        call_count = 0
        
        @cached(ttl=60, key_prefix="test_func")
        async def expensive_function(param1, param2=None):
            nonlocal call_count
            call_count += 1
            return f"result_{param1}_{param2}"
        
        # First call should execute function
        result1 = await expensive_function("a", param2="b")
        assert result1 == "result_a_b"
        assert call_count == 1
        
        # Second call with same params should use cache
        result2 = await expensive_function("a", param2="b")
        assert result2 == "result_a_b"
        assert call_count == 1  # Should not increment
        
        # Call with different params should execute function
        result3 = await expensive_function("c", param2="d")
        assert result3 == "result_c_d"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_invalidate_decorator(self, cache_client):
        """Test @cache_invalidate decorator."""
        # Set some cached data
        await cache_client.set("test:data:1", "cached_value")
        await cache_client.set("test:data:2", "cached_value")
        
        @cache_invalidate(key_pattern="test:data:*")
        async def update_data():
            return "data_updated"
        
        # Verify data exists before
        assert await cache_client.get("test:data:1") == "cached_value"
        
        # Call function with invalidation
        result = await update_data()
        assert result == "data_updated"
        
        # Verify data was invalidated
        assert await cache_client.get("test:data:1") is None
        assert await cache_client.get("test:data:2") is None
    
    @pytest.mark.asyncio
    async def test_rate_limit_decorator(self, cache_client):
        """Test @rate_limit decorator."""
        from fastapi import HTTPException
        
        @rate_limit(limit=2, window=60, identifier="test_endpoint")
        async def limited_function():
            return "success"
        
        # First two calls should succeed
        result1 = await limited_function()
        assert result1 == "success"
        
        result2 = await limited_function()
        assert result2 == "success"
        
        # Third call should raise rate limit exception
        with pytest.raises(HTTPException) as exc_info:
            await limited_function()
        
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in str(exc_info.value.detail)


class TestCacheManagement:
    """Test cache management functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_manager(self, cache_client):
        """Test cache invalidation manager."""
        invalidator = CacheInvalidationManager(cache_client)
        
        # Set up test data
        user_id = "user123"
        content_id = "content456"
        
        await cache_client.set(f"user:{user_id}", "user_data")
        await cache_client.set(f"user:{user_id}:preferences", "user_prefs")
        await cache_client.set(f"content:{content_id}", "content_data")
        await cache_client.set(f"search:query1", "search_results")
        
        # Test user invalidation
        cleared = await invalidator.invalidate_user_data(user_id)
        assert cleared >= 2  # Should clear user data and preferences
        assert await cache_client.get(f"user:{user_id}") is None
        
        # Test content invalidation
        cleared = await invalidator.invalidate_content_data(content_id)
        assert cleared >= 1  # Should clear content data and search cache
        assert await cache_client.get(f"content:{content_id}") is None
    
    @pytest.mark.asyncio
    async def test_cache_warmer(self, cache_client):
        """Test cache warming functionality."""
        warmer = CacheWarmer(cache_client)
        
        # Test user warming (mock implementation)
        user_ids = ["user1", "user2", "user3"]
        warmed = await warmer.warm_user_data(user_ids)
        # In real implementation, this would warm actual data
        assert warmed >= 0
        
        # Test content warming (mock implementation)
        content_ids = ["content1", "content2"]
        warmed = await warmer.warm_popular_content(content_ids)
        assert warmed >= 0
    
    @pytest.mark.asyncio
    async def test_cache_health_checker(self, cache_client):
        """Test cache health checking."""
        health_checker = CacheHealthChecker(cache_client)
        
        # Test connectivity
        is_connected = await health_checker.check_connectivity()
        assert is_connected is True
        
        # Test performance check
        performance = await health_checker.check_performance()
        assert "set_latency_ms" in performance
        assert "get_latency_ms" in performance
        assert "test_successful" in performance
        assert performance["test_successful"] is True
        
        # Test full health report
        health_report = await health_checker.get_full_health_report()
        assert "healthy" in health_report
        assert "connectivity" in health_report
        assert "performance" in health_report
        assert health_report["healthy"] is True


class TestRedisIntegrationWithApp:
    """Test Redis integration with FastAPI app."""
    
    @pytest.mark.asyncio
    async def test_redis_startup_shutdown(self):
        """Test Redis connection during app lifecycle."""
        manager = RedisManager()
        
        # Simulate app startup
        await manager.connect()
        assert await manager.health_check() is True
        
        # Simulate app shutdown
        await manager.disconnect()
        
        # Health check should fail after disconnect
        assert await manager.health_check() is False
    
    @pytest.mark.asyncio
    async def test_cache_error_handling(self, cache_client):
        """Test cache operations handle Redis errors gracefully."""
        # Mock Redis error
        with patch.object(cache_client.client, 'get', side_effect=Exception("Redis error")):
            # Should return default value on error
            result = await cache_client.get("test_key", default="fallback")
            assert result == "fallback"
        
        with patch.object(cache_client.client, 'set', side_effect=Exception("Redis error")):
            # Should return False on error
            result = await cache_client.set("test_key", "value")
            assert result is False


# Fixtures for Celery testing
@pytest.fixture
def celery_config():
    """Celery configuration for testing."""
    return {
        "broker_url": "redis://localhost:6379/1",
        "result_backend": "redis://localhost:6379/1",
        "task_always_eager": True,
        "task_eager_propagates": True,
    }


class TestCeleryIntegration:
    """Test Celery integration with Redis."""
    
    def test_celery_app_configuration(self):
        """Test Celery app is properly configured."""
        from src.workers.celery_app import celery_app
        
        assert celery_app.conf.broker_url == settings.get_redis_url()
        assert celery_app.conf.result_backend == settings.get_redis_url()
        assert celery_app.conf.task_serializer == "json"
    
    @pytest.mark.asyncio 
    async def test_health_check_task(self):
        """Test Celery health check task."""
        from src.workers.celery_app import health_check
        
        # Execute health check task
        result = health_check()
        
        assert result["status"] == "healthy"
        assert "execution_time" in result
        assert isinstance(result["execution_time"], float)