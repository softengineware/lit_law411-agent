"""Integration tests for API key management endpoints."""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, Mock

from src.main import app
from src.db.database import get_db
from src.models.sqlalchemy.base import Base
from src.models.sqlalchemy.user import User
from src.models.sqlalchemy.api_key import APIKey
from src.core.security import hash_password, create_access_token


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_api_keys.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def setup_database():
    """Set up test database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_user():
    """Create test user."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="test@example.com",
            username="testuser",
            password_hash=hash_password("testpass123"),
            first_name="Test",
            last_name="User",
            is_active=True,
            is_verified=True,
            subscription_tier="premium"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture
def superuser():
    """Create test superuser."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="admin@example.com",
            username="admin",
            password_hash=hash_password("adminpass123"),
            first_name="Admin",
            last_name="User",
            is_active=True,
            is_verified=True,
            is_superuser=True,
            subscription_tier="enterprise"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers for test user."""
    token = create_access_token({"sub": test_user.email, "user_id": test_user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(superuser):
    """Create authentication headers for superuser."""
    token = create_access_token({"sub": superuser.email, "user_id": superuser.id})
    return {"Authorization": f"Bearer {token}"}


class TestAPIKeyCreation:
    """Test cases for API key creation."""
    
    def test_create_api_key_success(self, client, test_user, auth_headers, setup_database):
        """Test successful API key creation."""
        with patch('src.core.api_key_utils.cache') as mock_cache:
            mock_cache.set = Mock()
            
            payload = {
                "name": "Test API Key",
                "description": "Test description",
                "scopes": ["read", "write"],
                "expires_days": 30,
                "rate_limit_per_minute": 100,
                "rate_limit_per_hour": 5000,
                "rate_limit_per_day": 50000,
                "key_metadata": {"project": "test"}
            }
            
            response = client.post("/api/v1/api-keys", json=payload, headers=auth_headers)
            
            assert response.status_code == 201
            data = response.json()
            
            assert data["message"] == "API key created successfully"
            assert data["api_key"].startswith("llk_")
            assert data["key_info"]["name"] == "Test API Key"
            assert data["key_info"]["scopes"] == ["read", "write"]
            assert data["key_info"]["rate_limit_per_minute"] == 100
    
    def test_create_api_key_duplicate_name(self, client, test_user, auth_headers, setup_database):
        """Test creating API key with duplicate name."""
        # Create first API key
        db = TestingSessionLocal()
        try:
            api_key = APIKey(
                name="Duplicate Name",
                key_hash="hash1",
                key_prefix="llk_test",
                user_id=test_user.id
            )
            db.add(api_key)
            db.commit()
        finally:
            db.close()
        
        # Try to create another with same name
        payload = {
            "name": "Duplicate Name",
            "description": "Different description"
        }
        
        response = client.post("/api/v1/api-keys", json=payload, headers=auth_headers)
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    def test_create_api_key_max_keys_limit(self, client, test_user, auth_headers, setup_database):
        """Test API key creation hitting max keys limit."""
        # Create multiple API keys to hit the limit
        db = TestingSessionLocal()
        try:
            # Premium users get 20 keys, so create 20
            for i in range(20):
                api_key = APIKey(
                    name=f"Key {i}",
                    key_hash=f"hash{i}",
                    key_prefix=f"llk_key{i}",
                    user_id=test_user.id
                )
                db.add(api_key)
            db.commit()
        finally:
            db.close()
        
        # Try to create one more
        payload = {"name": "One Too Many"}
        
        response = client.post("/api/v1/api-keys", json=payload, headers=auth_headers)
        
        assert response.status_code == 400
        assert "Maximum number of API keys reached" in response.json()["detail"]
    
    def test_create_api_key_unauthorized(self, client, setup_database):
        """Test creating API key without authentication."""
        payload = {"name": "Test Key"}
        
        response = client.post("/api/v1/api-keys", json=payload)
        
        assert response.status_code == 401
    
    def test_create_api_key_invalid_scopes(self, client, test_user, auth_headers, setup_database):
        """Test creating API key with invalid scopes."""
        payload = {
            "name": "Test Key",
            "scopes": ["invalid_scope"]
        }
        
        response = client.post("/api/v1/api-keys", json=payload, headers=auth_headers)
        
        assert response.status_code == 422  # Validation error


class TestAPIKeyListing:
    """Test cases for listing API keys."""
    
    def test_list_api_keys_success(self, client, test_user, auth_headers, setup_database):
        """Test successful API key listing."""
        # Create test API keys
        db = TestingSessionLocal()
        try:
            for i in range(3):
                api_key = APIKey(
                    name=f"Test Key {i}",
                    key_hash=f"hash{i}",
                    key_prefix=f"llk_test{i}",
                    user_id=test_user.id,
                    is_active=True
                )
                db.add(api_key)
            db.commit()
        finally:
            db.close()
        
        response = client.get("/api/v1/api-keys", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 3
        assert len(data["api_keys"]) == 3
        assert data["page"] == 1
        assert data["page_size"] == 50
        
        # Verify no sensitive data is included
        for key_data in data["api_keys"]:
            assert "key_hash" not in key_data
            assert "name" in key_data
            assert "key_prefix" in key_data
    
    def test_list_api_keys_pagination(self, client, test_user, auth_headers, setup_database):
        """Test API key listing with pagination."""
        response = client.get("/api/v1/api-keys?page=1&page_size=2", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
    
    def test_list_api_keys_include_inactive(self, client, test_user, auth_headers, setup_database):
        """Test listing API keys including inactive ones."""
        # Create inactive API key
        db = TestingSessionLocal()
        try:
            api_key = APIKey(
                name="Inactive Key",
                key_hash="inactive_hash",
                key_prefix="llk_inact",
                user_id=test_user.id,
                is_active=False
            )
            db.add(api_key)
            db.commit()
        finally:
            db.close()
        
        # Without include_inactive
        response = client.get("/api/v1/api-keys", headers=auth_headers)
        data = response.json()
        inactive_count = sum(1 for key in data["api_keys"] if not key["is_active"])
        assert inactive_count == 0
        
        # With include_inactive
        response = client.get("/api/v1/api-keys?include_inactive=true", headers=auth_headers)
        data = response.json()
        inactive_count = sum(1 for key in data["api_keys"] if not key["is_active"])
        assert inactive_count > 0


class TestAPIKeyRetrieval:
    """Test cases for retrieving individual API keys."""
    
    def test_get_api_key_success(self, client, test_user, auth_headers, setup_database):
        """Test successful API key retrieval."""
        # Create test API key
        db = TestingSessionLocal()
        api_key = None
        try:
            api_key = APIKey(
                name="Test Key",
                key_hash="test_hash",
                key_prefix="llk_test",
                user_id=test_user.id,
                scopes=["read", "write"]
            )
            db.add(api_key)
            db.commit()
            db.refresh(api_key)
        finally:
            db.close()
        
        response = client.get(f"/api/v1/api-keys/{api_key.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Test Key"
        assert data["scopes"] == ["read", "write"]
        assert "key_hash" not in data
    
    def test_get_api_key_not_found(self, client, test_user, auth_headers, setup_database):
        """Test retrieving non-existent API key."""
        response = client.get("/api/v1/api-keys/nonexistent-id", headers=auth_headers)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_get_api_key_other_user(self, client, test_user, auth_headers, setup_database):
        """Test retrieving API key belonging to another user."""
        # Create another user and their API key
        db = TestingSessionLocal()
        try:
            other_user = User(
                email="other@example.com",
                username="other",
                password_hash=hash_password("pass123"),
                is_active=True
            )
            db.add(other_user)
            db.commit()
            db.refresh(other_user)
            
            api_key = APIKey(
                name="Other User Key",
                key_hash="other_hash",
                key_prefix="llk_other",
                user_id=other_user.id
            )
            db.add(api_key)
            db.commit()
            db.refresh(api_key)
            
            # Try to access with test_user's token
            response = client.get(f"/api/v1/api-keys/{api_key.id}", headers=auth_headers)
            
            assert response.status_code == 404  # Should not find it
        finally:
            db.close()


class TestAPIKeyUpdating:
    """Test cases for updating API keys."""
    
    def test_update_api_key_success(self, client, test_user, auth_headers, setup_database):
        """Test successful API key update."""
        # Create test API key
        db = TestingSessionLocal()
        api_key = None
        try:
            api_key = APIKey(
                name="Original Name",
                key_hash="test_hash",
                key_prefix="llk_test",
                user_id=test_user.id
            )
            db.add(api_key)
            db.commit()
            db.refresh(api_key)
        finally:
            db.close()
        
        payload = {
            "name": "Updated Name",
            "description": "Updated description",
            "scopes": ["read"],
            "is_active": True
        }
        
        response = client.put(f"/api/v1/api-keys/{api_key.id}", json=payload, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        assert data["scopes"] == ["read"]
    
    def test_update_api_key_duplicate_name(self, client, test_user, auth_headers, setup_database):
        """Test updating API key with duplicate name."""
        db = TestingSessionLocal()
        try:
            # Create two API keys
            api_key1 = APIKey(
                name="Key One",
                key_hash="hash1",
                key_prefix="llk_one",
                user_id=test_user.id
            )
            api_key2 = APIKey(
                name="Key Two",
                key_hash="hash2",
                key_prefix="llk_two",
                user_id=test_user.id
            )
            db.add_all([api_key1, api_key2])
            db.commit()
            db.refresh(api_key1)
            db.refresh(api_key2)
            
            # Try to update key2 with key1's name
            payload = {"name": "Key One"}
            response = client.put(f"/api/v1/api-keys/{api_key2.id}", json=payload, headers=auth_headers)
            
            assert response.status_code == 400
            assert "already exists" in response.json()["detail"]
        finally:
            db.close()


class TestAPIKeyRotation:
    """Test cases for API key rotation."""
    
    def test_rotate_api_key_success(self, client, test_user, auth_headers, setup_database):
        """Test successful API key rotation."""
        # Create test API key
        db = TestingSessionLocal()
        api_key = None
        try:
            api_key = APIKey(
                name="Test Key",
                key_hash="old_hash",
                key_prefix="llk_old",
                user_id=test_user.id
            )
            db.add(api_key)
            db.commit()
            db.refresh(api_key)
        finally:
            db.close()
        
        response = client.post(f"/api/v1/api-keys/{api_key.id}/rotate", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "API key rotated successfully"
        assert data["new_api_key"].startswith("llk_")
        assert data["new_api_key"] != "llk_old"  # Should be different
        assert data["key_info"]["key_prefix"] != "llk_old"  # Should be different


class TestAPIKeyDeletion:
    """Test cases for API key deletion."""
    
    def test_delete_api_key_success(self, client, test_user, auth_headers, setup_database):
        """Test successful API key deletion."""
        # Create test API key
        db = TestingSessionLocal()
        api_key = None
        try:
            api_key = APIKey(
                name="To Be Deleted",
                key_hash="delete_hash",
                key_prefix="llk_del",
                user_id=test_user.id
            )
            db.add(api_key)
            db.commit()
            db.refresh(api_key)
        finally:
            db.close()
        
        with patch('src.core.rate_limiter.api_key_rate_limiter') as mock_limiter:
            mock_limiter.reset_api_key_limits = Mock(return_value=True)
            
            response = client.delete(f"/api/v1/api-keys/{api_key.id}", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert "deleted successfully" in data["message"]
            assert data["deleted_key_id"] == api_key.id
            
            # Verify it's actually deleted
            response = client.get(f"/api/v1/api-keys/{api_key.id}", headers=auth_headers)
            assert response.status_code == 404


class TestAPIKeyUsageAndLimits:
    """Test cases for API key usage and rate limit endpoints."""
    
    def test_get_api_key_usage(self, client, test_user, auth_headers, setup_database):
        """Test getting API key usage statistics."""
        # Create test API key with usage data
        db = TestingSessionLocal()
        api_key = None
        try:
            api_key = APIKey(
                name="Usage Key",
                key_hash="usage_hash",
                key_prefix="llk_usage",
                user_id=test_user.id,
                total_requests=100,
                requests_today=10,
                requests_this_hour=5,
                requests_this_minute=2,
                rate_limit_per_minute=60,
                rate_limit_per_hour=1000,
                rate_limit_per_day=10000
            )
            db.add(api_key)
            db.commit()
            db.refresh(api_key)
        finally:
            db.close()
        
        response = client.get(f"/api/v1/api-keys/{api_key.id}/usage", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_requests"] == 100
        assert data["requests_today"] == 10
        assert data["remaining_minute"] == 58  # 60 - 2
        assert data["remaining_hour"] == 995   # 1000 - 5
        assert data["remaining_day"] == 9990   # 10000 - 10
    
    def test_get_api_key_rate_limit(self, client, test_user, auth_headers, setup_database):
        """Test getting API key rate limit information."""
        # Create test API key
        db = TestingSessionLocal()
        api_key = None
        try:
            api_key = APIKey(
                name="Rate Limit Key",
                key_hash="rl_hash",
                key_prefix="llk_rl",
                user_id=test_user.id,
                rate_limit_per_minute=60,
                rate_limit_per_hour=1000,
                rate_limit_per_day=10000
            )
            db.add(api_key)
            db.commit()
            db.refresh(api_key)
        finally:
            db.close()
        
        with patch('src.core.api_key_utils.APIKeyManager.get_api_key_rate_limit_status') as mock_status:
            mock_status.return_value = {
                "remaining": {"this_minute": 60, "this_hour": 1000, "today": 10000},
                "reset_times": {
                    "minute": datetime.now(timezone.utc) + timedelta(seconds=30),
                    "hour": datetime.now(timezone.utc) + timedelta(minutes=30),
                    "day": datetime.now(timezone.utc) + timedelta(hours=12)
                }
            }
            
            response = client.get(f"/api/v1/api-keys/{api_key.id}/rate-limit", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["limit_per_minute"] == 60
            assert data["limit_per_hour"] == 1000
            assert data["limit_per_day"] == 10000
            assert data["remaining_minute"] == 60
            assert "reset_minute" in data


class TestAdminEndpoints:
    """Test cases for admin-only endpoints."""
    
    def test_admin_list_all_api_keys(self, client, superuser, admin_headers, setup_database):
        """Test admin endpoint to list all API keys."""
        response = client.get("/api/v1/api-keys/admin/all", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "api_keys" in data
        assert "total" in data
    
    def test_admin_list_all_api_keys_unauthorized(self, client, test_user, auth_headers, setup_database):
        """Test admin endpoint with non-admin user."""
        response = client.get("/api/v1/api-keys/admin/all", headers=auth_headers)
        
        assert response.status_code == 403
        assert "Superuser privileges required" in response.json()["detail"]
    
    def test_admin_reset_api_key_limits(self, client, superuser, admin_headers, setup_database):
        """Test admin endpoint to reset API key limits."""
        # Create test API key
        db = TestingSessionLocal()
        api_key = None
        try:
            api_key = APIKey(
                name="Admin Test Key",
                key_hash="admin_hash",
                key_prefix="llk_admin",
                user_id=superuser.id
            )
            db.add(api_key)
            db.commit()
            db.refresh(api_key)
        finally:
            db.close()
        
        with patch('src.core.rate_limiter.api_key_rate_limiter') as mock_limiter:
            mock_limiter.reset_api_key_limits = Mock(return_value=True)
            
            response = client.post(f"/api/v1/api-keys/admin/{api_key.id}/reset-limits", headers=admin_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert "reset" in data["message"]