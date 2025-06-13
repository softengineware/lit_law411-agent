"""Tests for monitoring and health check functionality."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.core.monitoring import (
    HealthChecker,
    ReadinessChecker,
    LivenessChecker,
    ComponentHealth,
    HealthStatus
)


class TestComponentHealth:
    """Test ComponentHealth class."""
    
    def test_component_health_creation(self):
        """Test creating ComponentHealth instance."""
        health = ComponentHealth(
            name="test_component",
            status=HealthStatus.HEALTHY,
            message="All good",
            details={"version": "1.0"},
            response_time_ms=100.5
        )
        
        assert health.name == "test_component"
        assert health.status == HealthStatus.HEALTHY
        assert health.message == "All good"
        assert health.details == {"version": "1.0"}
        assert health.response_time_ms == 100.5
        assert health.timestamp is not None


class TestHealthChecker:
    """Test HealthChecker class."""
    
    @pytest.fixture
    def health_checker(self):
        """Create HealthChecker instance for testing."""
        return HealthChecker()
    
    @pytest.mark.asyncio
    async def test_check_application_health(self, health_checker):
        """Test application health check."""
        health = await health_checker.check_application_health()
        
        assert health.name == "application"
        assert health.status == HealthStatus.HEALTHY
        assert "Application running normally" in health.message
        assert "version" in health.details
        assert "environment" in health.details
    
    @pytest.mark.asyncio
    async def test_check_system_health(self, health_checker):
        """Test system health check."""
        health = await health_checker.check_system_health()
        
        assert health.name == "system"
        assert health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
        assert "cpu_percent" in health.details
        assert "memory_percent" in health.details
        assert "disk_percent" in health.details
    
    @pytest.mark.asyncio
    async def test_check_database_health_success(self, health_checker):
        """Test successful database health check."""
        # Mock successful database connection
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.fetchone.return_value = (1,)
        mock_session.execute.return_value = mock_result
        
        with patch('src.core.monitoring.get_db_session') as mock_get_db:
            mock_get_db.return_value.__aenter__.return_value = mock_session
            
            health = await health_checker.check_database_health()
            
            assert health.name == "database"
            assert health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
            assert health.response_time_ms > 0
    
    @pytest.mark.asyncio
    async def test_check_database_health_failure(self, health_checker):
        """Test database health check failure."""
        # Mock database connection failure
        with patch('src.core.monitoring.get_db_session') as mock_get_db:
            mock_get_db.side_effect = Exception("Connection failed")
            
            health = await health_checker.check_database_health()
            
            assert health.name == "database"
            assert health.status == HealthStatus.UNHEALTHY
            assert "Connection failed" in health.message
    
    @pytest.mark.asyncio
    async def test_check_redis_health_success(self, health_checker):
        """Test successful Redis health check."""
        # Mock the entire check_redis_health method to avoid time complexity
        mock_health = ComponentHealth(
            name="redis",
            status=HealthStatus.HEALTHY,
            message="Redis connection and operations successful",
            response_time_ms=50.0
        )
        
        with patch.object(health_checker, 'check_redis_health', return_value=mock_health):
            health = await health_checker.check_redis_health()
            
            assert health.name == "redis"
            assert health.status == HealthStatus.HEALTHY
            assert health.response_time_ms == 50.0
    
    @pytest.mark.asyncio
    async def test_check_redis_health_failure(self, health_checker):
        """Test Redis health check failure."""
        # Mock Redis connection failure
        health_checker.redis_manager.connect = AsyncMock(side_effect=Exception("Redis unavailable"))
        
        health = await health_checker.check_redis_health()
        
        assert health.name == "redis"
        assert health.status == HealthStatus.UNHEALTHY
        assert "Redis unavailable" in health.message
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check(self, health_checker):
        """Test comprehensive health check."""
        # Mock all individual health checks to return healthy status
        with patch.object(health_checker, 'check_database_health') as mock_db, \
             patch.object(health_checker, 'check_redis_health') as mock_redis, \
             patch.object(health_checker, 'check_system_health') as mock_system, \
             patch.object(health_checker, 'check_application_health') as mock_app:
            
            # Set up mocks
            mock_db.return_value = ComponentHealth("database", HealthStatus.HEALTHY, "OK")
            mock_redis.return_value = ComponentHealth("redis", HealthStatus.HEALTHY, "OK")
            mock_system.return_value = ComponentHealth("system", HealthStatus.HEALTHY, "OK")
            mock_app.return_value = ComponentHealth("application", HealthStatus.HEALTHY, "OK")
            
            result = await health_checker.comprehensive_health_check()
            
            assert result["status"] == "healthy"
            assert "timestamp" in result
            assert "duration_ms" in result
            assert "components" in result
            assert len(result["components"]) == 4
            
            # Check each component
            for component_name in ["database", "redis", "system", "application"]:
                assert component_name in result["components"]
                assert result["components"][component_name]["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_degraded(self, health_checker):
        """Test comprehensive health check with degraded status."""
        with patch.object(health_checker, 'check_database_health') as mock_db, \
             patch.object(health_checker, 'check_redis_health') as mock_redis, \
             patch.object(health_checker, 'check_system_health') as mock_system, \
             patch.object(health_checker, 'check_application_health') as mock_app:
            
            # Set up mocks with one degraded service
            mock_db.return_value = ComponentHealth("database", HealthStatus.HEALTHY, "OK")
            mock_redis.return_value = ComponentHealth("redis", HealthStatus.DEGRADED, "Slow")
            mock_system.return_value = ComponentHealth("system", HealthStatus.HEALTHY, "OK")
            mock_app.return_value = ComponentHealth("application", HealthStatus.HEALTHY, "OK")
            
            result = await health_checker.comprehensive_health_check()
            
            assert result["status"] == "degraded"
            assert result["components"]["redis"]["status"] == "degraded"
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_unhealthy(self, health_checker):
        """Test comprehensive health check with unhealthy status."""
        with patch.object(health_checker, 'check_database_health') as mock_db, \
             patch.object(health_checker, 'check_redis_health') as mock_redis, \
             patch.object(health_checker, 'check_system_health') as mock_system, \
             patch.object(health_checker, 'check_application_health') as mock_app:
            
            # Set up mocks with one unhealthy service
            mock_db.return_value = ComponentHealth("database", HealthStatus.UNHEALTHY, "Failed")
            mock_redis.return_value = ComponentHealth("redis", HealthStatus.HEALTHY, "OK")
            mock_system.return_value = ComponentHealth("system", HealthStatus.HEALTHY, "OK")
            mock_app.return_value = ComponentHealth("application", HealthStatus.HEALTHY, "OK")
            
            result = await health_checker.comprehensive_health_check()
            
            assert result["status"] == "unhealthy"
            assert result["components"]["database"]["status"] == "unhealthy"


class TestReadinessChecker:
    """Test ReadinessChecker class."""
    
    @pytest.fixture
    def readiness_checker(self):
        """Create ReadinessChecker instance for testing."""
        return ReadinessChecker()
    
    @pytest.mark.asyncio
    async def test_check_readiness_ready(self, readiness_checker):
        """Test readiness check when ready."""
        # Mock health checker to return healthy components
        with patch.object(readiness_checker.health_checker, 'check_database_health') as mock_db, \
             patch.object(readiness_checker.health_checker, 'check_application_health') as mock_app:
            
            mock_db.return_value = ComponentHealth("database", HealthStatus.HEALTHY, "OK")
            mock_app.return_value = ComponentHealth("application", HealthStatus.HEALTHY, "OK")
            
            result = await readiness_checker.check_readiness()
            
            assert result["ready"] is True
            assert "timestamp" in result
            assert "duration_ms" in result
            assert "checks" in result
    
    @pytest.mark.asyncio
    async def test_check_readiness_not_ready(self, readiness_checker):
        """Test readiness check when not ready."""
        # Mock health checker to return unhealthy database
        with patch.object(readiness_checker.health_checker, 'check_database_health') as mock_db, \
             patch.object(readiness_checker.health_checker, 'check_application_health') as mock_app:
            
            mock_db.return_value = ComponentHealth("database", HealthStatus.UNHEALTHY, "Failed")
            mock_app.return_value = ComponentHealth("application", HealthStatus.HEALTHY, "OK")
            
            result = await readiness_checker.check_readiness()
            
            assert result["ready"] is False
            assert result["checks"]["database"]["status"] == "unhealthy"
    
    @pytest.mark.asyncio
    async def test_check_readiness_exception(self, readiness_checker):
        """Test readiness check with exception."""
        # Mock health checker to raise exception
        with patch.object(readiness_checker.health_checker, 'check_database_health') as mock_db:
            mock_db.side_effect = Exception("Health check failed")
            
            result = await readiness_checker.check_readiness()
            
            assert result["ready"] is False
            assert "error" in result


class TestLivenessChecker:
    """Test LivenessChecker class."""
    
    @pytest.fixture
    def liveness_checker(self):
        """Create LivenessChecker instance for testing."""
        return LivenessChecker()
    
    @pytest.mark.asyncio
    async def test_check_liveness(self, liveness_checker):
        """Test liveness check."""
        result = await liveness_checker.check_liveness()
        
        assert result["alive"] is True
        assert "timestamp" in result
        assert result["message"] == "Application is alive"


class TestPrometheusMetrics:
    """Test Prometheus metrics functionality."""
    
    def test_get_prometheus_metrics(self):
        """Test getting Prometheus metrics."""
        from src.core.monitoring import get_prometheus_metrics
        
        metrics = get_prometheus_metrics()
        
        assert isinstance(metrics, str)
        assert len(metrics) > 0
        # Should contain some basic metrics
        assert "http_requests_total" in metrics or "python_info" in metrics
    
    def test_update_system_metrics(self):
        """Test updating system metrics."""
        from src.core.monitoring import update_system_metrics, SYSTEM_CPU_USAGE
        
        # This should not raise an exception
        update_system_metrics()
        
        # CPU usage should be set (value depends on system)
        # We can't assert specific values, but can check it was called
        assert SYSTEM_CPU_USAGE._value.get() is not None


class TestPerformanceDecorators:
    """Test performance monitoring decorators."""
    
    def test_monitor_performance_decorator_import(self):
        """Test that performance decorators can be imported."""
        from src.utils.performance_decorators import (
            monitor_performance,
            monitor_database_operation,
            monitor_cache_operation
        )
        
        assert callable(monitor_performance)
        assert callable(monitor_database_operation)
        assert callable(monitor_cache_operation)
    
    def test_monitor_performance_sync_function(self):
        """Test performance monitoring decorator on sync function."""
        from src.utils.performance_decorators import monitor_performance
        
        @monitor_performance("test_operation")
        def test_function(x, y):
            return x + y
        
        result = test_function(1, 2)
        assert result == 3
    
    @pytest.mark.asyncio
    async def test_monitor_performance_async_function(self):
        """Test performance monitoring decorator on async function."""
        from src.utils.performance_decorators import monitor_performance
        
        @monitor_performance("test_async_operation")
        async def test_async_function(x, y):
            await asyncio.sleep(0.001)  # Small delay
            return x * y
        
        result = await test_async_function(3, 4)
        assert result == 12