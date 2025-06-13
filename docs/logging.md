# Logging Infrastructure

This document describes the logging infrastructure and standards for the lit_law411-agent project.

## Overview

The application uses structured logging with [structlog](https://www.structlog.org/) for consistent, searchable, and analyzable logs. The logging system is designed to support both development and production environments with appropriate formatting and log levels.

## Features

- **Structured Logging**: JSON format in production, human-readable in development
- **Request ID Tracking**: Automatic request ID generation and tracking across the request lifecycle
- **Performance Monitoring**: Built-in performance metric logging
- **Security Event Logging**: Dedicated logging for security-related events
- **Audit Trail**: Comprehensive audit logging for data modifications
- **Error Tracking**: Integration with Sentry for error monitoring in production
- **Middleware Integration**: Automatic logging for all HTTP requests

## Configuration

### Environment Variables

```bash
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Environment (affects log formatting)
ENVIRONMENT=development

# Sentry DSN for error tracking (optional)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

### Setup

The logging system is automatically initialized when the application starts:

```python
from src.core.logging import setup_logging

# Initialize logging (done automatically in main.py)
setup_logging()
```

## Usage

### Basic Logging

```python
from src.core.logging import get_logger

logger = get_logger(__name__)

# Basic log messages
logger.debug("Debug information")
logger.info("Information message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical error")

# Structured logging with context
logger.info(
    "User action performed",
    user_id="123",
    action="login",
    ip_address="192.168.1.1",
    duration=1.5
)
```

### Request ID Tracking

Request IDs are automatically generated and tracked for all HTTP requests. You can also manually set request IDs:

```python
from src.core.logging import set_request_id, get_request_id, clear_request_id

# Set custom request ID
request_id = set_request_id("custom-req-123")

# Get current request ID
current_id = get_request_id()

# Clear request ID (done automatically after request)
clear_request_id()
```

### Performance Logging

```python
from src.core.logging import log_performance

# Log performance metrics
log_performance(
    operation="database_query",
    duration=0.5,
    query_type="SELECT",
    rows_returned=150
)
```

### Exception Logging

```python
from src.core.logging import log_exception

try:
    risky_operation()
except Exception as e:
    log_exception(e, {
        "operation": "risky_operation",
        "user_id": "123",
        "context": "additional context"
    })
    raise
```

### Security Event Logging

```python
from src.core.logging import log_security_event

log_security_event("suspicious_login", {
    "user_id": "123",
    "ip_address": "192.168.1.1",
    "user_agent": "suspicious-bot",
    "attempts": 5
})
```

### Audit Trail Logging

```python
from src.core.logging import log_audit_trail

log_audit_trail(
    action="create",
    resource="user",
    user_id="admin123",
    resource_id="user456",
    details="Created new user account"
)
```

## Decorators

### Function Call Logging

```python
from src.utils.logging_utils import log_function_calls

@log_function_calls(
    include_args=True,
    include_result=False,
    exclude_args=["password", "secret"]
)
def sensitive_function(username, password, data):
    return process_data(data)

# Usage automatically logs function calls
result = sensitive_function("user", "secret123", {"key": "value"})
```

### Method Call Logging

```python
from src.utils.logging_utils import log_method_calls

class UserService:
    @log_method_calls(include_args=True)
    def create_user(self, username, email):
        # Method implementation
        return user_id
```

### Database Operation Logging

```python
from src.utils.logging_utils import log_database_operations

@log_database_operations()
async def get_users():
    # Database operation implementation
    return users
```

## Context Managers

### Log Context

```python
from src.utils.logging_utils import LogContext

with LogContext(user_id="123", operation="data_processing") as logger:
    logger.info("Starting data processing")
    process_data()
    logger.info("Data processing completed")
```

### Time Operation

```python
from src.utils.logging_utils import time_operation

with time_operation("expensive_calculation"):
    result = expensive_calculation()
    # Automatically logs start, completion, and duration
```

## Middleware

The application includes three middleware components for automatic logging:

### LoggingMiddleware

Automatically logs all HTTP requests and responses:

```python
# Added automatically in main.py
app.add_middleware(LoggingMiddleware)
```

### SecurityMiddleware

Logs security events and adds security headers:

```python
# Added automatically in main.py
app.add_middleware(SecurityMiddleware)
```

### MetricsMiddleware

Collects and logs performance metrics:

```python
# Added automatically in main.py
app.add_middleware(MetricsMiddleware)
```

## Log Formats

### Development Format

Human-readable format with colors:

```
2025-01-13T10:30:45.123456 [INFO    ] src.main: Starting lit_law411-agent environment=development debug=False
2025-01-13T10:30:45.124000 [INFO    ] src.api.auth: User login successful user_id=123 duration=0.5
```

### Production Format

JSON format for log aggregation:

```json
{
  "timestamp": "2025-01-13T10:30:45.123456Z",
  "level": "info",
  "logger": "src.main",
  "message": "Starting lit_law411-agent",
  "environment": "production",
  "debug": false,
  "service": "lit_law411-agent",
  "version": "0.1.0",
  "request_id": "req-abc123"
}
```

## Error Tracking with Sentry

When Sentry is configured, errors are automatically sent to Sentry with context:

```python
# Automatic error tracking
logger.error("Database connection failed", extra={
    "database_url": "postgresql://...",
    "connection_timeout": 30
})

# Manual error capture
from src.core.sentry import capture_exception

try:
    risky_operation()
except Exception as e:
    capture_exception(e, operation="risky_operation", user_id="123")
    raise
```

## Best Practices

### 1. Use Appropriate Log Levels

- **DEBUG**: Detailed information for debugging
- **INFO**: General information about application flow
- **WARNING**: Something unexpected happened but application continues
- **ERROR**: Serious problem occurred, function failed
- **CRITICAL**: Very serious error, application may not continue

### 2. Include Context

Always include relevant context in log messages:

```python
# Good
logger.info("User authenticated", user_id="123", method="oauth", duration=1.2)

# Avoid
logger.info("User authenticated")
```

### 3. Use Structured Logging

Prefer structured data over string formatting:

```python
# Good
logger.info("Database query completed", 
    query_type="SELECT", 
    table="users", 
    duration=0.5,
    rows=42
)

# Avoid
logger.info(f"Database query SELECT on users took 0.5s and returned 42 rows")
```

### 4. Don't Log Sensitive Information

Never log passwords, tokens, or other sensitive data:

```python
# Good
logger.info("User login", user_id="123", method="password")

# NEVER DO THIS
logger.info("User login", user_id="123", password="secret123")
```

### 5. Use Decorators for Consistent Logging

Use provided decorators for consistent function/method logging:

```python
@log_function_calls(exclude_args=["password", "secret"])
def authenticate_user(username, password):
    pass
```

### 6. Log Performance Metrics

Log performance-critical operations:

```python
with time_operation("data_processing"):
    process_large_dataset()
```

## Monitoring and Alerting

### Log Aggregation

In production, logs should be collected by a log aggregation system like:

- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Grafana Loki**
- **AWS CloudWatch**
- **Google Cloud Logging**

### Alerting Rules

Set up alerts for:

- Error rate spikes
- Critical/fatal log messages
- Performance degradation
- Security events
- Application startup/shutdown

### Dashboards

Create dashboards for:

- Request volume and latency
- Error rates by endpoint
- User activity patterns
- System resource usage
- Security event monitoring

## Troubleshooting

### Common Issues

1. **Logs not appearing**: Check LOG_LEVEL setting
2. **JSON format in development**: Verify ENVIRONMENT setting
3. **Missing request IDs**: Ensure LoggingMiddleware is installed
4. **Sentry not working**: Check SENTRY_DSN configuration

### Debug Logging

Enable debug logging temporarily:

```bash
export LOG_LEVEL=DEBUG
```

Or in code:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

## Performance Considerations

- Log aggregation is asynchronous and shouldn't block request processing
- Sensitive data filtering happens before log output
- Request ID tracking uses context variables for thread safety
- JSON formatting is optimized for production log volume

## Examples

See `tests/unit/test_logging.py` for comprehensive examples of all logging features.