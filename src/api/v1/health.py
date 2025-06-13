"""Health check and monitoring API endpoints."""

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse

from ...core.monitoring import (
    health_checker,
    readiness_checker, 
    liveness_checker,
    get_prometheus_metrics,
    update_system_metrics
)
from ...core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health Checks"])


@router.get("/")
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Returns detailed health status of all application components.
    """
    try:
        result = await health_checker.comprehensive_health_check()
        
        # Return appropriate HTTP status based on health
        if result["status"] == "unhealthy":
            raise HTTPException(status_code=503, detail=result)
        elif result["status"] == "degraded":
            # Still return 200 for degraded but log warning
            logger.warning("System health degraded", details=result)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Health check endpoint failed", exception=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "status": "unhealthy",
                "message": f"Health check failed: {str(e)}"
            }
        )


@router.get("/ready")
async def readiness_probe():
    """
    Kubernetes readiness probe endpoint.
    
    Returns 200 if application is ready to receive traffic,
    503 if not ready.
    """
    try:
        result = await readiness_checker.check_readiness()
        
        if not result["ready"]:
            raise HTTPException(status_code=503, detail=result)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness probe failed", exception=str(e))
        raise HTTPException(
            status_code=503,
            detail={
                "ready": False,
                "error": str(e)
            }
        )


@router.get("/live")
async def liveness_probe():
    """
    Kubernetes liveness probe endpoint.
    
    Simple check that returns 200 if application is alive.
    """
    try:
        result = await liveness_checker.check_liveness()
        return result
        
    except Exception as e:
        logger.error("Liveness probe failed", exception=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "alive": False,
                "error": str(e)
            }
        )


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus format for scraping.
    """
    try:
        # Update system metrics before returning
        update_system_metrics()
        
        metrics = get_prometheus_metrics()
        
        return Response(
            content=metrics,
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
        
    except Exception as e:
        logger.error("Prometheus metrics endpoint failed", exception=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate metrics: {str(e)}"
        )


@router.get("/status")
async def simple_status():
    """
    Simple status endpoint for quick health verification.
    
    Returns basic application status information.
    """
    try:
        from ...core.config import get_settings
        settings = get_settings()
        
        return {
            "status": "ok",
            "service": "lit_law411-agent",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT
        }
        
    except Exception as e:
        logger.error("Status endpoint failed", exception=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Status check failed: {str(e)}"
        )