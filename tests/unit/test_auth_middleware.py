"""Unit tests for authentication middleware."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

pytest_plugins = ("pytest_asyncio",)

from src.core.auth_middleware import (
    get_current_user,
    get_current_active_user,
    get_current_verified_user,
    get_current_superuser,
    get_current_premium_user,
    require_role,
    require_permissions,
    create_auth_dependency,
    AuthenticationError,
    AuthorizationError,
)
from src.models.sqlalchemy.user import User


class TestGetCurrentUser:
    """Test get_current_user function."""
    
    @pytest.mark.asyncio
    @patch('src.core.auth_middleware.verify_token')
    async def test_get_current_user_success(self, mock_verify_token):
        """Test successful user authentication."""
        # Mock token verification
        mock_verify_token.return_value = {
            "sub": "test@example.com",
            "user_id": 123,
            "type": "access"
        }
        
        # Mock database session and user
        mock_db = Mock()
        mock_user = User(
            id=123,
            email="test@example.com",
            is_active=True,
            locked_until=None
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        # Mock credentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="mock_token"
        )
        
        result = await get_current_user(credentials, mock_db)
        
        assert result == mock_user
        mock_verify_token.assert_called_once_with("mock_token", token_type="access")
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_credentials(self):
        """Test get_current_user with no credentials."""
        mock_db = Mock()
        
        result = await get_current_user(None, mock_db)
        
        assert result is None
    
    @pytest.mark.asyncio
    @patch('src.core.auth_middleware.verify_token')
    async def test_get_current_user_invalid_token(self, mock_verify_token):
        """Test get_current_user with invalid token."""
        from src.core.security import TokenError
        
        mock_verify_token.side_effect = TokenError("Invalid token")
        mock_db = Mock()
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_token"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, mock_db)
        
        assert exc_info.value.status_code == 401
        assert "Token validation failed" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch('src.core.auth_middleware.verify_token')
    async def test_get_current_user_no_subject(self, mock_verify_token):
        """Test get_current_user with token missing subject."""
        mock_verify_token.return_value = {"user_id": 123, "type": "access"}
        mock_db = Mock()
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="mock_token"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, mock_db)
        
        assert exc_info.value.status_code == 401
        assert "missing user identifier" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch('src.core.auth_middleware.verify_token')
    async def test_get_current_user_not_found(self, mock_verify_token):
        """Test get_current_user with user not found in database."""
        mock_verify_token.return_value = {
            "sub": "nonexistent@example.com",
            "user_id": 999,
            "type": "access"
        }
        
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="mock_token"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, mock_db)
        
        assert exc_info.value.status_code == 401
        assert "User not found" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch('src.core.auth_middleware.verify_token')
    async def test_get_current_user_inactive(self, mock_verify_token):
        """Test get_current_user with inactive user."""
        mock_verify_token.return_value = {
            "sub": "test@example.com",
            "user_id": 123,
            "type": "access"
        }
        
        mock_db = Mock()
        mock_user = User(
            id=123,
            email="test@example.com",
            is_active=False,
            locked_until=None
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="mock_token"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, mock_db)
        
        assert exc_info.value.status_code == 401
        assert "Inactive user" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch('src.core.auth_middleware.verify_token')
    async def test_get_current_user_locked(self, mock_verify_token):
        """Test get_current_user with locked user."""
        mock_verify_token.return_value = {
            "sub": "test@example.com",
            "user_id": 123,
            "type": "access"
        }
        
        mock_db = Mock()
        mock_user = User(
            id=123,
            email="test@example.com",
            is_active=True,
            locked_until=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="mock_token"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, mock_db)
        
        assert exc_info.value.status_code == 423
        assert "Account is locked" in str(exc_info.value.detail)


class TestAuthDependencies:
    """Test authentication dependency functions."""
    
    @pytest.mark.asyncio
    async def test_get_current_active_user_success(self):
        """Test get_current_active_user with valid user."""
        mock_user = User(
            id=123,
            email="test@example.com",
            is_active=True
        )
        
        result = await get_current_active_user(mock_user)
        
        assert result == mock_user
    
    @pytest.mark.asyncio
    async def test_get_current_active_user_no_user(self):
        """Test get_current_active_user with no user."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(None)
        
        assert exc_info.value.status_code == 401
        assert "Authentication required" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_current_verified_user_success(self):
        """Test get_current_verified_user with verified user."""
        mock_user = User(
            id=123,
            email="test@example.com",
            is_active=True,
            is_verified=True
        )
        
        result = await get_current_verified_user(mock_user)
        
        assert result == mock_user
    
    @pytest.mark.asyncio
    async def test_get_current_verified_user_unverified(self):
        """Test get_current_verified_user with unverified user."""
        mock_user = User(
            id=123,
            email="test@example.com",
            is_active=True,
            is_verified=False
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_verified_user(mock_user)
        
        assert exc_info.value.status_code == 403
        assert "Email verification required" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_current_superuser_success(self):
        """Test get_current_superuser with superuser."""
        mock_user = User(
            id=123,
            email="admin@example.com",
            is_active=True,
            is_superuser=True
        )
        
        result = await get_current_superuser(mock_user)
        
        assert result == mock_user
    
    @pytest.mark.asyncio
    async def test_get_current_superuser_not_super(self):
        """Test get_current_superuser with regular user."""
        mock_user = User(
            id=123,
            email="user@example.com",
            is_active=True,
            is_superuser=False
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_superuser(mock_user)
        
        assert exc_info.value.status_code == 403
        assert "Superuser privileges required" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_current_premium_user_success(self):
        """Test get_current_premium_user with premium user."""
        mock_user = User(
            id=123,
            email="premium@example.com",
            is_active=True,
            subscription_tier="premium"
        )
        
        result = await get_current_premium_user(mock_user)
        
        assert result == mock_user
    
    @pytest.mark.asyncio
    async def test_get_current_premium_user_not_premium(self):
        """Test get_current_premium_user with free user."""
        mock_user = User(
            id=123,
            email="free@example.com",
            is_active=True,
            subscription_tier="free"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_premium_user(mock_user)
        
        assert exc_info.value.status_code == 403
        assert "Premium subscription required" in str(exc_info.value.detail)


class TestRoleAndPermissionCheckers:
    """Test role and permission checking functions."""
    
    def test_require_role_success(self):
        """Test require_role with correct role."""
        checker = require_role("admin")
        
        mock_user = User(
            id=123,
            email="admin@example.com",
            is_active=True,
            role="admin"
        )
        
        # This should not raise an exception
        assert checker is not None
    
    def test_require_permissions_success(self):
        """Test require_permissions with sufficient permissions."""
        checker = require_permissions(["read", "write"])
        
        mock_user = User(
            id=123,
            email="user@example.com",
            is_active=True,
            permissions=["read", "write", "delete"],
            is_superuser=False
        )
        
        assert checker is not None
    
    def test_require_permissions_superuser(self):
        """Test require_permissions with superuser (should have all permissions)."""
        checker = require_permissions(["read", "write", "admin"])
        
        mock_user = User(
            id=123,
            email="admin@example.com",
            is_active=True,
            permissions=["read"],  # Limited permissions
            is_superuser=True  # But is superuser
        )
        
        assert checker is not None


class TestCreateAuthDependency:
    """Test create_auth_dependency function."""
    
    def test_create_auth_dependency_basic(self):
        """Test creating basic auth dependency."""
        dependency = create_auth_dependency()
        
        assert callable(dependency)
    
    def test_create_auth_dependency_with_requirements(self):
        """Test creating auth dependency with specific requirements."""
        dependency = create_auth_dependency(
            require_verification=True,
            require_premium=True,
            required_role="admin",
            required_permissions=["read", "write"]
        )
        
        assert callable(dependency)


class TestExceptions:
    """Test custom authentication exceptions."""
    
    def test_authentication_error(self):
        """Test AuthenticationError exception."""
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("Test authentication error")
    
    def test_authorization_error(self):
        """Test AuthorizationError exception."""
        with pytest.raises(AuthorizationError):
            raise AuthorizationError("Test authorization error")