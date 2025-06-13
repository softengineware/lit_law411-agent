"""Pydantic models for authentication and authorization."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator


class UserRegistration(BaseModel):
    """User registration request model."""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="Username")
    first_name: Optional[str] = Field(None, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name")
    organization: Optional[str] = Field(None, max_length=255, description="Organization")
    job_title: Optional[str] = Field(None, max_length=100, description="Job title")
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        from ...core.security import validate_password_strength
        
        is_valid, issues = validate_password_strength(v)
        if not is_valid:
            raise ValueError(f"Password validation failed: {'; '.join(issues)}")
        return v
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        if v is not None:
            if not v.replace('_', '').replace('-', '').isalnum():
                raise ValueError("Username can only contain letters, numbers, hyphens, and underscores")
        return v


class UserLogin(BaseModel):
    """User login request model."""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    remember_me: bool = Field(default=False, description="Remember user login")


class TokenResponse(BaseModel):
    """Token response model."""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class TokenRefresh(BaseModel):
    """Token refresh request model."""
    
    refresh_token: str = Field(..., description="JWT refresh token")


class PasswordReset(BaseModel):
    """Password reset request model."""
    
    email: EmailStr = Field(..., description="User email address")


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation model."""
    
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")
    
    @validator('new_password')
    def validate_password(cls, v):
        """Validate password strength."""
        from ...core.security import validate_password_strength
        
        is_valid, issues = validate_password_strength(v)
        if not is_valid:
            raise ValueError(f"Password validation failed: {'; '.join(issues)}")
        return v


class PasswordChange(BaseModel):
    """Password change request model."""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    
    @validator('new_password')
    def validate_password(cls, v):
        """Validate password strength."""
        from ...core.security import validate_password_strength
        
        is_valid, issues = validate_password_strength(v)
        if not is_valid:
            raise ValueError(f"Password validation failed: {'; '.join(issues)}")
        return v


class EmailVerification(BaseModel):
    """Email verification request model."""
    
    token: str = Field(..., description="Email verification token")


class UserProfile(BaseModel):
    """User profile response model."""
    
    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    username: Optional[str] = Field(None, description="Username")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    full_name: str = Field(..., description="Full name")
    organization: Optional[str] = Field(None, description="Organization")
    job_title: Optional[str] = Field(None, description="Job title")
    role: str = Field(..., description="User role")
    subscription_tier: str = Field(..., description="Subscription tier")
    is_active: bool = Field(..., description="Account is active")
    is_verified: bool = Field(..., description="Email is verified")
    is_superuser: bool = Field(..., description="Has admin privileges")
    is_premium: bool = Field(..., description="Has premium subscription")
    created_at: datetime = Field(..., description="Account creation date")
    updated_at: datetime = Field(..., description="Last update date")
    last_login_at: Optional[datetime] = Field(None, description="Last login date")
    api_calls_today: int = Field(..., description="API calls made today")
    api_calls_month: int = Field(..., description="API calls made this month")
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """User profile update model."""
    
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="Username")
    first_name: Optional[str] = Field(None, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name")
    organization: Optional[str] = Field(None, max_length=255, description="Organization")
    job_title: Optional[str] = Field(None, max_length=100, description="Job title")
    preferences: Optional[dict] = Field(None, description="User preferences")
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        if v is not None:
            if not v.replace('_', '').replace('-', '').isalnum():
                raise ValueError("Username can only contain letters, numbers, hyphens, and underscores")
        return v


class AuthStatus(BaseModel):
    """Authentication status model."""
    
    authenticated: bool = Field(..., description="User is authenticated")
    user: Optional[UserProfile] = Field(None, description="User profile if authenticated")
    permissions: list[str] = Field(default_factory=list, description="User permissions")
    subscription_active: bool = Field(default=False, description="Subscription is active")
    api_quota_remaining: int = Field(default=0, description="Remaining API quota")


class LoginResponse(BaseModel):
    """Login response model."""
    
    message: str = Field(..., description="Login status message")
    user: UserProfile = Field(..., description="User profile")
    tokens: TokenResponse = Field(..., description="Authentication tokens")
    
    
class LogoutResponse(BaseModel):
    """Logout response model."""
    
    message: str = Field(default="Successfully logged out", description="Logout message")


class RegistrationResponse(BaseModel):
    """Registration response model."""
    
    message: str = Field(..., description="Registration status message")
    user: UserProfile = Field(..., description="Created user profile")
    verification_required: bool = Field(default=True, description="Email verification required")


class ErrorResponse(BaseModel):
    """Error response model."""
    
    detail: str = Field(..., description="Error detail message")
    type: Optional[str] = Field(None, description="Error type")
    code: Optional[str] = Field(None, description="Error code")


class SuccessResponse(BaseModel):
    """Generic success response model."""
    
    message: str = Field(..., description="Success message")
    success: bool = Field(default=True, description="Operation success status")


# Rate limiting models
class RateLimitInfo(BaseModel):
    """Rate limit information model."""
    
    limit: int = Field(..., description="Rate limit per period")
    remaining: int = Field(..., description="Remaining requests")
    reset: datetime = Field(..., description="Rate limit reset time")
    retry_after: Optional[int] = Field(None, description="Retry after seconds")


# API Key models (for future use)
class APIKeyCreate(BaseModel):
    """API key creation model."""
    
    name: str = Field(..., max_length=100, description="API key name")
    description: Optional[str] = Field(None, max_length=255, description="API key description")
    expires_at: Optional[datetime] = Field(None, description="API key expiration")
    permissions: list[str] = Field(default_factory=list, description="API key permissions")


class APIKeyResponse(BaseModel):
    """API key response model."""
    
    id: int = Field(..., description="API key ID")
    name: str = Field(..., description="API key name")
    key: str = Field(..., description="API key value (only shown once)")
    description: Optional[str] = Field(None, description="API key description")
    created_at: datetime = Field(..., description="Creation date")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    is_active: bool = Field(..., description="API key is active")
    permissions: list[str] = Field(default_factory=list, description="API key permissions")
    
    class Config:
        from_attributes = True