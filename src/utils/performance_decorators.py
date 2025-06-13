"""Performance monitoring decorators for lit_law411-agent.

This module provides decorators for automatic performance monitoring
and metrics collection for functions and methods.
"""

import asyncio
import functools
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from ..core.monitoring import (
    DATABASE_QUERIES,
    DATABASE_QUERY_DURATION,
    CACHE_OPERATIONS
)
from ..core.logging import get_logger, log_performance

F = TypeVar("F", bound=Callable[..., Any])


def monitor_performance(
    operation_name: str = None,
    include_args: bool = False,
    track_memory: bool = False,
    slow_threshold_seconds: float = 1.0
) -> Callable[[F], F]:
    """
    Decorator to monitor function performance.
    
    Args:
        operation_name: Name for the operation (uses function name if None)
        include_args: Whether to include function arguments in logs
        track_memory: Whether to track memory usage
        slow_threshold_seconds: Threshold for logging slow operations
        
    Returns:
        Decorated function with performance monitoring
    """
    def decorator(func: F) -> F:
        logger = get_logger(func.__module__)
        op_name = operation_name or f"{func.__module__}.{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                memory_before = None
                
                if track_memory:
                    try:
                        import psutil
                        process = psutil.Process()
                        memory_before = process.memory_info().rss / 1024 / 1024  # MB
                    except ImportError:
                        logger.warning("psutil not available for memory tracking")
                
                # Log function start with arguments if requested
                log_data = {"operation": op_name}
                if include_args and args:
                    log_data["args_count"] = len(args)
                if include_args and kwargs:
                    log_data["kwargs_keys"] = list(kwargs.keys())
                
                logger.debug("Performance monitoring started", **log_data)
                
                try:
                    result = await func(*args, **kwargs)
                    
                    # Calculate performance metrics
                    duration = time.time() - start_time
                    
                    performance_data = {
                        "operation": op_name,
                        "duration_seconds": duration,
                        "success": True
                    }
                    
                    if track_memory and memory_before is not None:
                        try:
                            import psutil
                            process = psutil.Process()
                            memory_after = process.memory_info().rss / 1024 / 1024  # MB
                            memory_delta = memory_after - memory_before
                            performance_data.update({
                                "memory_before_mb": memory_before,
                                "memory_after_mb": memory_after,
                                "memory_delta_mb": memory_delta
                            })
                        except ImportError:
                            pass
                    
                    # Log performance data  
                    perf_kwargs = {k: v for k, v in performance_data.items() if k not in ['operation', 'duration_seconds']}
                    log_performance(op_name, duration, **perf_kwargs)
                    
                    # Log warning for slow operations
                    if duration > slow_threshold_seconds:
                        logger.warning(
                            f"Slow operation detected: {op_name}",
                            **performance_data
                        )
                    else:
                        logger.debug(
                            f"Operation completed: {op_name}",
                            **performance_data
                        )
                    
                    return result
                    
                except Exception as exc:
                    duration = time.time() - start_time
                    
                    error_data = {
                        "operation": op_name,
                        "duration_seconds": duration,
                        "success": False,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)
                    }
                    
                    logger.error(f"Operation failed: {op_name}", **error_data)
                    error_kwargs = {k: v for k, v in error_data.items() if k not in ['operation', 'duration_seconds']}
                    log_performance(op_name, duration, **error_kwargs)
                    
                    raise
            
            return async_wrapper
            
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                memory_before = None
                
                if track_memory:
                    try:
                        import psutil
                        process = psutil.Process()
                        memory_before = process.memory_info().rss / 1024 / 1024  # MB
                    except ImportError:
                        logger.warning("psutil not available for memory tracking")
                
                # Log function start with arguments if requested
                log_data = {"operation": op_name}
                if include_args and args:
                    log_data["args_count"] = len(args)
                if include_args and kwargs:
                    log_data["kwargs_keys"] = list(kwargs.keys())
                
                logger.debug("Performance monitoring started", **log_data)
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Calculate performance metrics
                    duration = time.time() - start_time
                    
                    performance_data = {
                        "operation": op_name,
                        "duration_seconds": duration,
                        "success": True
                    }
                    
                    if track_memory and memory_before is not None:
                        try:
                            import psutil
                            process = psutil.Process()
                            memory_after = process.memory_info().rss / 1024 / 1024  # MB
                            memory_delta = memory_after - memory_before
                            performance_data.update({
                                "memory_before_mb": memory_before,
                                "memory_after_mb": memory_after,
                                "memory_delta_mb": memory_delta
                            })
                        except ImportError:
                            pass
                    
                    # Log performance data  
                    perf_kwargs = {k: v for k, v in performance_data.items() if k not in ['operation', 'duration_seconds']}
                    log_performance(op_name, duration, **perf_kwargs)
                    
                    # Log warning for slow operations
                    if duration > slow_threshold_seconds:
                        logger.warning(
                            f"Slow operation detected: {op_name}",
                            **performance_data
                        )
                    else:
                        logger.debug(
                            f"Operation completed: {op_name}",
                            **performance_data
                        )
                    
                    return result
                    
                except Exception as exc:
                    duration = time.time() - start_time
                    
                    error_data = {
                        "operation": op_name,
                        "duration_seconds": duration,
                        "success": False,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)
                    }
                    
                    logger.error(f"Operation failed: {op_name}", **error_data)
                    error_kwargs = {k: v for k, v in error_data.items() if k not in ['operation', 'duration_seconds']}
                    log_performance(op_name, duration, **error_kwargs)
                    
                    raise
            
            return sync_wrapper
    
    return decorator


def monitor_database_operation(
    query_type: str = "unknown",
    track_rows: bool = True
) -> Callable[[F], F]:
    """
    Decorator to monitor database operations.
    
    Args:
        query_type: Type of database operation (select, insert, update, delete)
        track_rows: Whether to track affected row count
        
    Returns:
        Decorated function with database operation monitoring
    """
    def decorator(func: F) -> F:
        logger = get_logger(func.__module__)
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                
                logger.debug(
                    "Database operation started",
                    operation=func.__name__,
                    query_type=query_type
                )
                
                try:
                    result = await func(*args, **kwargs)
                    
                    duration = time.time() - start_time
                    
                    # Track metrics
                    DATABASE_QUERIES.labels(
                        query_type=query_type,
                        status="success"
                    ).inc()
                    
                    DATABASE_QUERY_DURATION.labels(
                        query_type=query_type
                    ).observe(duration)
                    
                    # Log performance
                    log_data = {
                        "operation": func.__name__,
                        "query_type": query_type,
                        "duration_seconds": duration,
                        "success": True
                    }
                    
                    if track_rows and result:
                        # Try to extract row count from result
                        if hasattr(result, "rowcount"):
                            log_data["rows_affected"] = result.rowcount
                        elif isinstance(result, (list, tuple)):
                            log_data["rows_returned"] = len(result)
                    
                    logger.info("Database operation completed", **log_data)
                    db_kwargs = {k: v for k, v in log_data.items() if k not in ['operation', 'duration_seconds']}
                    log_performance(f"db_{func.__name__}", duration, **db_kwargs)
                    
                    return result
                    
                except Exception as exc:
                    duration = time.time() - start_time
                    
                    # Track failed operation
                    DATABASE_QUERIES.labels(
                        query_type=query_type,
                        status="error"
                    ).inc()
                    
                    DATABASE_QUERY_DURATION.labels(
                        query_type=query_type
                    ).observe(duration)
                    
                    error_data = {
                        "operation": func.__name__,
                        "query_type": query_type,
                        "duration_seconds": duration,
                        "success": False,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)
                    }
                    
                    logger.error("Database operation failed", **error_data)
                    db_error_kwargs = {k: v for k, v in error_data.items() if k not in ['operation', 'duration_seconds']}
                    log_performance(f"db_{func.__name__}", duration, **db_error_kwargs)
                    
                    raise
            
            return async_wrapper
            
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                
                logger.debug(
                    "Database operation started",
                    operation=func.__name__,
                    query_type=query_type
                )
                
                try:
                    result = func(*args, **kwargs)
                    
                    duration = time.time() - start_time
                    
                    # Track metrics
                    DATABASE_QUERIES.labels(
                        query_type=query_type,
                        status="success"
                    ).inc()
                    
                    DATABASE_QUERY_DURATION.labels(
                        query_type=query_type
                    ).observe(duration)
                    
                    # Log performance
                    log_data = {
                        "operation": func.__name__,
                        "query_type": query_type,
                        "duration_seconds": duration,
                        "success": True
                    }
                    
                    if track_rows and result:
                        # Try to extract row count from result
                        if hasattr(result, "rowcount"):
                            log_data["rows_affected"] = result.rowcount
                        elif isinstance(result, (list, tuple)):
                            log_data["rows_returned"] = len(result)
                    
                    logger.info("Database operation completed", **log_data)
                    db_kwargs = {k: v for k, v in log_data.items() if k not in ['operation', 'duration_seconds']}
                    log_performance(f"db_{func.__name__}", duration, **db_kwargs)
                    
                    return result
                    
                except Exception as exc:
                    duration = time.time() - start_time
                    
                    # Track failed operation
                    DATABASE_QUERIES.labels(
                        query_type=query_type,
                        status="error"
                    ).inc()
                    
                    DATABASE_QUERY_DURATION.labels(
                        query_type=query_type
                    ).observe(duration)
                    
                    error_data = {
                        "operation": func.__name__,
                        "query_type": query_type,
                        "duration_seconds": duration,
                        "success": False,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)
                    }
                    
                    logger.error("Database operation failed", **error_data)
                    db_error_kwargs = {k: v for k, v in error_data.items() if k not in ['operation', 'duration_seconds']}
                    log_performance(f"db_{func.__name__}", duration, **db_error_kwargs)
                    
                    raise
            
            return sync_wrapper
    
    return decorator


def monitor_cache_operation(
    operation: str = "unknown"
) -> Callable[[F], F]:
    """
    Decorator to monitor cache operations.
    
    Args:
        operation: Type of cache operation (get, set, delete, clear)
        
    Returns:
        Decorated function with cache operation monitoring
    """
    def decorator(func: F) -> F:
        logger = get_logger(func.__module__)
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                
                try:
                    result = await func(*args, **kwargs)
                    
                    duration = time.time() - start_time
                    
                    # Track successful cache operation
                    CACHE_OPERATIONS.labels(
                        operation=operation,
                        status="success"
                    ).inc()
                    
                    logger.debug(
                        "Cache operation completed",
                        operation=operation,
                        function=func.__name__,
                        duration_seconds=duration
                    )
                    
                    return result
                    
                except Exception as exc:
                    duration = time.time() - start_time
                    
                    # Track failed cache operation
                    CACHE_OPERATIONS.labels(
                        operation=operation,
                        status="error"
                    ).inc()
                    
                    logger.error(
                        "Cache operation failed",
                        operation=operation,
                        function=func.__name__,
                        duration_seconds=duration,
                        error_type=type(exc).__name__,
                        error_message=str(exc)
                    )
                    
                    raise
            
            return async_wrapper
            
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    
                    duration = time.time() - start_time
                    
                    # Track successful cache operation
                    CACHE_OPERATIONS.labels(
                        operation=operation,
                        status="success"
                    ).inc()
                    
                    logger.debug(
                        "Cache operation completed",
                        operation=operation,
                        function=func.__name__,
                        duration_seconds=duration
                    )
                    
                    return result
                    
                except Exception as exc:
                    duration = time.time() - start_time
                    
                    # Track failed cache operation
                    CACHE_OPERATIONS.labels(
                        operation=operation,
                        status="error"
                    ).inc()
                    
                    logger.error(
                        "Cache operation failed",
                        operation=operation,
                        function=func.__name__,
                        duration_seconds=duration,
                        error_type=type(exc).__name__,
                        error_message=str(exc)
                    )
                    
                    raise
            
            return sync_wrapper
    
    return decorator


# Export decorators
__all__ = [
    "monitor_performance",
    "monitor_database_operation", 
    "monitor_cache_operation",
]