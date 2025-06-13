"""API Key model for secure API authentication and rate limiting."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class APIKey(BaseModel):
    """Model for API key management and authentication."""
    
    __tablename__ = "api_keys"
    
    # Key Information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable name for the API key"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Optional description of the API key purpose"
    )
    
    # The actual API key (hashed for security)
    key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Hashed API key for secure storage"
    )
    
    # Key prefix (first 8 characters) for identification in logs/UI
    key_prefix: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        comment="First 8 characters of key for identification"
    )
    
    # User Association
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Owner of this API key"
    )
    
    # Status and Lifecycle
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Whether the API key is active"
    )
    
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        comment="When the API key expires (null = never)"
    )
    
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        comment="When the API key was last used"
    )
    
    last_used_ip: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 support
        comment="IP address of last API key usage"
    )
    
    # Permissions and Scopes
    scopes: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        comment="List of allowed scopes/permissions for this key"
    )
    
    # Rate Limiting
    rate_limit_per_minute: Mapped[int] = mapped_column(
        Integer,
        default=60,
        comment="Rate limit: requests per minute"
    )
    
    rate_limit_per_hour: Mapped[int] = mapped_column(
        Integer,
        default=1000,
        comment="Rate limit: requests per hour"
    )
    
    rate_limit_per_day: Mapped[int] = mapped_column(
        Integer,
        default=10000,
        comment="Rate limit: requests per day"
    )
    
    # Usage Statistics
    total_requests: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Total number of requests made with this key"
    )
    
    requests_today: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of requests made today"
    )
    
    requests_this_hour: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of requests made this hour"
    )
    
    requests_this_minute: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of requests made this minute"
    )
    
    # Metadata
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(512),
        comment="User agent of the last request"
    )
    
    key_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        comment="Additional metadata for the API key"
    )
    
    # Relationships
    user = relationship(
        "User",
        back_populates="api_keys"
    )
    
    @classmethod
    def generate_key(cls) -> str:
        """
        Generate a new API key.
        
        Format: llk_[32_random_chars] (lit law411 key)
        Total length: 36 characters
        
        Returns:
            Generated API key string
        """
        random_part = secrets.token_urlsafe(24)  # ~32 chars when base64 encoded
        return f"llk_{random_part}"
    
    @classmethod
    def hash_key(cls, api_key: str) -> str:
        """
        Hash an API key for secure storage.
        
        Args:
            api_key: The raw API key to hash
            
        Returns:
            Hashed API key
        """
        import hashlib
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @classmethod
    def get_key_prefix(cls, api_key: str) -> str:
        """
        Get the prefix of an API key for identification.
        
        Args:
            api_key: The API key to get prefix from
            
        Returns:
            First 8 characters of the API key
        """
        return api_key[:8] if len(api_key) >= 8 else api_key
    
    @property
    def is_expired(self) -> bool:
        """Check if the API key has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if the API key is valid (active and not expired)."""
        return self.is_active and not self.is_expired
    
    def is_rate_limited(self, period: str = "minute") -> bool:
        """
        Check if the API key has exceeded rate limits.
        
        Args:
            period: Rate limit period to check ("minute", "hour", "day")
            
        Returns:
            True if rate limited, False otherwise
        """
        if period == "minute":
            return self.requests_this_minute >= self.rate_limit_per_minute
        elif period == "hour":
            return self.requests_this_hour >= self.rate_limit_per_hour
        elif period == "day":
            return self.requests_today >= self.rate_limit_per_day
        return False
    
    def has_scope(self, required_scope: str) -> bool:
        """
        Check if the API key has a required scope.
        
        Args:
            required_scope: The scope to check for
            
        Returns:
            True if key has the scope, False otherwise
        """
        if not self.scopes:
            return False
        return required_scope in self.scopes or "*" in self.scopes
    
    def increment_usage(self) -> None:
        """Increment usage counters for the API key."""
        self.total_requests += 1
        self.requests_today += 1
        self.requests_this_hour += 1
        self.requests_this_minute += 1
        self.last_used_at = datetime.now(timezone.utc)
    
    def reset_daily_usage(self) -> None:
        """Reset daily usage counter."""
        self.requests_today = 0
    
    def reset_hourly_usage(self) -> None:
        """Reset hourly usage counter."""
        self.requests_this_hour = 0
    
    def reset_minute_usage(self) -> None:
        """Reset minute usage counter."""
        self.requests_this_minute = 0
    
    def update_metadata(self, user_agent: Optional[str] = None, ip: Optional[str] = None) -> None:
        """
        Update API key metadata with request information.
        
        Args:
            user_agent: User agent string from request
            ip: IP address from request
        """
        if user_agent:
            self.user_agent = user_agent
        if ip:
            self.last_used_ip = ip
    
    def to_safe_dict(self) -> dict:
        """
        Convert to dictionary without sensitive information.
        
        Returns:
            Dictionary representation without key_hash
        """
        data = self.to_dict()
        # Remove sensitive fields
        data.pop('key_hash', None)
        # Add computed fields
        data['is_expired'] = self.is_expired
        data['is_valid'] = self.is_valid
        return data
    
    def __repr__(self) -> str:
        """String representation."""
        return f"<APIKey(name='{self.name}', prefix='{self.key_prefix}', user_id='{self.user_id}')>"