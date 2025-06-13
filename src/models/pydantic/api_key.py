"""Pydantic models for API key management requests and responses."""

from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, field_validator


class APIKeyCreate(BaseModel):
    """Schema for creating a new API key."""
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable name for the API key"
    )
    
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional description of the API key purpose"
    )
    
    scopes: Optional[List[str]] = Field(
        default_factory=list,
        description="List of allowed scopes/permissions for this key"
    )
    
    expires_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Number of days until the key expires (null = never expires)"
    )
    
    rate_limit_per_minute: int = Field(
        default=60,
        ge=1,
        le=10000,
        description="Rate limit: requests per minute"
    )
    
    rate_limit_per_hour: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="Rate limit: requests per hour"
    )
    
    rate_limit_per_day: int = Field(
        default=10000,
        ge=1,
        le=1000000,
        description="Rate limit: requests per day"
    )
    
    key_metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata for the API key"
    )
    
    @field_validator('scopes')
    @classmethod
    def validate_scopes(cls, v: Optional[List[str]]) -> List[str]:
        """Validate and normalize scopes."""
        if not v:
            return []
        
        # Define valid scopes
        valid_scopes = {
            "*",  # All permissions
            "read",
            "write",
            "admin",
            "content:read",
            "content:write",
            "search:read",
            "user:read",
            "user:write",
            "analytics:read",
        }
        
        # Check all scopes are valid
        invalid_scopes = set(v) - valid_scopes
        if invalid_scopes:
            raise ValueError(f"Invalid scopes: {', '.join(invalid_scopes)}")
        
        return list(set(v))  # Remove duplicates


class APIKeyUpdate(BaseModel):
    """Schema for updating an existing API key."""
    
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Human-readable name for the API key"
    )
    
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional description of the API key purpose"
    )
    
    scopes: Optional[List[str]] = Field(
        None,
        description="List of allowed scopes/permissions for this key"
    )
    
    is_active: Optional[bool] = Field(
        None,
        description="Whether the API key is active"
    )
    
    rate_limit_per_minute: Optional[int] = Field(
        None,
        ge=1,
        le=10000,
        description="Rate limit: requests per minute"
    )
    
    rate_limit_per_hour: Optional[int] = Field(
        None,
        ge=1,
        le=100000,
        description="Rate limit: requests per hour"
    )
    
    rate_limit_per_day: Optional[int] = Field(
        None,
        ge=1,
        le=1000000,
        description="Rate limit: requests per day"
    )
    
    key_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata for the API key"
    )
    
    @field_validator('scopes')
    @classmethod
    def validate_scopes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and normalize scopes."""
        if v is None:
            return None
        
        # Use the same validation as APIKeyCreate
        return APIKeyCreate.validate_scopes(v)


class APIKeyResponse(BaseModel):
    """Schema for API key response (safe, without sensitive data)."""
    
    id: str
    name: str
    description: Optional[str] = None
    key_prefix: str
    user_id: str
    is_active: bool
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    last_used_ip: Optional[str] = None
    scopes: Optional[List[str]] = None
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    rate_limit_per_day: int
    total_requests: int
    requests_today: int
    requests_this_hour: int
    requests_this_minute: int
    user_agent: Optional[str] = None
    key_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    is_expired: bool
    is_valid: bool
    
    class Config:
        from_attributes = True


class APIKeyCreateResponse(BaseModel):
    """Schema for API key creation response (includes the actual key)."""
    
    message: str
    api_key: str = Field(
        description="The actual API key (only shown once during creation)"
    )
    key_info: APIKeyResponse
    
    class Config:
        from_attributes = True


class APIKeyUsageStats(BaseModel):
    """Schema for API key usage statistics."""
    
    key_id: str
    key_name: str
    key_prefix: str
    total_requests: int
    requests_today: int
    requests_this_hour: int
    requests_this_minute: int
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    rate_limit_per_day: int
    remaining_minute: int = Field(description="Remaining requests this minute")
    remaining_hour: int = Field(description="Remaining requests this hour")
    remaining_day: int = Field(description="Remaining requests today")
    last_used_at: Optional[datetime] = None
    last_used_ip: Optional[str] = None
    user_agent: Optional[str] = None
    
    class Config:
        from_attributes = True


class APIKeyListResponse(BaseModel):
    """Schema for listing API keys."""
    
    api_keys: List[APIKeyResponse]
    total: int
    page: int = 1
    page_size: int = 50
    
    class Config:
        from_attributes = True


class APIKeyRotateResponse(BaseModel):
    """Schema for API key rotation response."""
    
    message: str
    new_api_key: str = Field(
        description="The new API key (only shown once during rotation)"
    )
    key_info: APIKeyResponse
    
    class Config:
        from_attributes = True


class APIKeyDeleteResponse(BaseModel):
    """Schema for API key deletion response."""
    
    message: str
    deleted_key_id: str
    
    class Config:
        from_attributes = True


class APIKeyValidationError(BaseModel):
    """Schema for API key validation errors."""
    
    error: str
    code: str
    details: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class RateLimitInfo(BaseModel):
    """Schema for rate limit information in responses."""
    
    limit_per_minute: int
    limit_per_hour: int
    limit_per_day: int
    remaining_minute: int
    remaining_hour: int
    remaining_day: int
    reset_minute: datetime
    reset_hour: datetime
    reset_day: datetime
    
    class Config:
        from_attributes = True