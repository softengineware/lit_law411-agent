"""Integration tests for authentication endpoints."""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from src.main import app
from src.db.database import get_db
from src.models.sqlalchemy.base import BaseModel
from src.models.sqlalchemy.user import User
from src.core.security import hash_password, generate_email_verification_token


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_auth.db"
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
client = TestClient(app)


@pytest.fixture(scope="module")
def setup_database():
    """Set up test database."""
    BaseModel.metadata.create_all(bind=engine)
    yield
    BaseModel.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provide database session for tests."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user_data():
    """Provide test user data."""
    return {
        "email": "test@example.com",
        "password": "TestPassword123!",
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User",
        "organization": "Test Corp",
        "job_title": "Tester"
    }


@pytest.fixture
def existing_user(db_session):
    """Create an existing user in the database."""
    user = User(
        email="existing@example.com",
        username="existinguser",
        password_hash=hash_password("ExistingPassword123!"),
        first_name="Existing",
        last_name="User",
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def unverified_user(db_session):
    """Create an unverified user in the database."""
    verification_token = generate_email_verification_token()
    user = User(
        email="unverified@example.com",
        username="unverifieduser",
        password_hash=hash_password("UnverifiedPassword123!"),
        first_name="Unverified",
        last_name="User",
        is_active=True,
        is_verified=False,
        email_verification_token=verification_token,
        email_verification_expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestUserRegistration:
    """Test user registration endpoint."""
    
    @patch('src.core.config.get_settings')
    def test_register_user_success(self, mock_settings, setup_database, test_user_data):
        """Test successful user registration."""
        mock_settings.return_value.jwt_secret_key = "test_secret"
        
        response = client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "User registered successfully. Please check your email for verification."
        assert data["user"]["email"] == test_user_data["email"]
        assert data["user"]["username"] == test_user_data["username"]
        assert data["user"]["is_verified"] is False
        assert data["verification_required"] is True
    
    def test_register_user_duplicate_email(self, setup_database, existing_user, test_user_data):
        """Test registration with duplicate email."""
        test_user_data["email"] = existing_user.email
        
        response = client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 400
        data = response.json()
        assert "already exists" in data["detail"]
    
    def test_register_user_duplicate_username(self, setup_database, existing_user, test_user_data):
        """Test registration with duplicate username."""
        test_user_data["username"] = existing_user.username
        
        response = client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 400
        data = response.json()
        assert "already taken" in data["detail"]
    
    def test_register_user_weak_password(self, setup_database, test_user_data):
        """Test registration with weak password."""
        test_user_data["password"] = "weak"
        
        response = client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "validation" in str(data).lower()
    
    def test_register_user_invalid_email(self, setup_database, test_user_data):
        """Test registration with invalid email."""
        test_user_data["email"] = "invalid-email"
        
        response = client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 422


class TestUserLogin:
    """Test user login endpoint."""
    
    @patch('src.core.config.get_settings')
    def test_login_success(self, mock_settings, setup_database, existing_user):
        """Test successful user login."""
        mock_settings.return_value.jwt_secret_key = "test_secret"
        mock_settings.return_value.jwt_algorithm = "HS256"
        mock_settings.return_value.jwt_access_token_expire_minutes = 30
        mock_settings.return_value.jwt_refresh_token_expire_days = 7
        
        login_data = {
            "email": existing_user.email,
            "password": "ExistingPassword123!",
            "remember_me": False
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Login successful"
        assert data["user"]["email"] == existing_user.email
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]
        assert data["tokens"]["token_type"] == "bearer"
    
    def test_login_invalid_email(self, setup_database):
        """Test login with non-existent email."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "SomePassword123!"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        data = response.json()
        assert "Invalid email or password" in data["detail"]
    
    def test_login_invalid_password(self, setup_database, existing_user):
        """Test login with incorrect password."""
        login_data = {
            "email": existing_user.email,
            "password": "WrongPassword123!"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        data = response.json()
        assert "Invalid email or password" in data["detail"]
    
    def test_login_inactive_user(self, setup_database, db_session, existing_user):
        """Test login with inactive user."""
        existing_user.is_active = False
        db_session.commit()
        
        login_data = {
            "email": existing_user.email,
            "password": "ExistingPassword123!"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        data = response.json()
        assert "inactive" in data["detail"].lower()
    
    @patch('src.core.config.get_settings')
    def test_login_remember_me(self, mock_settings, setup_database, existing_user):
        """Test login with remember me option."""
        mock_settings.return_value.jwt_secret_key = "test_secret"
        mock_settings.return_value.jwt_algorithm = "HS256"
        mock_settings.return_value.jwt_access_token_expire_minutes = 30
        mock_settings.return_value.jwt_refresh_token_expire_days = 7
        
        login_data = {
            "email": existing_user.email,
            "password": "ExistingPassword123!",
            "remember_me": True
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        # With remember me, access token should have longer expiration
        assert data["tokens"]["expires_in"] > 30 * 60  # More than 30 minutes


class TestTokenRefresh:
    """Test token refresh endpoint."""
    
    @patch('src.core.config.get_settings')
    def test_refresh_token_success(self, mock_settings, setup_database, existing_user):
        """Test successful token refresh."""
        from src.core.security import create_refresh_token
        
        mock_settings.return_value.jwt_secret_key = "test_secret"
        mock_settings.return_value.jwt_algorithm = "HS256"
        mock_settings.return_value.jwt_access_token_expire_minutes = 30
        
        # Create a valid refresh token
        token_data = {"sub": existing_user.email, "user_id": existing_user.id}
        refresh_token = create_refresh_token(token_data)
        
        refresh_data = {"refresh_token": refresh_token}
        
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 30 * 60  # 30 minutes in seconds
    
    def test_refresh_token_invalid(self, setup_database):
        """Test token refresh with invalid token."""
        refresh_data = {"refresh_token": "invalid.token.here"}
        
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == 401
        data = response.json()
        assert "Token refresh failed" in data["detail"]


class TestUserProfile:
    """Test user profile endpoints."""
    
    @patch('src.core.config.get_settings')
    def test_get_current_user_authenticated(self, mock_settings, setup_database, existing_user):
        """Test getting current user profile when authenticated."""
        from src.core.security import create_access_token
        
        mock_settings.return_value.jwt_secret_key = "test_secret"
        mock_settings.return_value.jwt_algorithm = "HS256"
        
        # Create access token
        token_data = {"sub": existing_user.email, "user_id": existing_user.id}
        access_token = create_access_token(token_data)
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == existing_user.email
        assert data["username"] == existing_user.username
        assert data["id"] == existing_user.id
    
    def test_get_current_user_unauthenticated(self, setup_database):
        """Test getting current user profile when not authenticated."""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
        data = response.json()
        assert "Authentication required" in data["detail"]
    
    @patch('src.core.config.get_settings')
    def test_update_user_profile(self, mock_settings, setup_database, existing_user, db_session):
        """Test updating user profile."""
        from src.core.security import create_access_token
        
        mock_settings.return_value.jwt_secret_key = "test_secret"
        mock_settings.return_value.jwt_algorithm = "HS256"
        
        # Create access token
        token_data = {"sub": existing_user.email, "user_id": existing_user.id}
        access_token = create_access_token(token_data)
        
        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "organization": "New Corp"
        }
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.put("/api/v1/auth/me", json=update_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Name"
        assert data["organization"] == "New Corp"


class TestEmailVerification:
    """Test email verification endpoint."""
    
    def test_verify_email_success(self, setup_database, unverified_user, db_session):
        """Test successful email verification."""
        verification_data = {
            "token": unverified_user.email_verification_token
        }
        
        response = client.post("/api/v1/auth/verify-email", json=verification_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Email verified successfully"
        
        # Check that user is now verified
        db_session.refresh(unverified_user)
        assert unverified_user.is_verified is True
        assert unverified_user.email_verification_token is None
    
    def test_verify_email_invalid_token(self, setup_database):
        """Test email verification with invalid token."""
        verification_data = {"token": "invalid_token"}
        
        response = client.post("/api/v1/auth/verify-email", json=verification_data)
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid verification token" in data["detail"]


class TestPasswordReset:
    """Test password reset endpoints."""
    
    def test_forgot_password_existing_email(self, setup_database, existing_user):
        """Test password reset request with existing email."""
        reset_data = {"email": existing_user.email}
        
        response = client.post("/api/v1/auth/forgot-password", json=reset_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "password reset link has been sent" in data["message"]
    
    def test_forgot_password_nonexistent_email(self, setup_database):
        """Test password reset request with non-existent email."""
        reset_data = {"email": "nonexistent@example.com"}
        
        response = client.post("/api/v1/auth/forgot-password", json=reset_data)
        
        # Should return success to prevent email enumeration
        assert response.status_code == 200
        data = response.json()
        assert "password reset link has been sent" in data["message"]


class TestLogout:
    """Test logout endpoint."""
    
    @patch('src.core.config.get_settings')
    def test_logout_authenticated(self, mock_settings, setup_database, existing_user):
        """Test logout when authenticated."""
        from src.core.security import create_access_token
        
        mock_settings.return_value.jwt_secret_key = "test_secret"
        mock_settings.return_value.jwt_algorithm = "HS256"
        
        # Create access token
        token_data = {"sub": existing_user.email, "user_id": existing_user.id}
        access_token = create_access_token(token_data)
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/api/v1/auth/logout", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Successfully logged out"
    
    def test_logout_unauthenticated(self, setup_database):
        """Test logout when not authenticated."""
        response = client.post("/api/v1/auth/logout")
        
        assert response.status_code == 401


class TestAuthStatus:
    """Test authentication status endpoint."""
    
    @patch('src.core.config.get_settings')
    def test_auth_status_authenticated(self, mock_settings, setup_database, existing_user):
        """Test auth status when authenticated."""
        from src.core.security import create_access_token
        
        mock_settings.return_value.jwt_secret_key = "test_secret"
        mock_settings.return_value.jwt_algorithm = "HS256"
        
        # Create access token
        token_data = {"sub": existing_user.email, "user_id": existing_user.id}
        access_token = create_access_token(token_data)
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/api/v1/auth/status", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["user"]["email"] == existing_user.email
        assert "api_quota_remaining" in data
    
    def test_auth_status_unauthenticated(self, setup_database):
        """Test auth status when not authenticated."""
        response = client.get("/api/v1/auth/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["user"] is None
        assert data["api_quota_remaining"] == 0