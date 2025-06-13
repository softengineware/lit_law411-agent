"""Main application entry point for lit_law411-agent."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Manage application lifespan."""
    # Startup
    print(f"Starting lit_law411-agent in {settings.environment} mode")
    yield
    # Shutdown
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
async def global_exception_handler(request, exc):
    """Handle global exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
            "message": str(exc) if settings.debug else "An error occurred",
        },
    )