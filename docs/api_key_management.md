# API Key Management System

This document provides comprehensive information about the API Key Management system implemented in the lit_law411-agent project.

## Overview

The API Key Management system provides secure, scalable authentication for the lit_law411-agent API as an alternative to JWT token authentication. It includes features for key generation, validation, rate limiting, usage tracking, and administrative management.

## Features

- **Secure API Key Generation**: Cryptographically secure API keys with custom prefix
- **Flexible Authentication**: Works alongside JWT authentication with automatic fallback
- **Advanced Rate Limiting**: Redis-based distributed rate limiting with configurable limits
- **Usage Tracking**: Comprehensive analytics and usage statistics
- **Key Rotation**: Secure key rotation mechanism
- **Scope-based Permissions**: Fine-grained access control with scopes
- **Admin Management**: Administrative endpoints for key oversight
- **Multi-tier Support**: Different limits based on subscription tiers

## API Key Format

API keys follow this format:
```
llk_[random_32_characters]
```

- **Prefix**: `llk_` (lit law411 key)
- **Random Part**: 32 cryptographically secure random characters
- **Total Length**: ~36 characters
- **Example**: `llk_xY9kL2mN8pQr5tUvWx1zA3bC6dE9fG2h`

## Authentication Methods

### API Key Headers

API keys can be provided in three ways (in order of precedence):

1. **Authorization Header** (recommended):
   ```http
   Authorization: Bearer llk_xY9kL2mN8pQr5tUvWx1zA3bC6dE9fG2h
   ```

2. **X-API-Key Header**:
   ```http
   X-API-Key: llk_xY9kL2mN8pQr5tUvWx1zA3bC6dE9fG2h
   ```

3. **Query Parameter** (least secure):
   ```http
   GET /api/v1/content?api_key=llk_xY9kL2mN8pQr5tUvWx1zA3bC6dE9fG2h
   ```

### Flexible Authentication

The system supports flexible authentication that tries API key first, then falls back to JWT:

- If a request includes an API key, it will be validated
- If API key validation fails (except for rate limits), the system falls back to JWT
- Rate limit errors do not trigger JWT fallback to prevent circumvention

## Database Schema

### API Key Model

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Key Information
    name VARCHAR(255) NOT NULL,
    description TEXT,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    key_prefix VARCHAR(8) NOT NULL,
    
    -- User Association
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Status and Lifecycle
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    last_used_ip VARCHAR(45),
    
    -- Permissions and Scopes
    scopes JSON,
    
    -- Rate Limiting
    rate_limit_per_minute INTEGER DEFAULT 60,
    rate_limit_per_hour INTEGER DEFAULT 1000,
    rate_limit_per_day INTEGER DEFAULT 10000,
    
    -- Usage Statistics
    total_requests INTEGER DEFAULT 0,
    requests_today INTEGER DEFAULT 0,
    requests_this_hour INTEGER DEFAULT 0,
    requests_this_minute INTEGER DEFAULT 0,
    
    -- Metadata
    user_agent VARCHAR(512),
    key_metadata JSON
);
```

## API Endpoints

### User Endpoints

#### Create API Key
```http
POST /api/v1/api-keys
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
    "name": "My API Key",
    "description": "API key for my application",
    "scopes": ["read", "write"],
    "expires_days": 90,
    "rate_limit_per_minute": 100,
    "rate_limit_per_hour": 5000,
    "rate_limit_per_day": 50000,
    "key_metadata": {
        "project": "my-project",
        "environment": "production"
    }
}
```

Response:
```json
{
    "message": "API key created successfully",
    "api_key": "llk_xY9kL2mN8pQr5tUvWx1zA3bC6dE9fG2h",
    "key_info": {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "My API Key",
        "key_prefix": "llk_xY9k",
        "scopes": ["read", "write"],
        "rate_limit_per_minute": 100,
        "is_active": true,
        "created_at": "2024-01-01T12:00:00Z"
    }
}
```

#### List API Keys
```http
GET /api/v1/api-keys?page=1&page_size=50&include_inactive=false
Authorization: Bearer <jwt_token>
```

#### Get API Key Details
```http
GET /api/v1/api-keys/{key_id}
Authorization: Bearer <jwt_token>
```

#### Update API Key
```http
PUT /api/v1/api-keys/{key_id}
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
    "name": "Updated Name",
    "scopes": ["read"],
    "is_active": false
}
```

#### Rotate API Key
```http
POST /api/v1/api-keys/{key_id}/rotate
Authorization: Bearer <jwt_token>
```

#### Delete API Key
```http
DELETE /api/v1/api-keys/{key_id}
Authorization: Bearer <jwt_token>
```

#### Get Usage Statistics
```http
GET /api/v1/api-keys/{key_id}/usage
Authorization: Bearer <jwt_token>
```

#### Get Rate Limit Info
```http
GET /api/v1/api-keys/{key_id}/rate-limit
Authorization: Bearer <jwt_token>
```

### Admin Endpoints

#### List All API Keys (Admin)
```http
GET /api/v1/api-keys/admin/all?user_id=<user_id>&include_inactive=true
Authorization: Bearer <admin_jwt_token>
```

#### Reset API Key Limits (Admin)
```http
POST /api/v1/api-keys/admin/{key_id}/reset-limits
Authorization: Bearer <admin_jwt_token>
```

## Rate Limiting

### Rate Limit Tiers

Based on user subscription tier:

| Tier | Per Minute | Per Hour | Per Day | Max Keys |
|------|------------|----------|---------|----------|
| Free | 10 | 100 | 1,000 | 2 |
| Basic | 30 | 500 | 5,000 | 5 |
| Premium | 100 | 5,000 | 50,000 | 20 |
| Enterprise | 100 | 5,000 | 50,000 | 20 |
| Superuser | 100 | 5,000 | 50,000 | 100 |

### Rate Limit Headers

API responses include rate limit information:

```http
X-RateLimit-Limit-Minute: 100
X-RateLimit-Limit-Hour: 5000
X-RateLimit-Limit-Day: 50000
X-RateLimit-Remaining-Minute: 95
X-RateLimit-Remaining-Hour: 4950
X-RateLimit-Remaining-Day: 49500
X-RateLimit-Reset-Minute: 1704110460
X-RateLimit-Reset-Hour: 1704110460
X-RateLimit-Reset-Day: 1704110460
```

### Rate Limit Responses

When rate limited:
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
Content-Type: application/json

{
    "detail": "Rate limit exceeded: too many requests per minute"
}
```

## Scopes and Permissions

### Available Scopes

- `*`: All permissions (wildcard)
- `read`: Read access to resources
- `write`: Write access to resources
- `admin`: Administrative operations
- `content:read`: Read content data
- `content:write`: Create/update content
- `search:read`: Perform searches
- `user:read`: Read user information
- `user:write`: Update user information
- `analytics:read`: Access analytics data

### Scope Validation

Scopes are validated during API key creation and when accessing protected endpoints:

```python
# Require specific scope
@router.get("/admin/users")
async def list_users(
    current_user_and_key = Depends(require_api_key_scope("admin"))
):
    pass

# Require any authentication with optional scope
@router.get("/content")
async def get_content(
    current_user_and_key = Depends(require_any_auth_with_scope("content:read"))
):
    pass
```

## Security Features

### Key Storage

- API keys are **never stored in plain text**
- Keys are hashed using SHA-256 before storage
- Only the first 8 characters (prefix) are stored for identification
- Original key is only returned once during creation/rotation

### Validation

- Format validation ensures keys match expected pattern
- Active status and expiration checks
- User account validation (active, not locked)
- Scope verification for protected endpoints

### Rate Limiting

- Redis-based sliding window algorithm
- Distributed rate limiting across multiple instances
- Multiple time windows (minute, hour, day)
- Per-key limits with subscription tier enforcement

### Audit Trail

- Comprehensive usage tracking
- IP address and user agent logging
- Request timestamps and counters
- Administrative action logging

## Usage Examples

### Python Client

```python
import requests

# Using API key authentication
headers = {
    "Authorization": "Bearer llk_xY9kL2mN8pQr5tUvWx1zA3bC6dE9fG2h",
    "Content-Type": "application/json"
}

response = requests.get(
    "https://api.law411.com/api/v1/content",
    headers=headers
)

# Check rate limit headers
print(f"Remaining requests this minute: {response.headers.get('X-RateLimit-Remaining-Minute')}")
```

### cURL

```bash
# Create API key
curl -X POST https://api.law411.com/api/v1/api-keys \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production API Key",
    "scopes": ["read", "write"],
    "rate_limit_per_minute": 100
  }'

# Use API key
curl -X GET https://api.law411.com/api/v1/content \
  -H "Authorization: Bearer llk_xY9kL2mN8pQr5tUvWx1zA3bC6dE9fG2h"
```

### JavaScript/TypeScript

```typescript
class APIClient {
    constructor(private apiKey: string, private baseUrl: string) {}

    async makeRequest(endpoint: string, options: RequestInit = {}) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            ...options,
            headers: {
                'Authorization': `Bearer ${this.apiKey}`,
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        // Check rate limits
        const remaining = response.headers.get('X-RateLimit-Remaining-Minute');
        if (remaining && parseInt(remaining) < 10) {
            console.warn('Approaching rate limit');
        }

        return response;
    }
}

const client = new APIClient('llk_xY9kL2mN8pQr5tUvWx1zA3bC6dE9fG2h', 'https://api.law411.com');
```

## Best Practices

### Key Management

1. **Rotate Keys Regularly**: Rotate API keys every 90 days or when compromised
2. **Use Descriptive Names**: Give keys meaningful names for easy identification
3. **Limit Scopes**: Only grant necessary permissions (principle of least privilege)
4. **Monitor Usage**: Regularly check usage statistics and unusual patterns
5. **Secure Storage**: Store keys securely in environment variables or key management systems

### Rate Limiting

1. **Implement Backoff**: Use exponential backoff when hitting rate limits
2. **Monitor Headers**: Check rate limit headers to avoid hitting limits
3. **Distribute Load**: Spread requests evenly over time
4. **Cache Results**: Cache API responses to reduce request volume

### Security

1. **Use HTTPS**: Always use HTTPS in production
2. **Validate Responses**: Verify API responses and handle errors gracefully
3. **Log Securely**: Never log API keys in plain text
4. **Revoke Unused Keys**: Delete API keys that are no longer needed
5. **Monitor for Abuse**: Set up alerts for unusual usage patterns

## Troubleshooting

### Common Issues

#### 401 Unauthorized
- Check API key format (should start with `llk_`)
- Verify key is active and not expired
- Ensure user account is active

#### 403 Forbidden
- Check if API key has required scope
- Verify user has necessary permissions
- Check if endpoint requires specific role

#### 429 Too Many Requests
- Check rate limit headers
- Implement exponential backoff
- Consider upgrading subscription tier

#### 404 Not Found
- Verify API key belongs to authenticated user
- Check if key was deleted
- Ensure correct key ID in URL

### Debugging

Enable debug logging to trace API key validation:

```python
import logging
logging.getLogger('src.core.api_key_middleware').setLevel(logging.DEBUG)
```

Check rate limit status:
```http
GET /api/v1/api-keys/{key_id}/rate-limit
```

View usage statistics:
```http
GET /api/v1/api-keys/{key_id}/usage
```

## Performance Considerations

### Redis Configuration

- Use Redis cluster for high availability
- Configure appropriate memory limits
- Set up monitoring for Redis performance

### Database Optimization

- Index on `key_hash` for fast lookups
- Index on `user_id` for user queries
- Consider partitioning for large datasets

### Caching

- Cache API key validation results (short TTL)
- Cache rate limit counters in Redis
- Use CDN for static responses

## Migration and Deployment

### Database Migration

Run the Alembic migration to create the API key table:

```bash
alembic upgrade head
```

### Environment Variables

Add required environment variables:

```bash
# Redis for rate limiting
REDIS_URL=redis://localhost:6379

# Rate limits
RATE_LIMIT_ANONYMOUS=10
RATE_LIMIT_AUTHENTICATED=100
RATE_LIMIT_PREMIUM=1000
```

### Monitoring

Set up monitoring for:
- API key creation/deletion events
- Rate limit violations
- Unusual usage patterns
- Failed authentication attempts

## Support and Maintenance

### Regular Tasks

- Monitor API key usage trends
- Clean up expired keys
- Review and update rate limits
- Audit security practices

### Emergency Procedures

#### Key Compromise
1. Immediately revoke compromised key
2. Generate new key for user
3. Investigate usage logs
4. Update security measures

#### Rate Limit Issues
1. Check Redis connectivity
2. Review rate limit configurations
3. Consider temporary limit increases
4. Investigate abuse patterns

For additional support, refer to the main project documentation or contact the development team.