"""Unit tests for security utilities."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    generate_secret_key,
    generate_email_verification_token,
    generate_password_reset_token,
    is_token_expired,
    validate_password_strength,
    SecurityError,
    TokenError,
    PasswordError,
)


class TestPasswordHashing:
    """Test password hashing functionality."""
    
    def test_hash_password_success(self):
        """Test successful password hashing."""
        password = "test_password_123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 0
        assert isinstance(hashed, str)
    
    def test_hash_password_different_results(self):
        """Test that same password produces different hashes (due to salt)."""
        password = "test_password_123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        assert hash1 != hash2
    
    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "test_password_123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_hash_password_empty_string(self):
        """Test hashing empty password."""
        password = ""
        hashed = hash_password(password)
        
        assert len(hashed) > 0
        assert verify_password(password, hashed) is True
    
    def test_hash_password_unicode(self):
        """Test hashing password with unicode characters."""
        password = "пароль_123_🔒"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True


class TestJWTTokens:
    """Test JWT token functionality."""
    
    @patch('src.core.security.settings')
    def test_create_access_token_success(self, mock_settings):
        """Test successful access token creation."""
        mock_settings.jwt_secret_key = "test_secret_key"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expire_minutes = 30
        
        data = {"sub": "test@example.com", "user_id": 123}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    @patch('src.core.security.settings')
    def test_create_access_token_with_expiry(self, mock_settings):
        """Test access token creation with custom expiry."""
        mock_settings.jwt_secret_key = "test_secret_key"
        mock_settings.jwt_algorithm = "HS256"
        
        data = {"sub": "test@example.com"}
        expires_delta = timedelta(minutes=60)
        token = create_access_token(data, expires_delta)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    @patch('src.core.security.settings')
    def test_create_refresh_token_success(self, mock_settings):
        """Test successful refresh token creation."""
        mock_settings.jwt_secret_key = "test_secret_key"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_refresh_token_expire_days = 7
        
        data = {"sub": "test@example.com", "user_id": 123}
        token = create_refresh_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    @patch('src.core.security.settings')
    def test_verify_access_token_success(self, mock_settings):
        """Test successful access token verification."""
        mock_settings.jwt_secret_key = "test_secret_key"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expire_minutes = 30
        
        data = {"sub": "test@example.com", "user_id": 123}
        token = create_access_token(data)
        payload = verify_token(token, token_type="access")
        
        assert payload["sub"] == data["sub"]
        assert payload["user_id"] == data["user_id"]
        assert payload["type"] == "access"
    
    @patch('src.core.security.settings')
    def test_verify_refresh_token_success(self, mock_settings):
        """Test successful refresh token verification."""
        mock_settings.jwt_secret_key = "test_secret_key"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_refresh_token_expire_days = 7
        
        data = {"sub": "test@example.com", "user_id": 123}
        token = create_refresh_token(data)
        payload = verify_token(token, token_type="refresh")
        
        assert payload["sub"] == data["sub"]
        assert payload["user_id"] == data["user_id"]
        assert payload["type"] == "refresh"
    
    @patch('src.core.security.settings')
    def test_verify_token_wrong_type(self, mock_settings):
        """Test token verification with wrong token type."""
        mock_settings.jwt_secret_key = "test_secret_key"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expire_minutes = 30
        
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        
        with pytest.raises(TokenError, match="Invalid token type"):
            verify_token(token, token_type="refresh")
    
    @patch('src.core.security.settings')
    def test_verify_token_invalid_token(self, mock_settings):
        """Test verification of invalid token."""
        mock_settings.jwt_secret_key = "test_secret_key"
        mock_settings.jwt_algorithm = "HS256"
        
        invalid_token = "invalid.token.here"
        
        with pytest.raises(TokenError, match="Invalid token"):
            verify_token(invalid_token)
    
    @patch('src.core.security.settings')
    def test_create_token_no_secret(self, mock_settings):
        """Test token creation without secret key."""
        mock_settings.jwt_secret_key = None
        mock_settings.jwt_access_token_expire_minutes = 30
        
        data = {"sub": "test@example.com"}
        
        with pytest.raises(TokenError, match="JWT secret key not configured"):
            create_access_token(data)
    
    @patch('src.core.security.settings')
    def test_verify_token_no_secret(self, mock_settings):
        """Test token verification without secret key."""
        mock_settings.jwt_secret_key = None
        
        token = "some.jwt.token"
        
        with pytest.raises(TokenError, match="JWT secret key not configured"):
            verify_token(token)


class TestTokenUtils:
    """Test token utility functions."""
    
    def test_generate_secret_key(self):
        """Test secret key generation."""
        key1 = generate_secret_key()
        key2 = generate_secret_key()
        
        assert isinstance(key1, str)
        assert isinstance(key2, str)
        assert len(key1) > 20
        assert len(key2) > 20
        assert key1 != key2
    
    def test_generate_email_verification_token(self):
        """Test email verification token generation."""
        token1 = generate_email_verification_token()
        token2 = generate_email_verification_token()
        
        assert isinstance(token1, str)
        assert isinstance(token2, str)
        assert len(token1) > 20
        assert len(token2) > 20
        assert token1 != token2
    
    def test_generate_password_reset_token(self):
        """Test password reset token generation."""
        token1 = generate_password_reset_token()
        token2 = generate_password_reset_token()
        
        assert isinstance(token1, str)
        assert isinstance(token2, str)
        assert len(token1) > 20
        assert len(token2) > 20
        assert token1 != token2
    
    def test_is_token_expired_not_expired(self):
        """Test token expiration check for non-expired token."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        assert is_token_expired(future_time) is False
    
    def test_is_token_expired_expired(self):
        """Test token expiration check for expired token."""
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        assert is_token_expired(past_time) is True
    
    def test_is_token_expired_exactly_now(self):
        """Test token expiration check for token expiring now."""
        # Use a time slightly in the past to ensure it's expired
        almost_now = datetime.now(timezone.utc) - timedelta(microseconds=1)
        assert is_token_expired(almost_now) is True


class TestPasswordValidation:
    """Test password strength validation."""
    
    def test_validate_strong_password(self):
        """Test validation of strong password."""
        password = "StrongP@ss123"
        is_valid, issues = validate_password_strength(password)
        
        assert is_valid is True
        assert len(issues) == 0
    
    def test_validate_weak_password_short(self):
        """Test validation of short password."""
        password = "Short1!"
        is_valid, issues = validate_password_strength(password)
        
        assert is_valid is False
        assert "at least 8 characters" in str(issues)
    
    def test_validate_weak_password_no_uppercase(self):
        """Test validation of password without uppercase."""
        password = "lowercase123!"
        is_valid, issues = validate_password_strength(password)
        
        assert is_valid is False
        assert "uppercase letter" in str(issues)
    
    def test_validate_weak_password_no_lowercase(self):
        """Test validation of password without lowercase."""
        password = "UPPERCASE123!"
        is_valid, issues = validate_password_strength(password)
        
        assert is_valid is False
        assert "lowercase letter" in str(issues)
    
    def test_validate_weak_password_no_digit(self):
        """Test validation of password without digit."""
        password = "NoDigitsHere!"
        is_valid, issues = validate_password_strength(password)
        
        assert is_valid is False
        assert "digit" in str(issues)
    
    def test_validate_weak_password_no_special(self):
        """Test validation of password without special character."""
        password = "NoSpecialChars123"
        is_valid, issues = validate_password_strength(password)
        
        assert is_valid is False
        assert "special character" in str(issues)
    
    def test_validate_password_multiple_issues(self):
        """Test validation of password with multiple issues."""
        password = "weak"
        is_valid, issues = validate_password_strength(password)
        
        assert is_valid is False
        assert len(issues) > 1
        assert "at least 8 characters" in str(issues)
        assert "uppercase letter" in str(issues)
        assert "digit" in str(issues)
        assert "special character" in str(issues)
    
    def test_validate_empty_password(self):
        """Test validation of empty password."""
        password = ""
        is_valid, issues = validate_password_strength(password)
        
        assert is_valid is False
        assert len(issues) > 0


class TestSecurityExceptions:
    """Test custom security exceptions."""
    
    def test_security_error(self):
        """Test SecurityError exception."""
        with pytest.raises(SecurityError):
            raise SecurityError("Test security error")
    
    def test_token_error(self):
        """Test TokenError exception."""
        with pytest.raises(TokenError):
            raise TokenError("Test token error")
        
        # TokenError should be a subclass of SecurityError
        with pytest.raises(SecurityError):
            raise TokenError("Test token error")
    
    def test_password_error(self):
        """Test PasswordError exception."""
        with pytest.raises(PasswordError):
            raise PasswordError("Test password error")
        
        # PasswordError should be a subclass of SecurityError
        with pytest.raises(SecurityError):
            raise PasswordError("Test password error")