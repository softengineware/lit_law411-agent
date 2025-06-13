"""Structured logging configuration for lit_law411-agent.

This module provides centralized logging configuration using structlog
with JSON formatting for production and human-readable formatting for development.
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

import structlog
from structlog.types import EventDict
from uvicorn.logging import DefaultFormatter

from .config import get_settings

# Context variable for request ID tracking
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def add_request_id(_, __, event_dict: EventDict) -> EventDict:
    """Add request ID to log entries."""
    request_id = request_id_ctx.get()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def add_service_info(_, __, event_dict: EventDict) -> EventDict:
    """Add service information to log entries."""
    event_dict["service"] = "lit_law411-agent"
    event_dict["version"] = "0.1.0"
    return event_dict


def drop_color_message_key(_, __, event_dict: EventDict) -> EventDict:
    """Drop the color message key added by uvicorn."""
    event_dict.pop("color_message", None)
    return event_dict


def setup_logging() -> None:
    """Configure structured logging for the application."""
    settings = get_settings()
    
    # Configure processors based on environment
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_request_id,
        add_service_info,
        drop_color_message_key,
    ]
    
    if settings.is_production:
        # Production: JSON formatting for log aggregation
        processors.append(structlog.processors.JSONRenderer())
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
        )
    else:
        # Development: Human-readable formatting
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
        )
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )
    
    # Configure handlers for different loggers
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Configure uvicorn logging
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers.clear()
    uvicorn_logger.addHandler(handler)
    uvicorn_logger.propagate = False
    
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers.clear()
    uvicorn_access.addHandler(handler)
    uvicorn_access.propagate = False
    
    # Configure other third-party loggers
    for logger_name in [
        "sqlalchemy.engine",
        "celery",
        "redis",
        "aiohttp",
        "elasticsearch",
        "scrapy",
    ]:
        logger = logging.getLogger(logger_name)
        # Set third-party loggers to WARNING to reduce noise
        logger.setLevel(logging.WARNING)
    
    # Configure application loggers to use configured level
    for logger_name in [
        "lit_law411_agent",
        "src",
    ]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, settings.log_level.upper()))


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.
    
    Args:
        name: Logger name (defaults to calling module)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def set_request_id(request_id: str = None) -> str:
    """Set request ID in context.
    
    Args:
        request_id: Request ID to set (generates UUID if None)
        
    Returns:
        The request ID that was set
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    
    request_id_ctx.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """Get current request ID from context.
    
    Returns:
        Current request ID or None
    """
    return request_id_ctx.get()


def clear_request_id() -> None:
    """Clear request ID from context."""
    request_id_ctx.set(None)


def log_function_call(func_name: str, **kwargs) -> None:
    """Log function call with parameters.
    
    Args:
        func_name: Name of the function being called
        **kwargs: Function parameters to log
    """
    logger = get_logger()
    logger.info(
        "Function called",
        function=func_name,
        parameters=kwargs,
    )


def log_exception(exc: Exception, context: Dict[str, Any] = None) -> None:
    """Log exception with context.
    
    Args:
        exc: Exception to log
        context: Additional context information
    """
    logger = get_logger()
    logger.error(
        "Exception occurred",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        context=context or {},
        exc_info=True,
    )


def log_performance(operation: str, duration: float, **kwargs) -> None:
    """Log performance metrics.
    
    Args:
        operation: Name of the operation
        duration: Duration in seconds
        **kwargs: Additional metrics
    """
    logger = get_logger()
    logger.info(
        "Performance metric",
        operation=operation,
        duration_seconds=duration,
        **kwargs,
    )


def log_security_event(event_type: str, details: Dict[str, Any]) -> None:
    """Log security-related events.
    
    Args:
        event_type: Type of security event
        details: Event details
    """
    logger = get_logger()
    logger.warning(
        "Security event",
        event_type=event_type,
        **details,
    )


def log_audit_trail(action: str, resource: str, user_id: str = None, **kwargs) -> None:
    """Log audit trail events.
    
    Args:
        action: Action performed
        resource: Resource affected
        user_id: ID of user performing action
        **kwargs: Additional audit information
    """
    logger = get_logger()
    logger.info(
        "Audit event",
        action=action,
        resource=resource,
        user_id=user_id,
        **kwargs,
    )


# Export commonly used functions
__all__ = [
    "setup_logging",
    "get_logger",
    "set_request_id",
    "get_request_id",
    "clear_request_id",
    "log_function_call",
    "log_exception",
    "log_performance",
    "log_security_event",
    "log_audit_trail",
]