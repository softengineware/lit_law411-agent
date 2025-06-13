"""Security headers middleware for FastAPI application.

This module provides comprehensive security headers to protect against
common web vulnerabilities including XSS, clickjacking, and content
type sniffing attacks.
"""

from typing import Dict, Optional, List
from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""
    
    def __init__(
        self, 
        app: ASGIApp,
        csp_directives: Optional[Dict[str, List[str]]] = None,
        hsts_max_age: int = 31536000,  # 1 year
        custom_headers: Optional[Dict[str, str]] = None
    ):
        """Initialize security headers middleware.
        
        Args:
            app: The ASGI application
            csp_directives: Content Security Policy directives
            hsts_max_age: Max age for HSTS header in seconds
            custom_headers: Additional custom headers to add
        """
        super().__init__(app)
        self.csp_directives = csp_directives or self._get_default_csp()
        self.hsts_max_age = hsts_max_age
        self.custom_headers = custom_headers or {}
        
    def _get_default_csp(self) -> Dict[str, List[str]]:
        """Get default Content Security Policy directives.
        
        Returns:
            Dictionary of CSP directives
        """
        return {
            "default-src": ["'self'"],
            "script-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
            "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
            "font-src": ["'self'", "https://fonts.gstatic.com"],
            "img-src": ["'self'", "data:", "https:"],
            "connect-src": ["'self'"],
            "frame-ancestors": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"]
        }
    
    def _build_csp_header(self) -> str:
        """Build Content Security Policy header value.
        
        Returns:
            CSP header string
        """
        directives = []
        for directive, sources in self.csp_directives.items():
            if sources:
                directive_value = f"{directive} {' '.join(sources)}"
                directives.append(directive_value)
        return "; ".join(directives)
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers to response.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler
            
        Returns:
            Response with security headers
        """
        response = await call_next(request)
        
        # Core security headers
        security_headers = {
            # Prevent XSS attacks
            "X-XSS-Protection": "1; mode=block",
            
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # Control referrer information
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Content Security Policy
            "Content-Security-Policy": self._build_csp_header(),
            
            # Force HTTPS
            "Strict-Transport-Security": f"max-age={self.hsts_max_age}; includeSubDomains",
            
            # Prevent browser features
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            
            # Remove server header info
            "X-Powered-By": "",
            "Server": ""
        }
        
        # Add custom headers
        security_headers.update(self.custom_headers)
        
        # Apply headers to response
        for header, value in security_headers.items():
            if value:  # Only set non-empty values
                response.headers[header] = value
                
        return response


def get_security_headers_middleware(
    csp_overrides: Optional[Dict[str, List[str]]] = None,
    enable_hsts: bool = True,
    hsts_max_age: int = 31536000,
    custom_headers: Optional[Dict[str, str]] = None
) -> SecurityHeadersMiddleware:
    """Factory function to create security headers middleware.
    
    Args:
        csp_overrides: Override specific CSP directives
        enable_hsts: Whether to enable HSTS
        hsts_max_age: HSTS max age if enabled
        custom_headers: Additional headers to add
        
    Returns:
        Configured SecurityHeadersMiddleware instance
    """
    # Get default CSP and apply overrides
    middleware = SecurityHeadersMiddleware(
        app=None,  # Will be set by FastAPI
        csp_directives=csp_overrides,
        hsts_max_age=hsts_max_age if enable_hsts else 0,
        custom_headers=custom_headers
    )
    
    return middleware