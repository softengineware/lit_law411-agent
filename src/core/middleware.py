"""Middleware components for lit_law411-agent.

This module provides FastAPI middleware for logging, security, and monitoring.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .logging import (
    clear_request_id,
    get_logger,
    get_request_id,
    log_performance,
    log_security_event,
    set_request_id,
)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request logging and tracking."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with logging.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            HTTP response
        """
        # Generate and set request ID
        request_id = set_request_id()
        
        # Add request ID to response headers
        start_time = time.time()
        
        logger = get_logger(__name__)
        
        # Log incoming request
        logger.info(
            "Request started",
            method=request.method,
            url=str(request.url),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            content_type=request.headers.get("content-type"),
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                "Request completed",
                status_code=response.status_code,
                duration_seconds=duration,
            )
            
            # Log performance metric
            log_performance(
                operation="http_request",
                duration=duration,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as exc:
            # Calculate duration
            duration = time.time() - start_time
            
            # Log error
            logger.error(
                "Request failed",
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                duration_seconds=duration,
                exc_info=True,
            )
            
            # Log performance metric for failed request
            log_performance(
                operation="http_request_failed",
                duration=duration,
                method=request.method,
                path=request.url.path,
                exception_type=type(exc).__name__,
            )
            
            raise
            
        finally:
            # Clean up request context
            clear_request_id()


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for security monitoring and headers."""

    def __init__(self, app, max_request_size: int = 10 * 1024 * 1024):  # 10MB default
        """Initialize security middleware.
        
        Args:
            app: FastAPI application
            max_request_size: Maximum request size in bytes
        """
        super().__init__(app)
        self.max_request_size = max_request_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with security checks.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            HTTP response with security headers
        """
        # Check request size
        if hasattr(request, "headers"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_request_size:
                log_security_event(
                    "request_too_large",
                    {
                        "content_length": content_length,
                        "max_allowed": self.max_request_size,
                        "client_ip": request.client.host if request.client else None,
                        "path": request.url.path,
                    }
                )
        
        # Check for suspicious patterns
        suspicious_patterns = [
            "../",
            "script>",
            "SELECT ",
            "UNION ",
            "DROP ",
            "INSERT ",
            "UPDATE ",
            "DELETE ",
        ]
        
        query_string = str(request.url.query).upper()
        path = request.url.path.upper()
        
        for pattern in suspicious_patterns:
            if pattern in query_string or pattern in path:
                log_security_event(
                    "suspicious_request",
                    {
                        "pattern": pattern,
                        "path": request.url.path,
                        "query": str(request.url.query),
                        "client_ip": request.client.host if request.client else None,
                        "user_agent": request.headers.get("user-agent"),
                    }
                )
                break
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for metrics collection."""

    def __init__(self, app):
        """Initialize metrics middleware.
        
        Args:
            app: FastAPI application
        """
        super().__init__(app)
        self.request_count = 0
        self.request_duration_sum = 0.0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with metrics collection.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            HTTP response
        """
        start_time = time.time()
        
        # Increment request counter
        self.request_count += 1
        
        # Process request
        response = await call_next(request)
        
        # Calculate and store duration
        duration = time.time() - start_time
        self.request_duration_sum += duration
        
        # Add metrics headers
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        
        return response


# Export middleware classes
__all__ = [
    "LoggingMiddleware",
    "SecurityMiddleware", 
    "MetricsMiddleware",
]