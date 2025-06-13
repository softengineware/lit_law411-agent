"""Main application entry point for lit_law411-agent."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.logging import get_logger, log_exception, setup_logging
from src.core.middleware import LoggingMiddleware, MetricsMiddleware, SecurityMiddleware
from src.core.sentry import setup_sentry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Manage application lifespan."""
    # Startup - Initialize logging first
    setup_logging()
    setup_sentry()
    
    logger = get_logger(__name__)
    logger.info(
        "Starting lit_law411-agent",
        environment=settings.environment,
        debug=settings.debug,
        log_level=settings.log_level,
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down lit_law411-agent")
    print("Shutting down lit_law411-agent")


# Create FastAPI application
app = FastAPI(
    title="lit_law411-agent",
    description="Legal Knowledge Base Agent API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# Add custom middleware (order matters - last added is executed first)
app.add_middleware(SecurityMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(LoggingMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    logger = get_logger(__name__)
    logger.info("Root endpoint accessed")
    
    return {
        "message": "Legal Knowledge Base Agent API",
        "version": "0.1.0",
        "environment": settings.environment,
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "debug": settings.debug,
    }


@app.get("/ready")
async def ready():
    """Readiness check endpoint."""
    # TODO: Add database and service checks
    return {
        "status": "ready",
        "services": {
            "database": "ready",
            "redis": "ready",
            "elasticsearch": "ready",
        },
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle global exceptions."""
    logger = get_logger(__name__)
    
    # Log exception with context
    log_exception(exc, {
        "path": request.url.path,
        "method": request.method,
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    })
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
            "message": str(exc) if settings.debug else "An error occurred",
        },
    )