"""Unit tests for rate limiter."""

import pytest
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock

from src.core.rate_limiter import (
    RateLimitExceeded,
    RateLimiter,
    APIKeyRateLimiter,
    IPRateLimiter,
    api_key_rate_limiter,
    ip_rate_limiter,
    general_rate_limiter,
)


class TestRateLimitExceeded:
    """Test cases for RateLimitExceeded exception."""
    
    def test_rate_limit_exceeded_creation(self):
        """Test creating RateLimitExceeded exception."""
        exc = RateLimitExceeded("Rate limit exceeded", 60, "minute")
        
        assert str(exc) == "Rate limit exceeded"
        assert exc.retry_after == 60
        assert exc.limit_type == "minute"


class TestRateLimiter:
    """Test cases for RateLimiter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_cache = Mock()
        self.rate_limiter = RateLimiter()
        self.rate_limiter.cache = self.mock_cache
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self):
        """Test rate limit check when request is allowed."""
        # Mock Redis pipeline operations
        mock_pipeline = Mock()
        mock_pipeline.execute = AsyncMock(return_value=[None, 5, None, None])  # 5 current requests
        
        self.mock_cache.client.pipeline.return_value = mock_pipeline
        self.mock_cache.client.zrange.return_value = [(b"req1", 1234567890.0)]
        
        is_allowed, info = await self.rate_limiter.check_rate_limit(
            identifier="user123",
            limit=10,
            window_seconds=60
        )
        
        assert is_allowed is True
        assert info["limit"] == 10
        assert info["remaining"] == 5
        assert info["current_count"] == 5
        assert "reset_time" in info
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self):
        """Test rate limit check when limit is exceeded."""
        mock_pipeline = Mock()
        mock_pipeline.execute = AsyncMock(return_value=[None, 15, None, None])  # 15 current requests
        
        self.mock_cache.client.pipeline.return_value = mock_pipeline
        self.mock_cache.client.zrem = AsyncMock()
        self.mock_cache.client.zrange.return_value = []
        
        is_allowed, info = await self.rate_limiter.check_rate_limit(
            identifier="user123",
            limit=10,
            window_seconds=60
        )
        
        assert is_allowed is False
        assert info["remaining"] == 0
        assert info["current_count"] == 14  # Decremented because request was removed
        assert info["retry_after"] > 0
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_redis_error(self):
        """Test rate limit check when Redis fails."""
        self.mock_cache.client.pipeline.side_effect = Exception("Redis error")
        
        is_allowed, info = await self.rate_limiter.check_rate_limit(
            identifier="user123",
            limit=10,
            window_seconds=60
        )
        
        # Should allow request on error
        assert is_allowed is True
        assert info["remaining"] == 10
        assert "error" in info
    
    @pytest.mark.asyncio
    async def test_check_multiple_limits_all_allowed(self):
        """Test checking multiple rate limits when all are allowed."""
        with patch.object(self.rate_limiter, 'check_rate_limit') as mock_check:
            mock_check.return_value = (True, {"limit": 10, "remaining": 5})
            
            limits = {
                "minute": (10, 60),
                "hour": (100, 3600)
            }
            
            is_allowed, info = await self.rate_limiter.check_multiple_limits(
                identifier="user123",
                limits=limits
            )
            
            assert is_allowed is True
            assert "minute" in info
            assert "hour" in info
            assert mock_check.call_count == 2
    
    @pytest.mark.asyncio
    async def test_check_multiple_limits_exceeded(self):
        """Test checking multiple rate limits when one is exceeded."""
        def mock_check_side_effect(*args, **kwargs):
            if "minute" in kwargs.get("prefix", ""):
                return (False, {"limit": 10, "remaining": 0, "retry_after": 60})
            return (True, {"limit": 100, "remaining": 50, "retry_after": 0})
        
        with patch.object(self.rate_limiter, 'check_rate_limit', side_effect=mock_check_side_effect):
            limits = {
                "minute": (10, 60),
                "hour": (100, 3600)
            }
            
            with pytest.raises(RateLimitExceeded) as exc_info:
                await self.rate_limiter.check_multiple_limits(
                    identifier="user123",
                    limits=limits
                )
            
            assert "minute" in str(exc_info.value)
            assert exc_info.value.retry_after == 60
    
    @pytest.mark.asyncio
    async def test_reset_rate_limit_specific_window(self):
        """Test resetting rate limit for specific window."""
        self.mock_cache.clear_pattern = AsyncMock(return_value=5)
        
        result = await self.rate_limiter.reset_rate_limit(
            identifier="user123",
            window_seconds=60
        )
        
        assert result is True
        self.mock_cache.clear_pattern.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reset_rate_limit_all_windows(self):
        """Test resetting rate limit for all windows."""
        self.mock_cache.clear_pattern = AsyncMock(return_value=10)
        
        result = await self.rate_limiter.reset_rate_limit(identifier="user123")
        
        assert result is True
        self.mock_cache.clear_pattern.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reset_rate_limit_error(self):
        """Test resetting rate limit with error."""
        self.mock_cache.clear_pattern = AsyncMock(side_effect=Exception("Redis error"))
        
        result = await self.rate_limiter.reset_rate_limit(identifier="user123")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_status(self):
        """Test getting rate limit status."""
        self.mock_cache.client.zremrangebyscore = AsyncMock()
        self.mock_cache.client.zcard = AsyncMock(return_value=5)
        self.mock_cache.client.zrange.return_value = [(b"req1", time.time() - 30)]
        
        limits = {
            "minute": (10, 60),
            "hour": (100, 3600)
        }
        
        status = await self.rate_limiter.get_rate_limit_status(
            identifier="user123",
            limits=limits
        )
        
        assert "minute" in status
        assert "hour" in status
        assert status["minute"]["limit"] == 10
        assert status["minute"]["current"] == 5
        assert status["minute"]["remaining"] == 5
        assert not status["minute"]["is_limited"]
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_status_error(self):
        """Test getting rate limit status with Redis error."""
        self.mock_cache.client.zremrangebyscore = AsyncMock(side_effect=Exception("Redis error"))
        
        limits = {"minute": (10, 60)}
        
        status = await self.rate_limiter.get_rate_limit_status(
            identifier="user123",
            limits=limits
        )
        
        assert "minute" in status
        assert status["minute"]["remaining"] == 10  # Default values on error
        assert "error" in status["minute"]


class TestAPIKeyRateLimiter:
    """Test cases for APIKeyRateLimiter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api_key_limiter = APIKeyRateLimiter()
        self.api_key_limiter.rate_limiter = Mock()
    
    @pytest.mark.asyncio
    async def test_check_api_key_limits(self):
        """Test checking API key rate limits."""
        self.api_key_limiter.rate_limiter.check_multiple_limits = AsyncMock(
            return_value=(True, {"minute": {"remaining": 50}})
        )
        
        is_allowed, info = await self.api_key_limiter.check_api_key_limits(
            api_key_id="key123",
            rate_limit_per_minute=60,
            rate_limit_per_hour=1000,
            rate_limit_per_day=10000
        )
        
        assert is_allowed is True
        assert "minute" in info
        
        # Verify limits were passed correctly
        call_args = self.api_key_limiter.rate_limiter.check_multiple_limits.call_args
        limits = call_args[1]["limits"]
        assert limits["minute"] == (60, 60)
        assert limits["hour"] == (1000, 3600)
        assert limits["day"] == (10000, 86400)
    
    @pytest.mark.asyncio
    async def test_get_api_key_status(self):
        """Test getting API key status."""
        self.api_key_limiter.rate_limiter.get_rate_limit_status = AsyncMock(
            return_value={"minute": {"remaining": 50}}
        )
        
        status = await self.api_key_limiter.get_api_key_status(
            api_key_id="key123",
            rate_limit_per_minute=60,
            rate_limit_per_hour=1000,
            rate_limit_per_day=10000
        )
        
        assert "minute" in status
        
        # Verify limits were passed correctly
        call_args = self.api_key_limiter.rate_limiter.get_rate_limit_status.call_args
        limits = call_args[1]["limits"]
        assert limits["minute"] == (60, 60)
    
    @pytest.mark.asyncio
    async def test_reset_api_key_limits(self):
        """Test resetting API key limits."""
        self.api_key_limiter.rate_limiter.reset_rate_limit = AsyncMock(return_value=True)
        
        result = await self.api_key_limiter.reset_api_key_limits("key123")
        
        assert result is True
        self.api_key_limiter.rate_limiter.reset_rate_limit.assert_called_once_with(
            identifier="key123",
            prefix="api_key_rate_limit"
        )


class TestIPRateLimiter:
    """Test cases for IPRateLimiter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.ip_limiter = IPRateLimiter()
        self.ip_limiter.rate_limiter = Mock()
    
    @pytest.mark.asyncio
    async def test_check_ip_limits_anonymous(self):
        """Test checking IP limits for anonymous user."""
        self.ip_limiter.rate_limiter.check_multiple_limits = AsyncMock(
            return_value=(True, {"minute": {"remaining": 5}})
        )
        
        with patch('src.core.rate_limiter.settings') as mock_settings:
            mock_settings.rate_limit_anonymous = 10
            
            is_allowed, info = await self.ip_limiter.check_ip_limits(
                ip_address="127.0.0.1",
                user_type="anonymous"
            )
            
            assert is_allowed is True
            
            # Verify limits for anonymous user
            call_args = self.ip_limiter.rate_limiter.check_multiple_limits.call_args
            limits = call_args[1]["limits"]
            assert limits["minute"] == (10, 60)
            assert limits["hour"] == (100, 3600)  # 10 * 10
    
    @pytest.mark.asyncio
    async def test_check_ip_limits_authenticated(self):
        """Test checking IP limits for authenticated user."""
        self.ip_limiter.rate_limiter.check_multiple_limits = AsyncMock(
            return_value=(True, {"minute": {"remaining": 50}})
        )
        
        with patch('src.core.rate_limiter.settings') as mock_settings:
            mock_settings.rate_limit_authenticated = 100
            
            is_allowed, info = await self.ip_limiter.check_ip_limits(
                ip_address="127.0.0.1",
                user_type="authenticated"
            )
            
            assert is_allowed is True
            
            # Verify limits for authenticated user
            call_args = self.ip_limiter.rate_limiter.check_multiple_limits.call_args
            limits = call_args[1]["limits"]
            assert limits["minute"] == (100, 60)
            assert limits["hour"] == (1000, 3600)  # 100 * 10
    
    @pytest.mark.asyncio
    async def test_check_ip_limits_premium(self):
        """Test checking IP limits for premium user."""
        self.ip_limiter.rate_limiter.check_multiple_limits = AsyncMock(
            return_value=(True, {"minute": {"remaining": 500}})
        )
        
        with patch('src.core.rate_limiter.settings') as mock_settings:
            mock_settings.rate_limit_premium = 1000
            
            is_allowed, info = await self.ip_limiter.check_ip_limits(
                ip_address="127.0.0.1",
                user_type="premium"
            )
            
            assert is_allowed is True
            
            # Verify limits for premium user
            call_args = self.ip_limiter.rate_limiter.check_multiple_limits.call_args
            limits = call_args[1]["limits"]
            assert limits["minute"] == (1000, 60)
            assert limits["hour"] == (10000, 3600)  # 1000 * 10
    
    @pytest.mark.asyncio
    async def test_check_ip_limits_unknown_user_type(self):
        """Test checking IP limits for unknown user type."""
        self.ip_limiter.rate_limiter.check_multiple_limits = AsyncMock(
            return_value=(True, {"minute": {"remaining": 5}})
        )
        
        is_allowed, info = await self.ip_limiter.check_ip_limits(
            ip_address="127.0.0.1",
            user_type="unknown"
        )
        
        assert is_allowed is True
        
        # Verify default limits
        call_args = self.ip_limiter.rate_limiter.check_multiple_limits.call_args
        limits = call_args[1]["limits"]
        assert limits["minute"] == (10, 60)  # Default anonymous limits
        assert limits["hour"] == (100, 3600)


class TestGlobalInstances:
    """Test cases for global rate limiter instances."""
    
    def test_global_instances_exist(self):
        """Test that global rate limiter instances exist."""
        assert api_key_rate_limiter is not None
        assert isinstance(api_key_rate_limiter, APIKeyRateLimiter)
        
        assert ip_rate_limiter is not None
        assert isinstance(ip_rate_limiter, IPRateLimiter)
        
        assert general_rate_limiter is not None
        assert isinstance(general_rate_limiter, RateLimiter)
    
    def test_api_key_rate_limiter_has_rate_limiter(self):
        """Test that API key rate limiter has a rate limiter instance."""
        assert hasattr(api_key_rate_limiter, 'rate_limiter')
        assert isinstance(api_key_rate_limiter.rate_limiter, RateLimiter)
    
    def test_ip_rate_limiter_has_rate_limiter(self):
        """Test that IP rate limiter has a rate limiter instance."""
        assert hasattr(ip_rate_limiter, 'rate_limiter')
        assert isinstance(ip_rate_limiter.rate_limiter, RateLimiter)


class TestRateLimiterIntegration:
    """Integration test cases for rate limiter."""
    
    @pytest.mark.asyncio
    async def test_sliding_window_behavior(self):
        """Test sliding window rate limiting behavior."""
        # This would require a real Redis instance for proper testing
        # For now, we'll test the logic with mocked Redis operations
        
        rate_limiter = RateLimiter()
        mock_cache = Mock()
        rate_limiter.cache = mock_cache
        
        # Simulate a series of requests over time
        current_time = time.time()
        
        # Mock pipeline for first request (0 existing requests)
        mock_pipeline1 = Mock()
        mock_pipeline1.execute = AsyncMock(return_value=[None, 0, None, None])
        
        # Mock pipeline for subsequent requests
        mock_pipeline2 = Mock()
        mock_pipeline2.execute = AsyncMock(return_value=[None, 5, None, None])
        
        mock_cache.client.pipeline.side_effect = [mock_pipeline1, mock_pipeline2]
        mock_cache.client.zrange.return_value = []
        
        # First request should be allowed
        is_allowed1, info1 = await rate_limiter.check_rate_limit(
            identifier="user123",
            limit=10,
            window_seconds=60
        )
        
        assert is_allowed1 is True
        assert info1["remaining"] == 10
        
        # Reset mock for second call
        mock_cache.client.pipeline.side_effect = [mock_pipeline2]
        
        # Subsequent request should also be allowed
        is_allowed2, info2 = await rate_limiter.check_rate_limit(
            identifier="user123",
            limit=10,
            window_seconds=60
        )
        
        assert is_allowed2 is True
        assert info2["remaining"] == 5
    
    @pytest.mark.asyncio
    async def test_rate_limit_window_expiration(self):
        """Test that rate limit windows expire correctly."""
        rate_limiter = RateLimiter()
        mock_cache = Mock()
        rate_limiter.cache = mock_cache
        
        # Mock expired entries being removed
        mock_pipeline = Mock()
        mock_pipeline.execute = AsyncMock(return_value=[None, 0, None, None])  # No current requests after cleanup
        
        mock_cache.client.pipeline.return_value = mock_pipeline
        mock_cache.client.zrange.return_value = []
        
        is_allowed, info = await rate_limiter.check_rate_limit(
            identifier="user123",
            limit=10,
            window_seconds=60
        )
        
        assert is_allowed is True
        assert info["current_count"] == 0  # All expired requests were cleaned up
        
        # Verify that zremrangebyscore was called to remove expired entries
        mock_pipeline.zremrangebyscore.assert_called_once()