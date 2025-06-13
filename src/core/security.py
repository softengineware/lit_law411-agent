"""Security utilities for authentication and authorization."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

import bcrypt
import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from .config import get_settings

settings = get_settings()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SecurityError(Exception):
    """Base security error."""
    pass


class TokenError(SecurityError):
    """Token-related error."""
    pass


class PasswordError(SecurityError):
    """Password-related error."""
    pass


def generate_secret_key() -> str:
    """Generate a secure random secret key."""
    return secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
        
    Raises:
        PasswordError: If password hashing fails
    """
    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    except Exception as e:
        raise PasswordError(f"Failed to hash password: {str(e)}")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored hashed password
        
    Returns:
        True if password matches, False otherwise
        
    Raises:
        PasswordError: If password verification fails
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception as e:
        raise PasswordError(f"Failed to verify password: {str(e)}")


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time delta
        
    Returns:
        Encoded JWT token
        
    Raises:
        TokenError: If token creation fails
    """
    try:
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.jwt_access_token_expire_minutes
            )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access"
        })
        
        if not settings.jwt_secret_key:
            raise TokenError("JWT secret key not configured")
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )
        
        return encoded_jwt
        
    except jwt.PyJWTError as e:
        raise TokenError(f"Failed to create access token: {str(e)}")
    except Exception as e:
        raise TokenError(f"Unexpected error creating access token: {str(e)}")


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time delta
        
    Returns:
        Encoded JWT refresh token
        
    Raises:
        TokenError: If token creation fails
    """
    try:
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                days=settings.jwt_refresh_token_expire_days
            )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        })
        
        if not settings.jwt_secret_key:
            raise TokenError("JWT secret key not configured")
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )
        
        return encoded_jwt
        
    except jwt.PyJWTError as e:
        raise TokenError(f"Failed to create refresh token: {str(e)}")
    except Exception as e:
        raise TokenError(f"Unexpected error creating refresh token: {str(e)}")


def verify_token(token: str, token_type: str = "access") -> dict[str, Any]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token to verify
        token_type: Expected token type ('access' or 'refresh')
        
    Returns:
        Decoded token payload
        
    Raises:
        TokenError: If token verification fails
    """
    try:
        if not settings.jwt_secret_key:
            raise TokenError("JWT secret key not configured")
        
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        # Verify token type
        if payload.get("type") != token_type:
            raise TokenError(f"Invalid token type. Expected {token_type}")
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise TokenError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise TokenError(f"Invalid token: {str(e)}")
    except Exception as e:
        raise TokenError(f"Token verification failed: {str(e)}")


def generate_email_verification_token() -> str:
    """Generate a secure token for email verification."""
    return secrets.token_urlsafe(32)


def generate_password_reset_token() -> str:
    """Generate a secure token for password reset."""
    return secrets.token_urlsafe(32)


def is_token_expired(expires_at: datetime) -> bool:
    """
    Check if a token has expired.
    
    Args:
        expires_at: Token expiration datetime
        
    Returns:
        True if token has expired, False otherwise
    """
    return datetime.now(timezone.utc) > expires_at


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """
    Validate password strength.
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    if len(password) < 8:
        issues.append("Password must be at least 8 characters long")
    
    if not any(c.isupper() for c in password):
        issues.append("Password must contain at least one uppercase letter")
    
    if not any(c.islower() for c in password):
        issues.append("Password must contain at least one lowercase letter")
    
    if not any(c.isdigit() for c in password):
        issues.append("Password must contain at least one digit")
    
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        issues.append("Password must contain at least one special character")
    
    return len(issues) == 0, issues