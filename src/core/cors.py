"""CORS (Cross-Origin Resource Sharing) configuration for FastAPI.

This module provides CORS middleware configuration to control
which origins can access the API.
"""

from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)


def get_cors_origins() -> List[str]:
    """Get allowed CORS origins from settings.
    
    Returns:
        List of allowed origin URLs
    """
    # Default origins for development
    default_origins = [
        "http://localhost:3000",  # React dev server
        "http://localhost:8000",  # FastAPI dev server
        "http://localhost:8080",  # Alternative frontend
    ]
    
    # Add production origins from settings
    if hasattr(settings, 'cors_origins') and settings.cors_origins:
        if isinstance(settings.cors_origins, str):
            # Parse comma-separated string
            origins = [origin.strip() for origin in settings.cors_origins.split(',')]
        else:
            origins = settings.cors_origins
    else:
        origins = []
    
    # Combine default and configured origins
    all_origins = list(set(default_origins + origins))
    
    # In production, remove localhost origins
    if hasattr(settings, 'environment') and settings.environment == 'production':
        all_origins = [o for o in all_origins if 'localhost' not in o]
    
    return all_origins


def get_cors_middleware(
    allow_origins: Optional[List[str]] = None,
    allow_credentials: bool = True,
    allow_methods: Optional[List[str]] = None,
    allow_headers: Optional[List[str]] = None,
    expose_headers: Optional[List[str]] = None,
    max_age: int = 3600
) -> dict:
    """Get CORS middleware configuration.
    
    Args:
        allow_origins: List of allowed origins (uses settings if None)
        allow_credentials: Whether to allow credentials
        allow_methods: Allowed HTTP methods
        allow_headers: Allowed request headers
        expose_headers: Headers exposed to the browser
        max_age: Max age for preflight cache
        
    Returns:
        Dictionary of CORS middleware parameters
    """
    if allow_origins is None:
        allow_origins = get_cors_origins()
    
    if allow_methods is None:
        allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    
    if allow_headers is None:
        allow_headers = [
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "X-API-Key",
            "X-Client-Version",
            "X-Request-ID"
        ]
    
    if expose_headers is None:
        expose_headers = [
            "X-Total-Count",
            "X-Page-Count", 
            "X-Current-Page",
            "X-Per-Page",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ]
    
    cors_config = {
        "allow_origins": allow_origins,
        "allow_credentials": allow_credentials,
        "allow_methods": allow_methods,
        "allow_headers": allow_headers,
        "expose_headers": expose_headers,
        "max_age": max_age
    }
    
    logger.info(f"CORS configured with origins: {allow_origins}")
    
    return cors_config


class CORSConfig:
    """CORS configuration class for more advanced setups."""
    
    def __init__(self):
        self.origins = get_cors_origins()
        self.credentials = True
        self.methods = ["*"]  # Allow all methods
        self.headers = ["*"]  # Allow all headers
        
    def get_middleware_kwargs(self) -> dict:
        """Get keyword arguments for CORSMiddleware.
        
        Returns:
            Dictionary of middleware parameters
        """
        return {
            "allow_origins": self.origins,
            "allow_credentials": self.credentials,
            "allow_methods": self.methods,
            "allow_headers": self.headers,
        }
    
    def add_origin(self, origin: str) -> None:
        """Add an allowed origin.
        
        Args:
            origin: Origin URL to add
        """
        if origin not in self.origins:
            self.origins.append(origin)
            logger.info(f"Added CORS origin: {origin}")
    
    def remove_origin(self, origin: str) -> None:
        """Remove an allowed origin.
        
        Args:
            origin: Origin URL to remove
        """
        if origin in self.origins:
            self.origins.remove(origin)
            logger.info(f"Removed CORS origin: {origin}")
    
    def is_origin_allowed(self, origin: str) -> bool:
        """Check if an origin is allowed.
        
        Args:
            origin: Origin URL to check
            
        Returns:
            True if origin is allowed
        """
        return origin in self.origins or "*" in self.origins