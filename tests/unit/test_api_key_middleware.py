"""Unit tests for API key middleware."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException, Request, status

from src.core.api_key_middleware import (
    get_api_key_from_request,
    get_current_user_from_api_key,
    get_current_user_flexible,
    get_current_user_api_key_only,
    get_current_user_any_auth,
    require_api_key_scope,
    require_any_auth_with_scope,
    APIKeyRateLimitMiddleware,
)
from src.core.api_key_utils import (
    APIKeyNotFoundError,
    APIKeyExpiredError,
    APIKeyInactiveError,
    APIKeyRateLimitError,
    APIKeyScopeError,
)
from src.models.sqlalchemy.api_key import APIKey
from src.models.sqlalchemy.user import User


class TestAPIKeyExtraction:
    """Test cases for API key extraction from requests."""
    
    @pytest.mark.asyncio
    async def test_get_api_key_from_authorization_header(self):
        """Test extracting API key from Authorization header."""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer llk_test_key_123"}
        request.query_params = {}
        
        api_key = await get_api_key_from_request(request)
        assert api_key == "llk_test_key_123"
    
    @pytest.mark.asyncio
    async def test_get_api_key_from_x_api_key_header(self):
        """Test extracting API key from X-API-Key header."""
        request = Mock(spec=Request)
        request.headers = {"X-API-Key": "llk_test_key_456"}
        request.query_params = {}
        
        api_key = await get_api_key_from_request(request)
        assert api_key == "llk_test_key_456"
    
    @pytest.mark.asyncio
    async def test_get_api_key_from_query_param(self):
        """Test extracting API key from query parameter."""
        request = Mock(spec=Request)
        request.headers = {}
        request.query_params = {"api_key": "llk_test_key_789"}
        
        api_key = await get_api_key_from_request(request)
        assert api_key == "llk_test_key_789"
    
    @pytest.mark.asyncio
    async def test_get_api_key_jwt_token_ignored(self):
        """Test that JWT tokens are ignored when looking for API keys."""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."}  # JWT token
        request.query_params = {}
        
        api_key = await get_api_key_from_request(request)
        assert api_key is None
    
    @pytest.mark.asyncio
    async def test_get_api_key_not_found(self):
        """Test when no API key is found."""
        request = Mock(spec=Request)
        request.headers = {}
        request.query_params = {}
        
        api_key = await get_api_key_from_request(request)
        assert api_key is None
    
    @pytest.mark.asyncio
    async def test_get_api_key_precedence(self):
        """Test API key extraction precedence (Authorization > X-API-Key > query param)."""
        request = Mock(spec=Request)
        request.headers = {
            "Authorization": "Bearer llk_auth_key",
            "X-API-Key": "llk_header_key"
        }
        request.query_params = {"api_key": "llk_query_key"}
        
        api_key = await get_api_key_from_request(request)
        assert api_key == "llk_auth_key"  # Authorization header takes precedence


class TestAPIKeyAuthentication:
    """Test cases for API key authentication."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_api_key_success(self):
        """Test successful API key authentication."""
        request = Mock(spec=Request)
        request.headers = {"X-API-Key": "llk_valid_key"}
        request.query_params = {}
        request.client = Mock()
        request.client.host = "127.0.0.1"
        
        mock_db = Mock()
        mock_api_key = Mock(spec=APIKey)
        mock_user = Mock(spec=User)
        
        with patch('src.core.api_key_middleware.get_api_key_from_request', return_value="llk_valid_key"), \
             patch('src.core.api_key_middleware.APIKeyManager') as mock_manager:
            
            mock_manager.validate_api_key = AsyncMock(return_value=(mock_api_key, mock_user))
            mock_manager.increment_api_key_usage = AsyncMock()
            
            result = await get_current_user_from_api_key(request, mock_db)
            
            assert result == (mock_user, mock_api_key)
            mock_manager.validate_api_key.assert_called_once_with(
                db=mock_db,
                api_key="llk_valid_key",
                required_scope=None,
                check_rate_limit=True
            )
            mock_manager.increment_api_key_usage.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_api_key_no_key(self):
        """Test API key authentication when no key provided."""
        request = Mock(spec=Request)
        request.headers = {}
        request.query_params = {}
        
        with patch('src.core.api_key_middleware.get_api_key_from_request', return_value=None):
            result = await get_current_user_from_api_key(request, Mock())
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_api_key_not_found(self):
        """Test API key authentication with non-existent key."""
        request = Mock(spec=Request)
        
        with patch('src.core.api_key_middleware.get_api_key_from_request', return_value="llk_invalid"), \
             patch('src.core.api_key_middleware.APIKeyManager') as mock_manager:
            
            mock_manager.validate_api_key = AsyncMock(side_effect=APIKeyNotFoundError("Not found"))
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_from_api_key(request, Mock())
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid API key" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_api_key_expired(self):
        """Test API key authentication with expired key."""
        request = Mock(spec=Request)
        
        with patch('src.core.api_key_middleware.get_api_key_from_request', return_value="llk_expired"), \
             patch('src.core.api_key_middleware.APIKeyManager') as mock_manager:
            
            mock_manager.validate_api_key = AsyncMock(side_effect=APIKeyExpiredError("Expired"))
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_from_api_key(request, Mock())
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "API key has expired" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_api_key_inactive(self):
        """Test API key authentication with inactive key."""
        request = Mock(spec=Request)
        
        with patch('src.core.api_key_middleware.get_api_key_from_request', return_value="llk_inactive"), \
             patch('src.core.api_key_middleware.APIKeyManager') as mock_manager:
            
            mock_manager.validate_api_key = AsyncMock(side_effect=APIKeyInactiveError("Inactive"))
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_from_api_key(request, Mock())
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "API key is inactive" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_api_key_rate_limited(self):
        """Test API key authentication with rate limiting."""
        request = Mock(spec=Request)
        
        with patch('src.core.api_key_middleware.get_api_key_from_request', return_value="llk_limited"), \
             patch('src.core.api_key_middleware.APIKeyManager') as mock_manager:
            
            mock_manager.validate_api_key = AsyncMock(
                side_effect=APIKeyRateLimitError("Rate limit exceeded")
            )
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_from_api_key(request, Mock())
            
            assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            assert "Rate limit exceeded" in exc_info.value.detail
            assert exc_info.value.headers["Retry-After"] == "60"
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_api_key_insufficient_scope(self):
        """Test API key authentication with insufficient scope."""
        request = Mock(spec=Request)
        
        with patch('src.core.api_key_middleware.get_api_key_from_request', return_value="llk_limited"), \
             patch('src.core.api_key_middleware.APIKeyManager') as mock_manager:
            
            mock_manager.validate_api_key = AsyncMock(
                side_effect=APIKeyScopeError("Missing scope: admin")
            )
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_from_api_key(request, Mock(), required_scope="admin")
            
            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
            assert "Missing scope: admin" in exc_info.value.detail


class TestFlexibleAuthentication:
    """Test cases for flexible authentication (API key + JWT fallback)."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_flexible_api_key_success(self):
        """Test flexible authentication with successful API key."""
        request = Mock(spec=Request)
        mock_user = Mock(spec=User)
        mock_api_key = Mock(spec=APIKey)
        
        with patch('src.core.api_key_middleware.get_current_user_from_api_key', 
                   return_value=(mock_user, mock_api_key)):
            
            result = await get_current_user_flexible(request, Mock())
            assert result == (mock_user, mock_api_key)
    
    @pytest.mark.asyncio
    async def test_get_current_user_flexible_jwt_fallback(self):
        """Test flexible authentication falling back to JWT."""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer jwt_token_here"}
        mock_user = Mock(spec=User)
        mock_user.email = "test@example.com"
        
        with patch('src.core.api_key_middleware.get_current_user_from_api_key', 
                   side_effect=HTTPException(status_code=401)), \
             patch('src.core.api_key_middleware.get_current_user', 
                   return_value=mock_user):
            
            result = await get_current_user_flexible(request, Mock())
            assert result == (mock_user, None)
    
    @pytest.mark.asyncio
    async def test_get_current_user_flexible_rate_limit_no_fallback(self):
        """Test that rate limit errors don't fall back to JWT."""
        request = Mock(spec=Request)
        
        with patch('src.core.api_key_middleware.get_current_user_from_api_key', 
                   side_effect=HTTPException(status_code=429)):
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_flexible(request, Mock())
            
            assert exc_info.value.status_code == 429
    
    @pytest.mark.asyncio
    async def test_get_current_user_flexible_no_auth(self):
        """Test flexible authentication with no authentication."""
        request = Mock(spec=Request)
        request.headers = {}
        
        with patch('src.core.api_key_middleware.get_current_user_from_api_key', return_value=None), \
             patch('src.core.api_key_middleware.get_current_user', return_value=None):
            
            result = await get_current_user_flexible(request, Mock())
            assert result is None


class TestRequiredAuthentication:
    """Test cases for required authentication functions."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_api_key_only_success(self):
        """Test API key only authentication success."""
        request = Mock(spec=Request)
        mock_user = Mock(spec=User)
        mock_api_key = Mock(spec=APIKey)
        
        with patch('src.core.api_key_middleware.get_current_user_from_api_key', 
                   return_value=(mock_user, mock_api_key)):
            
            result = await get_current_user_api_key_only(request, Mock())
            assert result == (mock_user, mock_api_key)
    
    @pytest.mark.asyncio
    async def test_get_current_user_api_key_only_no_key(self):
        """Test API key only authentication with no key."""
        request = Mock(spec=Request)
        
        with patch('src.core.api_key_middleware.get_current_user_from_api_key', return_value=None):
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_api_key_only(request, Mock())
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "API key authentication required" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_get_current_user_any_auth_success(self):
        """Test any authentication success."""
        request = Mock(spec=Request)
        mock_user = Mock(spec=User)
        mock_api_key = Mock(spec=APIKey)
        
        with patch('src.core.api_key_middleware.get_current_user_flexible', 
                   return_value=(mock_user, mock_api_key)):
            
            result = await get_current_user_any_auth(request, Mock())
            assert result == (mock_user, mock_api_key)
    
    @pytest.mark.asyncio
    async def test_get_current_user_any_auth_no_auth(self):
        """Test any authentication with no authentication."""
        request = Mock(spec=Request)
        
        with patch('src.core.api_key_middleware.get_current_user_flexible', return_value=None):
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_any_auth(request, Mock())
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Authentication required" in exc_info.value.detail


class TestAuthenticationDecorators:
    """Test cases for authentication decorators."""
    
    @pytest.mark.asyncio
    async def test_require_api_key_scope(self):
        """Test require API key scope decorator."""
        scope_checker = require_api_key_scope("admin")
        
        request = Mock(spec=Request)
        mock_user = Mock(spec=User)
        mock_api_key = Mock(spec=APIKey)
        
        with patch('src.core.api_key_middleware.get_current_user_api_key_only', 
                   return_value=(mock_user, mock_api_key)) as mock_auth:
            
            result = await scope_checker(request, Mock())
            assert result == (mock_user, mock_api_key)
            
            # Verify the required scope was passed
            mock_auth.assert_called_once()
            args, kwargs = mock_auth.call_args
            assert kwargs.get('required_scope') == "admin"
    
    @pytest.mark.asyncio
    async def test_require_any_auth_with_scope(self):
        """Test require any auth with scope decorator."""
        auth_checker = require_any_auth_with_scope("read")
        
        request = Mock(spec=Request)
        mock_user = Mock(spec=User)
        
        with patch('src.core.api_key_middleware.get_current_user_any_auth', 
                   return_value=(mock_user, None)) as mock_auth:
            
            result = await auth_checker(request, Mock())
            assert result == (mock_user, None)
            
            # Verify the required scope was passed
            mock_auth.assert_called_once()
            args, kwargs = mock_auth.call_args
            assert kwargs.get('required_scope') == "read"


class TestAPIKeyRateLimitMiddleware:
    """Test cases for API key rate limit middleware."""
    
    @pytest.mark.asyncio
    async def test_middleware_with_api_key(self):
        """Test middleware with API key request."""
        middleware = APIKeyRateLimitMiddleware()
        
        request = Mock(spec=Request)
        mock_response = Mock()
        mock_response.headers = {}
        
        # Mock the call_next function
        async def mock_call_next(request):
            return mock_response
        
        # Mock API key detection and database operations
        with patch('src.core.api_key_middleware.get_api_key_from_request', 
                   return_value="llk_test_key"), \
             patch('src.core.api_key_middleware.APIKeyManager') as mock_manager, \
             patch('src.core.api_key_middleware.SessionLocal') as mock_session_local:
            
            mock_manager.validate_api_key_format.return_value = True
            
            # Mock database session and API key
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mock_db.__enter__ = Mock(return_value=mock_db)
            mock_db.__exit__ = Mock(return_value=None)
            
            mock_api_key = Mock(spec=APIKey)
            mock_api_key.rate_limit_per_minute = 60
            mock_api_key.rate_limit_per_hour = 1000
            mock_api_key.rate_limit_per_day = 10000
            
            mock_manager.find_api_key_by_raw_key = AsyncMock(return_value=mock_api_key)
            mock_manager.get_api_key_rate_limit_status = AsyncMock(return_value={
                "remaining": {"this_minute": 50, "this_hour": 900, "today": 9000},
                "reset_times": {
                    "minute": Mock(timestamp=Mock(return_value=1234567890)),
                    "hour": Mock(timestamp=Mock(return_value=1234567890)),
                    "day": Mock(timestamp=Mock(return_value=1234567890))
                }
            })
            
            response = await middleware(request, mock_call_next)
            
            # Check that rate limit headers were added
            assert "X-RateLimit-Limit-Minute" in response.headers
            assert "X-RateLimit-Remaining-Minute" in response.headers
            assert response.headers["X-RateLimit-Limit-Minute"] == "60"
    
    @pytest.mark.asyncio
    async def test_middleware_without_api_key(self):
        """Test middleware without API key request."""
        middleware = APIKeyRateLimitMiddleware()
        
        request = Mock(spec=Request)
        mock_response = Mock()
        
        async def mock_call_next(request):
            return mock_response
        
        with patch('src.core.api_key_middleware.get_api_key_from_request', return_value=None):
            response = await middleware(request, mock_call_next)
            assert response == mock_response
    
    @pytest.mark.asyncio
    async def test_middleware_with_invalid_api_key(self):
        """Test middleware with invalid API key format."""
        middleware = APIKeyRateLimitMiddleware()
        
        request = Mock(spec=Request)
        mock_response = Mock()
        
        async def mock_call_next(request):
            return mock_response
        
        with patch('src.core.api_key_middleware.get_api_key_from_request', 
                   return_value="invalid_key"), \
             patch('src.core.api_key_middleware.APIKeyManager') as mock_manager:
            
            mock_manager.validate_api_key_format.return_value = False
            
            response = await middleware(request, mock_call_next)
            assert response == mock_response
    
    @pytest.mark.asyncio
    async def test_middleware_database_error(self):
        """Test middleware handling database errors gracefully."""
        middleware = APIKeyRateLimitMiddleware()
        
        request = Mock(spec=Request)
        mock_response = Mock()
        mock_response.headers = {}
        
        async def mock_call_next(request):
            return mock_response
        
        with patch('src.core.api_key_middleware.get_api_key_from_request', 
                   return_value="llk_test_key"), \
             patch('src.core.api_key_middleware.APIKeyManager') as mock_manager, \
             patch('src.core.api_key_middleware.SessionLocal') as mock_session_local:
            
            mock_manager.validate_api_key_format.return_value = True
            
            # Mock database error
            mock_session_local.side_effect = Exception("Database error")
            
            response = await middleware(request, mock_call_next)
            
            # Should continue without rate limit headers
            assert response == mock_response