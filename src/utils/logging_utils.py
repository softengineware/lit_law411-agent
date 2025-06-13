"""Logging utilities and decorators for lit_law411-agent.

This module provides utility functions and decorators for enhanced logging.
"""

import asyncio
import functools
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from ..core.logging import get_logger, log_exception, log_performance

F = TypeVar("F", bound=Callable[..., Any])


def log_function_calls(
    logger_name: str = None,
    include_args: bool = True,
    include_result: bool = False,
    exclude_args: list = None,
) -> Callable[[F], F]:
    """Decorator to log function calls.
    
    Args:
        logger_name: Logger name (uses function module if None)
        include_args: Whether to log function arguments
        include_result: Whether to log function result
        exclude_args: List of argument names to exclude from logging
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        logger = get_logger(logger_name or func.__module__)
        exclude_args_set = set(exclude_args or [])
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                
                # Prepare arguments for logging
                log_kwargs = {}
                if include_args:
                    # Filter out excluded arguments
                    filtered_kwargs = {
                        k: v for k, v in kwargs.items() 
                        if k not in exclude_args_set
                    }
                    log_kwargs["arguments"] = {
                        "args": args[:3] if len(args) <= 3 else f"{args[:3]}... ({len(args)} total)",
                        "kwargs": filtered_kwargs,
                    }
                
                logger.info(
                    "Function called",
                    function=func.__name__,
                    **log_kwargs,
                )
                
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    log_kwargs = {"duration_seconds": duration}
                    if include_result:
                        log_kwargs["result"] = str(result)[:200]  # Truncate long results
                    
                    logger.info(
                        "Function completed",
                        function=func.__name__,
                        **log_kwargs,
                    )
                    
                    log_performance(
                        operation=f"function_{func.__name__}",
                        duration=duration,
                    )
                    
                    return result
                    
                except Exception as exc:
                    duration = time.time() - start_time
                    logger.error(
                        "Function failed",
                        function=func.__name__,
                        duration_seconds=duration,
                        exception_type=type(exc).__name__,
                        exception_message=str(exc),
                    )
                    log_exception(exc, {"function": func.__name__})
                    raise
            
            return async_wrapper
        
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                
                # Prepare arguments for logging
                log_kwargs = {}
                if include_args:
                    # Filter out excluded arguments
                    filtered_kwargs = {
                        k: v for k, v in kwargs.items() 
                        if k not in exclude_args_set
                    }
                    log_kwargs["arguments"] = {
                        "args": args[:3] if len(args) <= 3 else f"{args[:3]}... ({len(args)} total)",
                        "kwargs": filtered_kwargs,
                    }
                
                logger.info(
                    "Function called",
                    function=func.__name__,
                    **log_kwargs,
                )
                
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    log_kwargs = {"duration_seconds": duration}
                    if include_result:
                        log_kwargs["result"] = str(result)[:200]  # Truncate long results
                    
                    logger.info(
                        "Function completed",
                        function=func.__name__,
                        **log_kwargs,
                    )
                    
                    log_performance(
                        operation=f"function_{func.__name__}",
                        duration=duration,
                    )
                    
                    return result
                    
                except Exception as exc:
                    duration = time.time() - start_time
                    logger.error(
                        "Function failed",
                        function=func.__name__,
                        duration_seconds=duration,
                        exception_type=type(exc).__name__,
                        exception_message=str(exc),
                    )
                    log_exception(exc, {"function": func.__name__})
                    raise
            
            return sync_wrapper
    
    return decorator


def log_method_calls(
    logger_name: str = None,
    include_args: bool = True,
    include_result: bool = False,
    exclude_args: list = None,
) -> Callable[[F], F]:
    """Decorator to log method calls (excludes 'self' argument).
    
    Args:
        logger_name: Logger name (uses method class if None)
        include_args: Whether to log method arguments
        include_result: Whether to log method result
        exclude_args: List of argument names to exclude from logging
        
    Returns:
        Decorated method
    """
    def decorator(func: F) -> F:
        exclude_args_set = set(exclude_args or [])
        exclude_args_set.add("self")  # Always exclude self
        
        return log_function_calls(
            logger_name=logger_name,
            include_args=include_args,
            include_result=include_result,
            exclude_args=list(exclude_args_set),
        )(func)
    
    return decorator


class LogContext:
    """Context manager for adding structured context to logs."""
    
    def __init__(self, logger_name: str = None, **context):
        """Initialize log context.
        
        Args:
            logger_name: Logger name
            **context: Context key-value pairs
        """
        self.logger = get_logger(logger_name)
        self.context = context
        self.bound_logger = None
    
    def __enter__(self):
        """Enter context and bind logger with context."""
        self.bound_logger = self.logger.bind(**self.context)
        return self.bound_logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        if exc_type:
            self.bound_logger.error(
                "Exception in log context",
                exception_type=exc_type.__name__,
                exception_message=str(exc_val),
                exc_info=True,
            )


def time_operation(operation_name: str, logger_name: str = None):
    """Context manager for timing operations.
    
    Args:
        operation_name: Name of the operation being timed
        logger_name: Logger name
    """
    class TimeOperation:
        def __init__(self):
            self.logger = get_logger(logger_name)
            self.start_time = None
            self.operation_name = operation_name
        
        def __enter__(self):
            self.start_time = time.time()
            self.logger.info(f"Starting {self.operation_name}")
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            duration = time.time() - self.start_time
            
            if exc_type:
                self.logger.error(
                    f"{self.operation_name} failed",
                    duration_seconds=duration,
                    exception_type=exc_type.__name__,
                    exception_message=str(exc_val),
                )
            else:
                self.logger.info(
                    f"{self.operation_name} completed",
                    duration_seconds=duration,
                )
            
            log_performance(self.operation_name, duration)
    
    return TimeOperation()


def log_database_operations(
    logger_name: str = None,
    log_queries: bool = False,
) -> Callable[[F], F]:
    """Decorator to log database operations.
    
    Args:
        logger_name: Logger name
        log_queries: Whether to log SQL queries (development only)
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        logger = get_logger(logger_name or func.__module__)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            logger.info(
                "Database operation started",
                operation=func.__name__,
            )
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Count affected rows if possible
                affected_rows = None
                if hasattr(result, "rowcount"):
                    affected_rows = result.rowcount
                elif isinstance(result, (list, tuple)):
                    affected_rows = len(result)
                
                log_kwargs = {
                    "duration_seconds": duration,
                }
                if affected_rows is not None:
                    log_kwargs["affected_rows"] = affected_rows
                
                logger.info(
                    "Database operation completed",
                    operation=func.__name__,
                    **log_kwargs,
                )
                
                log_performance(
                    operation=f"db_{func.__name__}",
                    duration=duration,
                    affected_rows=affected_rows,
                )
                
                return result
                
            except Exception as exc:
                duration = time.time() - start_time
                logger.error(
                    "Database operation failed",
                    operation=func.__name__,
                    duration_seconds=duration,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                )
                log_exception(exc, {"operation": f"db_{func.__name__}"})
                raise
        
        return wrapper
    
    return decorator


def sanitize_for_logging(data: Any, max_length: int = 1000) -> str:
    """Sanitize data for safe logging.
    
    Args:
        data: Data to sanitize
        max_length: Maximum length of returned string
        
    Returns:
        Sanitized string representation
    """
    if data is None:
        return "None"
    
    # Convert to string
    if isinstance(data, (dict, list, tuple)):
        data_str = str(data)
    else:
        data_str = repr(data)
    
    # Truncate if too long
    if len(data_str) > max_length:
        data_str = data_str[:max_length] + "..."
    
    # Remove sensitive patterns (replace both keys and values)
    sensitive_patterns = [
        ("password", "[PASSWORD]"),
        ("secret", "[SECRET]"),
        ("token", "[TOKEN]"),
        ("api_key", "[API_KEY]"),
        ("authorization", "[AUTH]"),
    ]
    
    data_str_lower = data_str.lower()
    for pattern, replacement in sensitive_patterns:
        if pattern in data_str_lower:
            # Replace the pattern in the original string (case-insensitive)
            import re
            # Replace both keys and values that contain the pattern
            data_str = re.sub(
                rf'({re.escape(pattern)}[^,\}}\]]*)', 
                replacement, 
                data_str, 
                flags=re.IGNORECASE
            )
    
    return data_str


# Export utilities
__all__ = [
    "log_function_calls",
    "log_method_calls",
    "LogContext",
    "time_operation",
    "log_database_operations",
    "sanitize_for_logging",
]