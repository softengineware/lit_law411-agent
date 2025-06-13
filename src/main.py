"""Main application entry point for lit_law411-agent."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.logging import get_logger, log_exception, setup_logging
from src.core.metrics_middleware import MetricsMiddleware, PerformanceTimingMiddleware
from src.core.sentry import setup_sentry
from src.db.redis_client import redis_manager
from src.db.cache_manager import cache_health_checker
from src.api.v1.health import router as health_router


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
    
    # Initialize Redis connection
    try:
        await redis_manager.connect()
        logger.info("Redis connection established successfully")
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        # Don't fail startup, but log the issue
    
    yield
    
    # Shutdown
    logger.info("Shutting down lit_law411-agent")
    
    # Close Redis connection
    try:
        await redis_manager.disconnect()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.error("Error closing Redis connection", error=str(e))
    
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
app.add_middleware(PerformanceTimingMiddleware)
app.add_middleware(MetricsMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)

# Import and include auth router
from src.api.v1.auth import router as auth_router
app.include_router(auth_router, prefix="/api/v1")


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


# Note: Health endpoints are now handled by the health_router
# Old endpoints are commented out to avoid conflicts

# @app.get("/health")
# async def health():
#     """Health check endpoint."""
#     return {
#         "status": "healthy",
#         "environment": settings.environment,
#         "debug": settings.debug,
#     }


# @app.get("/ready")
# async def ready():
#     """Readiness check endpoint."""
#     # Check Redis health
#     redis_healthy = await redis_manager.health_check()
#     redis_status = "ready" if redis_healthy else "unavailable"
#     
#     # TODO: Add database and elasticsearch checks
#     overall_status = "ready" if redis_healthy else "degraded"
#     
#     return {
#         "status": overall_status,
#         "services": {
#             "database": "ready",  # TODO: Implement actual check
#             "redis": redis_status,
#             "elasticsearch": "ready",  # TODO: Implement actual check
#         },
#     }


@app.get("/health/redis")
async def redis_health():
    """Redis-specific health check endpoint."""
    health_report = await cache_health_checker.get_full_health_report()
    
    status_code = 200 if health_report.get("healthy", False) else 503
    return JSONResponse(
        status_code=status_code,
        content=health_report
    )


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