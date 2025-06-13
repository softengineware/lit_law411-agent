"""HTTPS redirect middleware for FastAPI.

This module provides middleware to redirect HTTP requests to HTTPS
in production environments.
"""

from typing import Optional, List
from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

logger = logging.getLogger(__name__)


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to redirect HTTP requests to HTTPS."""
    
    def __init__(
        self,
        app: ASGIApp,
        enabled: bool = True,
        redirect_status_code: int = 301,
        exclude_paths: Optional[List[str]] = None,
        exclude_hosts: Optional[List[str]] = None
    ):
        """Initialize HTTPS redirect middleware.
        
        Args:
            app: The ASGI application
            enabled: Whether HTTPS redirect is enabled
            redirect_status_code: HTTP status code for redirect (301 or 302)
            exclude_paths: Paths to exclude from redirect
            exclude_hosts: Hosts to exclude from redirect
        """
        super().__init__(app)
        self.enabled = enabled
        self.redirect_status_code = redirect_status_code
        self.exclude_paths = exclude_paths or ["/health", "/ready", "/metrics"]
        self.exclude_hosts = exclude_hosts or ["localhost", "127.0.0.1"]
    
    async def dispatch(self, request: Request, call_next):
        """Process request and redirect to HTTPS if needed.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler
            
        Returns:
            Redirect response or normal response
        """
        # Skip if disabled
        if not self.enabled:
            return await call_next(request)
        
        # Get request details
        headers = dict(request.headers)
        host = headers.get("host", "")
        
        # Check if already HTTPS
        # Check multiple headers that proxies might set
        is_https = (
            request.url.scheme == "https" or
            headers.get("x-forwarded-proto") == "https" or
            headers.get("x-forwarded-ssl") == "on" or
            headers.get("x-url-scheme") == "https"
        )
        
        if is_https:
            return await call_next(request)
        
        # Check exclusions
        # Exclude certain hosts (like localhost for development)
        for exclude_host in self.exclude_hosts:
            if exclude_host in host:
                return await call_next(request)
        
        # Exclude certain paths (like health checks)
        for exclude_path in self.exclude_paths:
            if request.url.path.startswith(exclude_path):
                return await call_next(request)
        
        # Build HTTPS URL
        https_url = request.url.replace(scheme="https")
        
        logger.info(f"Redirecting HTTP to HTTPS: {request.url} -> {https_url}")
        
        # Return redirect response
        return RedirectResponse(
            url=str(https_url),
            status_code=self.redirect_status_code
        )


def get_https_redirect_middleware(
    environment: Optional[str] = None,
    force_enabled: Optional[bool] = None,
    **kwargs
) -> HTTPSRedirectMiddleware:
    """Factory function to create HTTPS redirect middleware.
    
    Args:
        environment: Application environment (production, development, etc.)
        force_enabled: Force enable/disable regardless of environment
        **kwargs: Additional arguments for HTTPSRedirectMiddleware
        
    Returns:
        Configured HTTPSRedirectMiddleware instance
    """
    # Determine if HTTPS redirect should be enabled
    if force_enabled is not None:
        enabled = force_enabled
    else:
        # Enable HTTPS redirect in production by default
        enabled = environment == "production"
    
    return HTTPSRedirectMiddleware(
        app=None,  # Will be set by FastAPI
        enabled=enabled,
        **kwargs
    )