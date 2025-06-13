"""API v1 module."""

from .auth import router as auth_router
from .health import router as health_router
from .content import router as content_router
from .search import router as search_router

__all__ = ["auth_router", "health_router", "content_router", "search_router"]