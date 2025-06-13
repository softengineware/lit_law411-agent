# Monitoring and Health Checks

This document describes the monitoring and health check infrastructure for lit_law411-agent.

## Overview

The monitoring system provides comprehensive health checking, performance monitoring, and metrics collection for the Legal Knowledge Base Agent. It includes:

- **Health Check Endpoints**: Comprehensive health status reporting
- **Prometheus Metrics**: Performance and system metrics collection
- **Performance Monitoring**: Automatic timing and profiling
- **System Monitoring**: CPU, memory, and disk usage tracking

## Health Check Endpoints

### Comprehensive Health Check
```
GET /health/
```

Returns detailed health status of all application components:

```json
{
  "status": "healthy",
  "timestamp": "2025-01-13T12:00:00Z",
  "duration_ms": 150.25,
  "components": {
    "database": {
      "status": "healthy",
      "message": "Database connection successful",
      "response_time_ms": 45.2,
      "details": {},
      "timestamp": "2025-01-13T12:00:00Z"
    },
    "redis": {
      "status": "healthy", 
      "message": "Redis connection and operations successful",
      "response_time_ms": 12.5,
      "details": {},
      "timestamp": "2025-01-13T12:00:00Z"
    },
    "system": {
      "status": "healthy",
      "message": "System resources normal",
      "response_time_ms": 0,
      "details": {
        "cpu_percent": 25.3,
        "memory_percent": 45.8,
        "disk_percent": 32.1,
        "memory_available_gb": 8.2,
        "disk_free_gb": 125.7
      },
      "timestamp": "2025-01-13T12:00:00Z"
    },
    "application": {
      "status": "healthy",
      "message": "Application running normally",
      "response_time_ms": 0,
      "details": {
        "version": "0.1.0",
        "environment": "development",
        "startup_time": "2025-01-13T12:00:00Z"
      },
      "timestamp": "2025-01-13T12:00:00Z"
    }
  }
}
```

**Status Codes:**
- `200`: All components healthy or degraded
- `503`: One or more components unhealthy
- `500`: Health check system failure

### Readiness Probe
```
GET /health/ready
```

Kubernetes readiness probe endpoint. Returns 200 if application is ready to receive traffic.

```json
{
  "ready": true,
  "timestamp": "2025-01-13T12:00:00Z",
  "duration_ms": 50.25,
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection successful"
    },
    "application": {
      "status": "healthy", 
      "message": "Application running normally"
    }
  }
}
```

**Status Codes:**
- `200`: Application ready
- `503`: Application not ready

### Liveness Probe
```
GET /health/live
```

Kubernetes liveness probe endpoint. Simple check that application is alive.

```json
{
  "alive": true,
  "timestamp": "2025-01-13T12:00:00Z",
  "message": "Application is alive"
}
```

**Status Codes:**
- `200`: Application alive
- `500`: Application unresponsive

### Simple Status
```
GET /health/status
```

Quick status endpoint for basic health verification.

```json
{
  "status": "ok",
  "service": "lit_law411-agent",
  "version": "0.1.0", 
  "environment": "development"
}
```

## Prometheus Metrics

### Metrics Endpoint
```
GET /health/metrics
```

Returns metrics in Prometheus format for scraping.

### Available Metrics

#### HTTP Request Metrics
- `http_requests_total`: Total HTTP requests (labels: method, endpoint, status_code)
- `http_request_duration_seconds`: HTTP request duration histogram (labels: method, endpoint)

#### Database Metrics
- `database_queries_total`: Total database queries (labels: query_type, status)
- `database_query_duration_seconds`: Database query duration histogram (labels: query_type)
- `active_connections_total`: Active database connections gauge

#### Cache Metrics
- `cache_operations_total`: Total cache operations (labels: operation, status)

#### System Metrics
- `system_cpu_usage_percent`: System CPU usage percentage
- `system_memory_usage_percent`: System memory usage percentage
- `system_disk_usage_percent`: System disk usage percentage

### Metric Collection

Metrics are automatically collected via middleware:

```python
# Automatic HTTP request metrics
app.add_middleware(MetricsMiddleware)

# Performance timing with detailed headers
app.add_middleware(PerformanceTimingMiddleware)
```

## Performance Monitoring

### Performance Decorators

Monitor function and method performance automatically:

```python
from src.utils.performance_decorators import (
    monitor_performance,
    monitor_database_operation,
    monitor_cache_operation
)

@monitor_performance("user_lookup", track_memory=True)
async def find_user(user_id: str):
    # Function automatically monitored
    pass

@monitor_database_operation("select", track_rows=True)
async def get_users():
    # Database operation automatically tracked
    pass

@monitor_cache_operation("get")
async def get_cached_data(key: str):
    # Cache operation automatically monitored
    pass
```

### Performance Features

- **Automatic Timing**: All decorated functions timed automatically
- **Memory Tracking**: Optional memory usage monitoring
- **Slow Operation Detection**: Warnings for operations exceeding thresholds
- **Error Tracking**: Failed operations logged with context
- **Prometheus Integration**: Metrics exported to Prometheus

## Health Status Levels

The system uses three health status levels:

### Healthy ✅
- All components functioning normally
- Response times within acceptable limits
- System resources at normal levels

### Degraded ⚠️ 
- Components functioning but performance impacted
- Response times elevated but acceptable
- System resources running high but not critical

### Unhealthy ❌
- Components failed or unresponsive
- Critical errors detected
- System resources critically low

## Kubernetes Integration

### Deployment Configuration

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lit-law411-agent
spec:
  template:
    spec:
      containers:
      - name: api
        image: lit-law411-agent:latest
        ports:
        - containerPort: 8000
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          successThreshold: 1
          failureThreshold: 3
```

### Service Monitor

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: lit-law411-agent
spec:
  selector:
    matchLabels:
      app: lit-law411-agent
  endpoints:
  - port: http
    path: /health/metrics
    interval: 30s
    scrapeTimeout: 10s
```

## Grafana Dashboard

### Key Panels

1. **System Overview**
   - Overall health status
   - Request rate and response times
   - Error rates

2. **System Resources**
   - CPU usage over time
   - Memory usage and availability
   - Disk usage trends

3. **Application Performance**
   - Request duration percentiles
   - Slow operation detection
   - Database query performance

4. **Component Health**
   - Database connection status
   - Redis performance
   - Cache hit rates

### Sample Queries

```promql
# Request rate
rate(http_requests_total[5m])

# 95th percentile response time
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status_code=~"5.."}[5m]) / rate(http_requests_total[5m])

# Database query performance
histogram_quantile(0.95, rate(database_query_duration_seconds_bucket[5m]))
```

## Alerting Rules

### Critical Alerts

```yaml
groups:
- name: lit-law411-agent-critical
  rules:
  - alert: ApplicationDown
    expr: up{job="lit-law411-agent"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Application is down"
      
  - alert: HighErrorRate
    expr: rate(http_requests_total{status_code=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
```

### Warning Alerts

```yaml
  - alert: HighResponseTime
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "High response time detected"
      
  - alert: HighMemoryUsage
    expr: system_memory_usage_percent > 80
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "High memory usage"
```

## Configuration

### Environment Variables

```bash
# Monitoring configuration
PROMETHEUS_METRICS_ENABLED=true
HEALTH_CHECK_TIMEOUT=30
SLOW_REQUEST_THRESHOLD=1.0
SYSTEM_METRICS_INTERVAL=60

# Thresholds
CPU_WARNING_THRESHOLD=75
CPU_CRITICAL_THRESHOLD=90
MEMORY_WARNING_THRESHOLD=75
MEMORY_CRITICAL_THRESHOLD=90
DISK_WARNING_THRESHOLD=85
DISK_CRITICAL_THRESHOLD=95
```

### Performance Tuning

- **Metrics Collection**: Can be disabled for performance
- **Health Check Frequency**: Configurable intervals
- **Threshold Adjustment**: Customize warning/critical levels
- **Retention**: Configure metric retention periods

## Troubleshooting

### Common Issues

1. **Health Check Timeouts**
   - Check database connectivity
   - Verify Redis availability
   - Review system resource usage

2. **Missing Metrics**
   - Ensure Prometheus metrics enabled
   - Check middleware configuration
   - Verify metrics endpoint accessibility

3. **High Resource Usage Alerts**
   - Review application performance
   - Check for memory leaks
   - Analyze slow operations

### Debug Commands

```bash
# Check health status
curl http://localhost:8000/health/

# Check readiness
curl http://localhost:8000/health/ready

# Get metrics
curl http://localhost:8000/health/metrics

# Check specific component
curl http://localhost:8000/health/redis
```

## Best Practices

1. **Monitor Early**: Set up monitoring before production deployment
2. **Set Appropriate Thresholds**: Tune alerts to minimize false positives
3. **Use Labels**: Tag metrics with relevant context
4. **Regular Review**: Periodically review and update alert rules
5. **Dashboard Maintenance**: Keep dashboards relevant and actionable
6. **Document Changes**: Update monitoring docs with system changes