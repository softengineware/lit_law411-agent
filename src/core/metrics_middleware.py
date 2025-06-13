"""Middleware for automatic metrics collection and performance monitoring."""

import time
from typing import Callable
from urllib.parse import urlparse

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .monitoring import REQUEST_COUNT, REQUEST_DURATION
from .logging import get_logger

logger = get_logger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically collect HTTP request metrics."""

    def __init__(self, app, record_response_times: bool = True):
        super().__init__(app)
        self.record_response_times = record_response_times

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        start_time = time.time()
        
        # Extract method and endpoint
        method = request.method
        path = request.url.path
        
        # Normalize endpoint for metrics (remove dynamic parts)
        endpoint = self._normalize_endpoint(path)
        
        try:
            # Process request
            response = await call_next(request)
            status_code = str(response.status_code)
            
        except Exception as e:
            # Handle exceptions
            logger.error(
                "Request processing failed",
                method=method,
                endpoint=endpoint,
                exception=str(e)
            )
            status_code = "500"
            
            # Re-raise the exception after metrics collection
            duration = time.time() - start_time
            
            # Record metrics for failed requests
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
            
            if self.record_response_times:
                REQUEST_DURATION.labels(
                    method=method,
                    endpoint=endpoint
                ).observe(duration)
            
            raise
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Record metrics
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()
        
        if self.record_response_times:
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
        
        # Add performance headers to response
        response.headers["X-Response-Time"] = f"{duration:.4f}"
        
        # Log slow requests
        if duration > 1.0:  # Log requests slower than 1 second
            logger.warning(
                "Slow request detected",
                method=method,
                endpoint=endpoint,
                duration_seconds=duration,
                status_code=status_code
            )
        
        return response

    def _normalize_endpoint(self, path: str) -> str:
        """
        Normalize endpoint path for metrics collection.
        
        Replaces dynamic segments with placeholders to avoid
        high cardinality in metrics.
        
        Examples:
        - /api/v1/users/123 -> /api/v1/users/{id}
        - /api/v1/content/abc-def-123 -> /api/v1/content/{id}
        """
        # Common patterns for dynamic segments
        import re
        
        # Replace UUIDs
        path = re.sub(
            r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '/{uuid}',
            path,
            flags=re.IGNORECASE
        )
        
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        
        # Replace alphanumeric IDs (like content IDs)
        path = re.sub(r'/[a-zA-Z0-9-_]{10,}', '/{id}', path)
        
        # Known endpoint patterns
        endpoint_patterns = {
            '/api/v1/users/{id}': '/api/v1/users/{id}',
            '/api/v1/content/{id}': '/api/v1/content/{id}',
            '/api/v1/sources/{id}': '/api/v1/sources/{id}',
            '/api/v1/search': '/api/v1/search',
            '/health': '/health',
            '/health/ready': '/health/ready',
            '/health/live': '/health/live',
            '/health/metrics': '/health/metrics',
            '/docs': '/docs',
            '/openapi.json': '/openapi.json',
        }
        
        # Return known pattern or normalized path
        return endpoint_patterns.get(path, path)


class PerformanceTimingMiddleware(BaseHTTPMiddleware):
    """Middleware for detailed performance timing and profiling."""

    def __init__(self, app, slow_request_threshold: float = 1.0):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with detailed timing."""
        start_time = time.time()
        
        # Extract request info
        method = request.method
        path = request.url.path
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Process request
        response = await call_next(request)
        
        # Calculate timings
        total_duration = time.time() - start_time
        
        # Add timing headers
        response.headers["X-Process-Time"] = f"{total_duration:.4f}"
        response.headers["X-Timestamp"] = str(int(start_time))
        
        # Log detailed performance info for slow requests
        if total_duration > self.slow_request_threshold:
            logger.warning(
                "Performance: Slow request",
                method=method,
                path=path,
                total_duration=total_duration,
                status_code=response.status_code,
                user_agent=user_agent,
                content_length=response.headers.get("content-length", "unknown")
            )
        
        # Log all requests at debug level
        logger.debug(
            "Request completed",
            method=method,
            path=path,
            duration_seconds=total_duration,
            status_code=response.status_code,
            response_size=response.headers.get("content-length", "unknown")
        )
        
        return response


# Export middleware classes
__all__ = [
    "MetricsMiddleware",
    "PerformanceTimingMiddleware",
]