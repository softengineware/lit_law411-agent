"""Monitoring and health check infrastructure for lit_law411-agent.

This module provides comprehensive monitoring capabilities including:
- Health check endpoints
- Prometheus metrics
- Performance monitoring
- System health monitoring
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from enum import Enum

import psutil
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import HTTPException
from sqlalchemy import text

from .config import get_settings
from .logging import get_logger
from ..db.database import get_db_session
from ..db.redis_client import RedisManager

logger = get_logger(__name__)

# Prometheus Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

DATABASE_QUERIES = Counter(
    'database_queries_total',
    'Total database queries',
    ['query_type', 'status']
)

DATABASE_QUERY_DURATION = Histogram(
    'database_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type']
)

CACHE_OPERATIONS = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'status']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections_total',
    'Active database connections'
)

SYSTEM_CPU_USAGE = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

SYSTEM_MEMORY_USAGE = Gauge(
    'system_memory_usage_percent', 
    'System memory usage percentage'
)

SYSTEM_DISK_USAGE = Gauge(
    'system_disk_usage_percent',
    'System disk usage percentage'
)


class HealthStatus(str, Enum):
    """Health check status enumeration."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class ComponentHealth:
    """Health status for individual components."""
    
    def __init__(self, name: str, status: HealthStatus, message: str = "", 
                 details: Dict[str, Any] = None, response_time_ms: float = 0):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.response_time_ms = response_time_ms
        self.timestamp = datetime.now(timezone.utc)


class HealthChecker:
    """Comprehensive health checking system."""
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_manager = RedisManager()
    
    async def check_database_health(self) -> ComponentHealth:
        """Check database connectivity and performance."""
        start_time = time.time()
        
        try:
            async with get_db_session() as session:
                # Simple connectivity test
                result = await session.execute(text("SELECT 1"))
                row = result.fetchone()
                
                if row and row[0] == 1:
                    response_time = (time.time() - start_time) * 1000
                    
                    # Check if response time is acceptable
                    if response_time > 1000:  # 1 second threshold
                        return ComponentHealth(
                            name="database",
                            status=HealthStatus.DEGRADED,
                            message=f"Database responding slowly: {response_time:.2f}ms",
                            response_time_ms=response_time
                        )
                    
                    return ComponentHealth(
                        name="database",
                        status=HealthStatus.HEALTHY,
                        message="Database connection successful",
                        response_time_ms=response_time
                    )
                else:
                    return ComponentHealth(
                        name="database",
                        status=HealthStatus.UNHEALTHY,
                        message="Database query returned unexpected result"
                    )
                    
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("Database health check failed", exception=str(e))
            
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def check_redis_health(self) -> ComponentHealth:
        """Check Redis connectivity and performance."""
        start_time = time.time()
        
        try:
            # Test Redis connection
            await self.redis_manager.connect()
            client = self.redis_manager.get_client()
            
            # Test basic operations
            test_key = "health_check"
            test_value = str(int(time.time()))
            
            await client.set(test_key, test_value, ex=60)
            retrieved_value = await client.get(test_key)
            await client.delete(test_key)
            
            response_time = (time.time() - start_time) * 1000
            
            if retrieved_value and retrieved_value.decode() == test_value:
                if response_time > 500:  # 500ms threshold
                    return ComponentHealth(
                        name="redis",
                        status=HealthStatus.DEGRADED,
                        message=f"Redis responding slowly: {response_time:.2f}ms",
                        response_time_ms=response_time
                    )
                
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    message="Redis connection and operations successful",
                    response_time_ms=response_time
                )
            else:
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.UNHEALTHY,
                    message="Redis operation test failed"
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("Redis health check failed", exception=str(e))
            
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def check_system_health(self) -> ComponentHealth:
        """Check system resource usage."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Update Prometheus metrics
            SYSTEM_CPU_USAGE.set(cpu_percent)
            SYSTEM_MEMORY_USAGE.set(memory_percent)
            SYSTEM_DISK_USAGE.set(disk_percent)
            
            details = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_free_gb": disk.free / (1024**3)
            }
            
            # Determine status based on thresholds
            if cpu_percent > 90 or memory_percent > 90 or disk_percent > 90:
                status = HealthStatus.UNHEALTHY
                message = "System resources critically low"
            elif cpu_percent > 75 or memory_percent > 75 or disk_percent > 85:
                status = HealthStatus.DEGRADED
                message = "System resources running high"
            else:
                status = HealthStatus.HEALTHY
                message = "System resources normal"
            
            return ComponentHealth(
                name="system",
                status=status,
                message=message,
                details=details
            )
            
        except Exception as e:
            logger.error("System health check failed", exception=str(e))
            
            return ComponentHealth(
                name="system",
                status=HealthStatus.UNHEALTHY,
                message=f"System health check failed: {str(e)}"
            )
    
    async def check_application_health(self) -> ComponentHealth:
        """Check application-specific health indicators."""
        try:
            details = {
                "version": self.settings.app_version,
                "environment": self.settings.environment,
                "startup_time": datetime.now(timezone.utc).isoformat()
            }
            
            return ComponentHealth(
                name="application",
                status=HealthStatus.HEALTHY,
                message="Application running normally",
                details=details
            )
            
        except Exception as e:
            logger.error("Application health check failed", exception=str(e))
            
            return ComponentHealth(
                name="application",
                status=HealthStatus.UNHEALTHY,
                message=f"Application health check failed: {str(e)}"
            )
    
    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of all components."""
        start_time = time.time()
        
        logger.info("Starting comprehensive health check")
        
        # Run all health checks concurrently
        health_checks = await asyncio.gather(
            self.check_database_health(),
            self.check_redis_health(),
            self.check_system_health(),
            self.check_application_health(),
            return_exceptions=True
        )
        
        components = {}
        overall_status = HealthStatus.HEALTHY
        
        for check in health_checks:
            if isinstance(check, Exception):
                logger.error("Health check failed with exception", exception=str(check))
                components["unknown"] = ComponentHealth(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {str(check)}"
                )
                overall_status = HealthStatus.UNHEALTHY
            else:
                components[check.name] = check
                
                # Determine overall status
                if check.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif check.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
        
        total_time = time.time() - start_time
        
        result = {
            "status": overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": round(total_time * 1000, 2),
            "components": {
                name: {
                    "status": component.status.value,
                    "message": component.message,
                    "response_time_ms": component.response_time_ms,
                    "details": component.details,
                    "timestamp": component.timestamp.isoformat()
                }
                for name, component in components.items()
            }
        }
        
        logger.info(
            "Health check completed",
            overall_status=overall_status.value,
            duration_ms=total_time * 1000,
            component_count=len(components)
        )
        
        return result


class ReadinessChecker:
    """Check if application is ready to receive traffic."""
    
    def __init__(self):
        self.health_checker = HealthChecker()
    
    async def check_readiness(self) -> Dict[str, Any]:
        """Check if application is ready to serve requests."""
        start_time = time.time()
        
        logger.info("Starting readiness check")
        
        # Check critical components for readiness
        try:
            db_health = await self.health_checker.check_database_health()
            app_health = await self.health_checker.check_application_health()
            
            # Application is ready if database and app are healthy
            is_ready = (
                db_health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED] and
                app_health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            result = {
                "ready": is_ready,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": round(duration_ms, 2),
                "checks": {
                    "database": {
                        "status": db_health.status.value,
                        "message": db_health.message
                    },
                    "application": {
                        "status": app_health.status.value,
                        "message": app_health.message
                    }
                }
            }
            
            logger.info(
                "Readiness check completed",
                ready=is_ready,
                duration_ms=duration_ms
            )
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("Readiness check failed", exception=str(e))
            
            return {
                "ready": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": round(duration_ms, 2),
                "error": str(e)
            }


class LivenessChecker:
    """Check if application is alive and running."""
    
    async def check_liveness(self) -> Dict[str, Any]:
        """Simple liveness check - just verify app is running."""
        timestamp = datetime.now(timezone.utc)
        
        result = {
            "alive": True,
            "timestamp": timestamp.isoformat(),
            "message": "Application is alive"
        }
        
        logger.debug("Liveness check completed", timestamp=timestamp.isoformat())
        
        return result


# Global instances
health_checker = HealthChecker()
readiness_checker = ReadinessChecker()
liveness_checker = LivenessChecker()


def get_prometheus_metrics() -> str:
    """Get Prometheus metrics in the expected format."""
    return generate_latest().decode('utf-8')


def update_system_metrics():
    """Update system-level Prometheus metrics."""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        SYSTEM_CPU_USAGE.set(cpu_percent)
        
        # Memory usage
        memory = psutil.virtual_memory()
        SYSTEM_MEMORY_USAGE.set(memory.percent)
        
        # Disk usage
        disk = psutil.disk_usage('/')
        SYSTEM_DISK_USAGE.set(disk.percent)
        
    except Exception as e:
        logger.error("Failed to update system metrics", exception=str(e))


# Export public interface
__all__ = [
    "HealthChecker",
    "ReadinessChecker", 
    "LivenessChecker",
    "health_checker",
    "readiness_checker",
    "liveness_checker",
    "get_prometheus_metrics",
    "update_system_metrics",
    "REQUEST_COUNT",
    "REQUEST_DURATION",
    "DATABASE_QUERIES",
    "DATABASE_QUERY_DURATION",
    "CACHE_OPERATIONS",
    "ACTIVE_CONNECTIONS",
]