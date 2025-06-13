"""Configuration management for lit_law411-agent.

This module provides centralized configuration management using Pydantic BaseSettings,
supporting environment variable overrides and validation.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Settings
    environment: str = Field(default="development", description="Runtime environment")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    workers: int = Field(default=4, description="Number of worker processes")

    # Database Configuration
    database_url: str = Field(
        default="postgresql://user:password@localhost:5432/lit_law411",
        description="PostgreSQL connection string",
    )

    # Three-Database Strategy
    # Airtable
    airtable_api_key: str = Field(description="Airtable API key")
    airtable_base_id: str = Field(description="Airtable base ID")

    # Supabase
    supabase_url: str = Field(description="Supabase project URL")
    supabase_key: str = Field(description="Supabase anon key")

    # Pinecone
    pinecone_api_key: str = Field(description="Pinecone API key")
    pinecone_environment: str = Field(description="Pinecone environment")
    pinecone_index_name: str = Field(default="lit_law411", description="Pinecone index name")

    # External APIs
    youtube_api_key: str = Field(description="YouTube Data API v3 key")
    openai_api_key: str = Field(description="OpenAI API key")

    # Cache & Queue
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection string",
    )
    elasticsearch_url: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch URL",
    )

    # Synchronization Settings
    sync_batch_size: int = Field(default=10, description="Batch size for sync operations")
    sync_max_retries: int = Field(default=5, description="Max retry attempts")
    sync_retry_delay: int = Field(default=1, description="Initial retry delay in seconds")
    consistency_check_enabled: bool = Field(
        default=True, description="Enable consistency checks"
    )
    consistency_tolerance_seconds: int = Field(
        default=5, description="Consistency check tolerance"
    )

    # Security
    jwt_secret_key: str = Field(description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=30, description="Access token expiration"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, description="Refresh token expiration"
    )
    session_secret: str = Field(description="Session secret key")

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins",
    )

    # Rate Limiting
    rate_limit_anonymous: int = Field(
        default=10, description="Anonymous requests per minute"
    )
    rate_limit_authenticated: int = Field(
        default=100, description="Authenticated requests per minute"
    )
    rate_limit_premium: int = Field(
        default=1000, description="Premium requests per minute"
    )

    # Monitoring
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN")
    metrics_enabled: bool = Field(default=True, description="Enable metrics")
    metrics_port: int = Field(default=9090, description="Metrics port")

    # Optional Services
    stripe_api_key: Optional[str] = Field(default=None, description="Stripe API key")
    stripe_webhook_secret: Optional[str] = Field(
        default=None, description="Stripe webhook secret"
    )
    sendgrid_api_key: Optional[str] = Field(default=None, description="SendGrid API key")
    from_email: str = Field(default="noreply@law411.com", description="From email")

    # AWS (optional)
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS access key")
    aws_secret_access_key: Optional[str] = Field(
        default=None, description="AWS secret key"
    )
    aws_region: str = Field(default="us-east-1", description="AWS region")
    s3_bucket_name: Optional[str] = Field(default=None, description="S3 bucket name")

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        allowed = {"development", "staging", "production", "test"}
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    @property
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.environment == "test"

    def get_database_url(self, include_driver: bool = True) -> str:
        """Get database URL with optional driver prefix."""
        if include_driver and not self.database_url.startswith("postgresql://"):
            return f"postgresql://{self.database_url}"
        return self.database_url

    def get_redis_url(self) -> str:
        """Get Redis URL with proper formatting."""
        if not self.redis_url.startswith("redis://"):
            return f"redis://{self.redis_url}"
        return self.redis_url


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export commonly used settings
settings = get_settings()