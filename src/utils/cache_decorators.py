"""Caching decorators for lit_law411-agent."""

import asyncio
import hashlib
import json
from functools import wraps
from typing import Any, Callable, Optional, Union

from src.core.logging import get_logger
from src.db.redis_client import get_cache

logger = get_logger(__name__)


def cache_key_from_args(*args, **kwargs) -> str:
    """Generate cache key from function arguments."""
    # Create a string representation of arguments
    args_str = json.dumps(args, default=str, sort_keys=True)
    kwargs_str = json.dumps(kwargs, default=str, sort_keys=True)
    combined = f"{args_str}:{kwargs_str}"
    
    # Create hash to avoid key length issues
    return hashlib.md5(combined.encode()).hexdigest()


def cached(
    ttl: int = 300,
    key_prefix: Optional[str] = None,
    key_func: Optional[Callable] = None,
    serialize: bool = True,
    skip_cache: bool = False,
) -> Callable:
    """
    Cache decorator for async functions.
    
    Args:
        ttl: Time to live in seconds (default: 5 minutes)
        key_prefix: Custom prefix for cache key
        key_func: Custom function to generate cache key
        serialize: Whether to serialize/deserialize cached values
        skip_cache: Skip caching entirely (useful for debugging)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if skip_cache:
                return await func(*args, **kwargs)
            
            try:
                cache_client = await get_cache()
                
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    func_name = f"{func.__module__}.{func.__qualname__}"
                    args_key = cache_key_from_args(*args, **kwargs)
                    cache_key = f"{key_prefix or func_name}:{args_key}"
                
                # Try to get from cache
                cached_result = await cache_client.get(
                    cache_key, 
                    deserialize=serialize
                )
                
                if cached_result is not None:
                    logger.debug("Cache hit", cache_key=cache_key, function=func.__name__)
                    return cached_result
                
                # Cache miss - execute function
                logger.debug("Cache miss", cache_key=cache_key, function=func.__name__)
                result = await func(*args, **kwargs)
                
                # Store in cache
                await cache_client.set(
                    cache_key, 
                    result, 
                    ttl=ttl,
                    serialize=serialize
                )
                
                return result
                
            except Exception as e:
                logger.error(
                    "Cache operation failed, executing function directly",
                    function=func.__name__,
                    error=str(e)
                )
                # Fallback to direct function execution
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def cache_invalidate(
    key_pattern: str,
    key_func: Optional[Callable] = None,
) -> Callable:
    """
    Decorator to invalidate cache keys after function execution.
    
    Args:
        key_pattern: Pattern to match cache keys for invalidation
        key_func: Function to generate specific key to invalidate
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            result = await func(*args, **kwargs)
            
            try:
                cache_client = await get_cache()
                
                if key_func:
                    # Invalidate specific key
                    cache_key = key_func(*args, **kwargs)
                    await cache_client.delete(cache_key)
                    logger.debug("Cache key invalidated", cache_key=cache_key)
                else:
                    # Invalidate pattern
                    cleared_count = await cache_client.clear_pattern(key_pattern)
                    logger.debug("Cache pattern cleared", pattern=key_pattern, count=cleared_count)
                
            except Exception as e:
                logger.error(
                    "Cache invalidation failed",
                    function=func.__name__,
                    pattern=key_pattern,
                    error=str(e)
                )
            
            return result
        
        return wrapper
    return decorator


def rate_limit(
    limit: int,
    window: int = 60,
    key_func: Optional[Callable] = None,
    identifier: str = "default",
) -> Callable:
    """
    Rate limiting decorator using Redis.
    
    Args:
        limit: Maximum number of calls allowed
        window: Time window in seconds
        key_func: Function to generate rate limit key
        identifier: Default identifier for rate limiting
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                cache_client = await get_cache()
                
                # Generate rate limit key
                if key_func:
                    rate_key = key_func(*args, **kwargs)
                else:
                    rate_key = f"rate_limit:{identifier}:{func.__name__}"
                
                # Check current count
                current_count = await cache_client.get(rate_key, default=0, deserialize=False)
                current_count = int(current_count) if current_count else 0
                
                if current_count >= limit:
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded. {limit} calls per {window} seconds allowed."
                    )
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Increment counter
                new_count = await cache_client.increment(rate_key)
                if new_count == 1:
                    # Set expiration on first increment
                    await cache_client.expire(rate_key, window)
                
                logger.debug(
                    "Rate limit check",
                    key=rate_key,
                    count=new_count,
                    limit=limit,
                    window=window
                )
                
                return result
                
            except Exception as e:
                if "Rate limit exceeded" in str(e):
                    raise
                logger.error(
                    "Rate limiting failed, allowing request",
                    function=func.__name__,
                    error=str(e)
                )
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def memoize(
    ttl: int = 3600,
    max_size: int = 128,
) -> Callable:
    """
    Simple memoization decorator for sync functions with Redis backend.
    
    Args:
        ttl: Time to live in seconds
        max_size: Maximum number of cached results (not enforced in Redis)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # For sync functions, we need to handle async cache operations
            async def _async_wrapper():
                cache_client = await get_cache()
                
                func_name = f"{func.__module__}.{func.__qualname__}"
                args_key = cache_key_from_args(*args, **kwargs)
                cache_key = f"memo:{func_name}:{args_key}"
                
                # Try cache first
                cached_result = await cache_client.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Cache result
                await cache_client.set(cache_key, result, ttl=ttl)
                return result
            
            # Run async wrapper in event loop
            try:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(_async_wrapper())
            except RuntimeError:
                # No event loop, execute function directly
                logger.warning(
                    "No event loop available for memoization, executing directly",
                    function=func.__name__
                )
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Specific cache decorators for common use cases
def cache_content(ttl: int = 1800) -> Callable:
    """Cache content data for 30 minutes."""
    return cached(ttl=ttl, key_prefix="content")


def cache_user(ttl: int = 900) -> Callable:
    """Cache user data for 15 minutes."""
    return cached(ttl=ttl, key_prefix="user")


def cache_search(ttl: int = 600) -> Callable:
    """Cache search results for 10 minutes."""
    return cached(ttl=ttl, key_prefix="search")


def cache_embeddings(ttl: int = 86400) -> Callable:
    """Cache embeddings for 24 hours."""
    return cached(ttl=ttl, key_prefix="embeddings")


def cache_transcripts(ttl: int = 3600) -> Callable:
    """Cache transcripts for 1 hour."""
    return cached(ttl=ttl, key_prefix="transcripts")