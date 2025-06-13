"""Redis-based rate limiting system for API keys and users."""

import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from ..db.redis_client import cache
from .config import get_settings
from .logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class RateLimitExceeded(Exception):
    """Rate limit exceeded exception."""
    
    def __init__(self, message: str, retry_after: int, limit_type: str):
        super().__init__(message)
        self.retry_after = retry_after
        self.limit_type = limit_type


class RateLimiter:
    """Redis-based rate limiter using sliding window algorithm."""
    
    def __init__(self):
        self.cache = cache
    
    async def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window_seconds: int,
        prefix: str = "rate_limit"
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Check if identifier is within rate limit using sliding window.
        
        Args:
            identifier: Unique identifier (API key, user ID, IP)
            limit: Maximum number of requests allowed
            window_seconds: Time window in seconds
            prefix: Redis key prefix
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        now = time.time()
        window_start = now - window_seconds
        
        # Redis key for this identifier and window
        redis_key = f"{prefix}:{identifier}:{window_seconds}"
        
        try:
            # Use Redis pipeline for atomic operations
            pipeline = self.cache.client.pipeline()
            
            # Remove expired entries
            pipeline.zremrangebyscore(redis_key, 0, window_start)
            
            # Count current requests in window
            pipeline.zcard(redis_key)
            
            # Add current request with timestamp as score
            pipeline.zadd(redis_key, {str(now): now})
            
            # Set expiration for cleanup
            pipeline.expire(redis_key, window_seconds + 1)
            
            results = await pipeline.execute()
            current_count = results[1]  # Count after removing expired
            
            # Check if limit exceeded (subtract 1 because we just added current request)
            is_allowed = current_count <= limit
            
            if not is_allowed:
                # Remove the request we just added since it's not allowed
                await self.cache.client.zrem(redis_key, str(now))
                current_count -= 1
            
            # Calculate reset time
            reset_time = datetime.fromtimestamp(now + window_seconds, tz=timezone.utc)
            
            # Get oldest request timestamp for more accurate reset calculation
            oldest_requests = await self.cache.client.zrange(
                redis_key, 0, 0, withscores=True
            )
            
            if oldest_requests:
                oldest_timestamp = oldest_requests[0][1]
                accurate_reset_time = datetime.fromtimestamp(
                    oldest_timestamp + window_seconds, tz=timezone.utc
                )
                reset_time = min(reset_time, accurate_reset_time)
            
            rate_limit_info = {
                "limit": limit,
                "remaining": max(0, limit - current_count),
                "reset_time": reset_time,
                "retry_after": int(reset_time.timestamp() - now) if not is_allowed else 0,
                "window_seconds": window_seconds,
                "current_count": current_count,
            }
            
            return is_allowed, rate_limit_info
            
        except Exception as e:
            logger.error(f"Rate limit check error for {identifier}: {str(e)}")
            # On error, allow the request but log the issue
            return True, {
                "limit": limit,
                "remaining": limit,
                "reset_time": datetime.now(timezone.utc) + timedelta(seconds=window_seconds),
                "retry_after": 0,
                "window_seconds": window_seconds,
                "current_count": 0,
                "error": str(e),
            }
    
    async def check_multiple_limits(
        self,
        identifier: str,
        limits: Dict[str, Tuple[int, int]],
        prefix: str = "rate_limit"
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Check multiple rate limits for an identifier.
        
        Args:
            identifier: Unique identifier
            limits: Dict of {period_name: (limit, window_seconds)}
            prefix: Redis key prefix
            
        Returns:
            Tuple of (all_allowed, combined_rate_limit_info)
            
        Raises:
            RateLimitExceeded: If any limit is exceeded
        """
        all_allowed = True
        combined_info = {}
        max_retry_after = 0
        failed_limit = None
        
        for period_name, (limit, window_seconds) in limits.items():
            is_allowed, info = await self.check_rate_limit(
                identifier=identifier,
                limit=limit,
                window_seconds=window_seconds,
                prefix=f"{prefix}:{period_name}"
            )
            
            combined_info[period_name] = info
            
            if not is_allowed:
                all_allowed = False
                if info["retry_after"] > max_retry_after:
                    max_retry_after = info["retry_after"]
                    failed_limit = period_name
        
        if not all_allowed:
            error_msg = f"Rate limit exceeded for {failed_limit}"
            raise RateLimitExceeded(error_msg, max_retry_after, failed_limit)
        
        return all_allowed, combined_info
    
    async def reset_rate_limit(
        self,
        identifier: str,
        window_seconds: Optional[int] = None,
        prefix: str = "rate_limit"
    ) -> bool:
        """
        Reset rate limit for an identifier.
        
        Args:
            identifier: Unique identifier
            window_seconds: Specific window to reset (None = all windows)
            prefix: Redis key prefix
            
        Returns:
            True if reset successful, False otherwise
        """
        try:
            if window_seconds:
                # Reset specific window
                redis_key = f"{prefix}:*:{identifier}:{window_seconds}"
                deleted = await self.cache.clear_pattern(redis_key)
                logger.info(f"Reset rate limit for {identifier} ({window_seconds}s): {deleted} keys")
            else:
                # Reset all windows for identifier
                redis_key = f"{prefix}:*:{identifier}:*"
                deleted = await self.cache.clear_pattern(redis_key)
                logger.info(f"Reset all rate limits for {identifier}: {deleted} keys")
            
            return True
            
        except Exception as e:
            logger.error(f"Error resetting rate limit for {identifier}: {str(e)}")
            return False
    
    async def get_rate_limit_status(
        self,
        identifier: str,
        limits: Dict[str, Tuple[int, int]],
        prefix: str = "rate_limit"
    ) -> Dict[str, any]:
        """
        Get current rate limit status without incrementing counters.
        
        Args:
            identifier: Unique identifier
            limits: Dict of {period_name: (limit, window_seconds)}
            prefix: Redis key prefix
            
        Returns:
            Dict with rate limit status for each period
        """
        status = {}
        now = time.time()
        
        for period_name, (limit, window_seconds) in limits.items():
            window_start = now - window_seconds
            redis_key = f"{prefix}:{period_name}:{identifier}:{window_seconds}"
            
            try:
                # Count current requests without modifying
                await self.cache.client.zremrangebyscore(redis_key, 0, window_start)
                current_count = await self.cache.client.zcard(redis_key)
                
                # Get oldest request for accurate reset time
                oldest_requests = await self.cache.client.zrange(
                    redis_key, 0, 0, withscores=True
                )
                
                if oldest_requests:
                    oldest_timestamp = oldest_requests[0][1]
                    reset_time = datetime.fromtimestamp(
                        oldest_timestamp + window_seconds, tz=timezone.utc
                    )
                else:
                    reset_time = datetime.fromtimestamp(
                        now + window_seconds, tz=timezone.utc
                    )
                
                status[period_name] = {
                    "limit": limit,
                    "current": current_count,
                    "remaining": max(0, limit - current_count),
                    "reset_time": reset_time,
                    "window_seconds": window_seconds,
                    "is_limited": current_count >= limit,
                }
                
            except Exception as e:
                logger.error(f"Error getting rate limit status for {identifier} ({period_name}): {str(e)}")
                status[period_name] = {
                    "limit": limit,
                    "current": 0,
                    "remaining": limit,
                    "reset_time": datetime.now(timezone.utc) + timedelta(seconds=window_seconds),
                    "window_seconds": window_seconds,
                    "is_limited": False,
                    "error": str(e),
                }
        
        return status


class APIKeyRateLimiter:
    """Specialized rate limiter for API keys."""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
    
    async def check_api_key_limits(
        self,
        api_key_id: str,
        rate_limit_per_minute: int,
        rate_limit_per_hour: int,
        rate_limit_per_day: int
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Check API key rate limits across all time windows.
        
        Args:
            api_key_id: API key identifier
            rate_limit_per_minute: Requests per minute limit
            rate_limit_per_hour: Requests per hour limit
            rate_limit_per_day: Requests per day limit
            
        Returns:
            Tuple of (all_allowed, rate_limit_info)
            
        Raises:
            RateLimitExceeded: If any limit is exceeded
        """
        limits = {
            "minute": (rate_limit_per_minute, 60),
            "hour": (rate_limit_per_hour, 3600),
            "day": (rate_limit_per_day, 86400),
        }
        
        return await self.rate_limiter.check_multiple_limits(
            identifier=api_key_id,
            limits=limits,
            prefix="api_key_rate_limit"
        )
    
    async def get_api_key_status(
        self,
        api_key_id: str,
        rate_limit_per_minute: int,
        rate_limit_per_hour: int,
        rate_limit_per_day: int
    ) -> Dict[str, any]:
        """
        Get API key rate limit status.
        
        Args:
            api_key_id: API key identifier
            rate_limit_per_minute: Requests per minute limit
            rate_limit_per_hour: Requests per hour limit
            rate_limit_per_day: Requests per day limit
            
        Returns:
            Dict with rate limit status
        """
        limits = {
            "minute": (rate_limit_per_minute, 60),
            "hour": (rate_limit_per_hour, 3600),
            "day": (rate_limit_per_day, 86400),
        }
        
        return await self.rate_limiter.get_rate_limit_status(
            identifier=api_key_id,
            limits=limits,
            prefix="api_key_rate_limit"
        )
    
    async def reset_api_key_limits(self, api_key_id: str) -> bool:
        """
        Reset all rate limits for an API key.
        
        Args:
            api_key_id: API key identifier
            
        Returns:
            True if reset successful, False otherwise
        """
        return await self.rate_limiter.reset_rate_limit(
            identifier=api_key_id,
            prefix="api_key_rate_limit"
        )


class IPRateLimiter:
    """Specialized rate limiter for IP addresses."""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
    
    async def check_ip_limits(
        self,
        ip_address: str,
        user_type: str = "anonymous"
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Check IP-based rate limits.
        
        Args:
            ip_address: Client IP address
            user_type: Type of user (anonymous, authenticated, premium)
            
        Returns:
            Tuple of (allowed, rate_limit_info)
            
        Raises:
            RateLimitExceeded: If limit exceeded
        """
        # Define limits based on user type
        if user_type == "anonymous":
            limits = {
                "minute": (settings.rate_limit_anonymous, 60),
                "hour": (settings.rate_limit_anonymous * 10, 3600),
            }
        elif user_type == "authenticated":
            limits = {
                "minute": (settings.rate_limit_authenticated, 60),
                "hour": (settings.rate_limit_authenticated * 10, 3600),
            }
        elif user_type == "premium":
            limits = {
                "minute": (settings.rate_limit_premium, 60),
                "hour": (settings.rate_limit_premium * 10, 3600),
            }
        else:
            # Default to anonymous limits
            limits = {
                "minute": (10, 60),
                "hour": (100, 3600),
            }
        
        return await self.rate_limiter.check_multiple_limits(
            identifier=ip_address,
            limits=limits,
            prefix=f"ip_rate_limit_{user_type}"
        )


# Global rate limiter instances
api_key_rate_limiter = APIKeyRateLimiter()
ip_rate_limiter = IPRateLimiter()
general_rate_limiter = RateLimiter()