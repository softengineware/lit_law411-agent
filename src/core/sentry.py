"""Sentry integration for error tracking and monitoring.

This module provides Sentry configuration for error tracking in production.
"""

import logging
from typing import Dict, Optional

try:
    import sentry_sdk
    from sentry_sdk.integrations.asyncio import AsyncioIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

from .config import get_settings
from .logging import get_logger

logger = get_logger(__name__)


def setup_sentry() -> None:
    """Configure Sentry for error tracking."""
    settings = get_settings()
    
    if not SENTRY_AVAILABLE:
        logger.warning("Sentry SDK not available, error tracking disabled")
        return
    
    if not settings.sentry_dsn:
        logger.info("Sentry DSN not configured, error tracking disabled")
        return
    
    # Configure Sentry integrations
    integrations = [
        # FastAPI integration for web request tracking
        FastApiIntegration(auto_enable=True),
        
        # Logging integration
        LoggingIntegration(
            level=logging.INFO,        # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors as events
        ),
        
        # SQLAlchemy integration for database query tracking
        SqlalchemyIntegration(),
        
        # Redis integration
        RedisIntegration(),
        
        # Celery integration for background task tracking
        CeleryIntegration(),
        
        # Asyncio integration
        AsyncioIntegration(),
    ]
    
    # Initialize Sentry
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=integrations,
        environment=settings.environment,
        release=f"lit_law411-agent@0.1.0",
        
        # Performance monitoring
        traces_sample_rate=1.0 if settings.is_development else 0.1,
        
        # Error sampling
        sample_rate=1.0,
        
        # Additional options
        attach_stacktrace=True,
        send_default_pii=False,  # Don't send personally identifiable information
        max_breadcrumbs=50,
        
        # Configure which data to send
        before_send=filter_sensitive_data,
        before_send_transaction=filter_transaction_data,
    )
    
    # Set user context
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("service", "lit_law411-agent")
        scope.set_tag("version", "0.1.0")
        scope.set_context("runtime", {
            "name": "Python",
            "version": "3.11+",
        })
    
    logger.info("Sentry error tracking initialized", environment=settings.environment)


def filter_sensitive_data(event: Dict, hint: Dict) -> Optional[Dict]:
    """Filter sensitive data from Sentry events.
    
    Args:
        event: Sentry event data
        hint: Additional context
        
    Returns:
        Filtered event or None to drop event
    """
    # Remove sensitive headers
    if "request" in event and "headers" in event["request"]:
        sensitive_headers = ["authorization", "cookie", "x-api-key", "x-auth-token"]
        for header in sensitive_headers:
            event["request"]["headers"].pop(header, None)
    
    # Remove sensitive query parameters
    if "request" in event and "query_string" in event["request"]:
        query_string = event["request"]["query_string"]
        if any(param in query_string.lower() for param in ["token", "key", "secret"]):
            event["request"]["query_string"] = "[Filtered]"
    
    # Remove sensitive form data
    if "request" in event and "data" in event["request"]:
        data = event["request"]["data"]
        if isinstance(data, dict):
            sensitive_fields = ["password", "token", "secret", "key", "api_key"]
            for field in sensitive_fields:
                if field in data:
                    data[field] = "[Filtered]"
    
    return event


def filter_transaction_data(event: Dict, hint: Dict) -> Optional[Dict]:
    """Filter sensitive data from Sentry transaction events.
    
    Args:
        event: Sentry transaction event
        hint: Additional context
        
    Returns:
        Filtered event or None to drop event
    """
    # Don't send transactions for health checks and metrics
    if "transaction" in event:
        transaction_name = event["transaction"]
        if any(path in transaction_name for path in ["/health", "/metrics", "/ready"]):
            return None
    
    return event


def capture_exception(exc: Exception, **kwargs) -> Optional[str]:
    """Capture exception in Sentry.
    
    Args:
        exc: Exception to capture
        **kwargs: Additional context
        
    Returns:
        Sentry event ID if sent
    """
    if not SENTRY_AVAILABLE:
        return None
    
    with sentry_sdk.configure_scope() as scope:
        # Add additional context
        for key, value in kwargs.items():
            scope.set_extra(key, value)
        
        # Capture exception
        return sentry_sdk.capture_exception(exc)


def capture_message(message: str, level: str = "info", **kwargs) -> Optional[str]:
    """Capture message in Sentry.
    
    Args:
        message: Message to capture
        level: Log level (debug, info, warning, error, fatal)
        **kwargs: Additional context
        
    Returns:
        Sentry event ID if sent
    """
    if not SENTRY_AVAILABLE:
        return None
    
    with sentry_sdk.configure_scope() as scope:
        # Add additional context
        for key, value in kwargs.items():
            scope.set_extra(key, value)
        
        # Capture message
        return sentry_sdk.capture_message(message, level=level)


def set_user_context(user_id: str, email: str = None, **kwargs) -> None:
    """Set user context for Sentry.
    
    Args:
        user_id: User identifier
        email: User email (optional)
        **kwargs: Additional user data
    """
    if not SENTRY_AVAILABLE:
        return
    
    with sentry_sdk.configure_scope() as scope:
        scope.set_user({
            "id": user_id,
            "email": email,
            **kwargs
        })


def add_breadcrumb(message: str, category: str = "custom", level: str = "info", **data) -> None:
    """Add breadcrumb to Sentry.
    
    Args:
        message: Breadcrumb message
        category: Breadcrumb category
        level: Log level
        **data: Additional breadcrumb data
    """
    if not SENTRY_AVAILABLE:
        return
    
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data,
    )


def configure_sentry_logging_handler() -> None:
    """Configure Python logging to send errors to Sentry."""
    if not SENTRY_AVAILABLE:
        return
    
    from sentry_sdk.integrations.logging import SentryHandler
    
    # Add Sentry handler to root logger
    sentry_handler = SentryHandler()
    sentry_handler.setLevel(logging.ERROR)
    
    root_logger = logging.getLogger()
    root_logger.addHandler(sentry_handler)
    
    logger.info("Sentry logging handler configured")


# Export functions
__all__ = [
    "setup_sentry",
    "capture_exception",
    "capture_message",
    "set_user_context",
    "add_breadcrumb",
    "configure_sentry_logging_handler",
]