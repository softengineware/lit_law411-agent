"""User model for authentication and authorization."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class User(BaseModel):
    """Model for user accounts."""
    
    __tablename__ = "users"
    
    # Authentication
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="User email address"
    )
    
    username: Mapped[Optional[str]] = mapped_column(
        String(50),
        unique=True,
        comment="Unique username"
    )
    
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hashed password"
    )
    
    # Profile Information
    first_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="First name"
    )
    
    last_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Last name"
    )
    
    organization: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="Organization or law firm"
    )
    
    job_title: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Job title"
    )
    
    # Account Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Account is active"
    )
    
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Email is verified"
    )
    
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Has admin privileges"
    )
    
    # Role and Permissions
    role: Mapped[str] = mapped_column(
        String(50),
        default="user",
        comment="User role: user, premium, admin, superuser"
    )
    
    permissions: Mapped[Optional[list]] = mapped_column(
        JSONB,
        comment="Additional permissions"
    )
    
    # Subscription and Billing
    subscription_tier: Mapped[str] = mapped_column(
        String(50),
        default="free",
        comment="Subscription tier: free, basic, premium, enterprise"
    )
    
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        comment="Subscription expiration date"
    )
    
    # Usage Tracking
    api_calls_today: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="API calls made today"
    )
    
    api_calls_month: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="API calls made this month"
    )
    
    total_api_calls: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Total API calls made"
    )
    
    # Security
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Failed login attempts"
    )
    
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        comment="Account locked until this time"
    )
    
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        comment="Last successful login"
    )
    
    last_login_ip: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 support
        comment="IP address of last login"
    )
    
    # Email Verification
    email_verification_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="Email verification token"
    )
    
    email_verification_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        comment="Email verification token expiration"
    )
    
    # Password Reset
    password_reset_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="Password reset token"
    )
    
    password_reset_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        comment="Password reset token expiration"
    )
    
    # Preferences
    preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="User preferences and settings"
    )
    
    # Relationships
    search_queries = relationship(
        "SearchQuery",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    @property
    def full_name(self) -> str:
        """Get user's full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(part for part in parts if part)
    
    @property
    def is_premium(self) -> bool:
        """Check if user has premium subscription."""
        return self.subscription_tier in ["premium", "enterprise"]
    
    @property
    def is_account_locked(self) -> bool:
        """Check if account is currently locked."""
        if not self.locked_until:
            return False
        return datetime.utcnow() < self.locked_until
    
    def __repr__(self) -> str:
        """String representation."""
        return f"<User(email='{self.email}', role='{self.role}')>"