"""Unit tests for configuration management."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.core.config import Settings, get_settings


class TestSettings:
    """Test Settings configuration class."""

    def test_default_settings(self):
        """Test settings with default values."""
        settings = Settings(
            airtable_api_key="test_key",
            airtable_base_id="test_base",
            supabase_url="https://test.supabase.co",
            supabase_key="test_key",
            pinecone_api_key="test_key",
            pinecone_environment="test",
            youtube_api_key="test_key",
            openai_api_key="test_key",
            jwt_secret_key="test_secret",
            session_secret="test_session",
        )
        
        assert settings.environment == "development"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.workers == 4
        assert settings.pinecone_index_name == "lit_law411"

    def test_environment_validation(self):
        """Test environment field validation."""
        # Valid environments
        for env in ["development", "staging", "production", "test"]:
            settings = Settings(
                environment=env,
                airtable_api_key="test_key",
                airtable_base_id="test_base",
                supabase_url="https://test.supabase.co",
                supabase_key="test_key",
                pinecone_api_key="test_key",
                pinecone_environment="test",
                youtube_api_key="test_key",
                openai_api_key="test_key",
                jwt_secret_key="test_secret",
                session_secret="test_session",
            )
            assert settings.environment == env

        # Invalid environment
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment="invalid",
                airtable_api_key="test_key",
                airtable_base_id="test_base",
                supabase_url="https://test.supabase.co",
                supabase_key="test_key",
                pinecone_api_key="test_key",
                pinecone_environment="test",
                youtube_api_key="test_key",
                openai_api_key="test_key",
                jwt_secret_key="test_secret",
                session_secret="test_session",
            )
        assert "Environment must be one of" in str(exc_info.value)

    def test_log_level_validation(self):
        """Test log level validation and normalization."""
        settings = Settings(
            log_level="debug",  # lowercase
            airtable_api_key="test_key",
            airtable_base_id="test_base",
            supabase_url="https://test.supabase.co",
            supabase_key="test_key",
            pinecone_api_key="test_key",
            pinecone_environment="test",
            youtube_api_key="test_key",
            openai_api_key="test_key",
            jwt_secret_key="test_secret",
            session_secret="test_session",
        )
        assert settings.log_level == "DEBUG"  # Should be uppercase

    def test_cors_origins_parsing(self):
        """Test CORS origins parsing from string."""
        # Test string input
        settings = Settings(
            cors_origins="http://localhost:3000,http://localhost:8000",
            airtable_api_key="test_key",
            airtable_base_id="test_base",
            supabase_url="https://test.supabase.co",
            supabase_key="test_key",
            pinecone_api_key="test_key",
            pinecone_environment="test",
            youtube_api_key="test_key",
            openai_api_key="test_key",
            jwt_secret_key="test_secret",
            session_secret="test_session",
        )
        assert settings.cors_origins == ["http://localhost:3000", "http://localhost:8000"]

        # Test list input
        settings2 = Settings(
            cors_origins=["http://example.com", "http://test.com"],
            airtable_api_key="test_key",
            airtable_base_id="test_base",
            supabase_url="https://test.supabase.co",
            supabase_key="test_key",
            pinecone_api_key="test_key",
            pinecone_environment="test",
            youtube_api_key="test_key",
            openai_api_key="test_key",
            jwt_secret_key="test_secret",
            session_secret="test_session",
        )
        assert settings2.cors_origins == ["http://example.com", "http://test.com"]

    def test_environment_properties(self):
        """Test environment property methods."""
        # Development
        settings = Settings(
            environment="development",
            airtable_api_key="test_key",
            airtable_base_id="test_base",
            supabase_url="https://test.supabase.co",
            supabase_key="test_key",
            pinecone_api_key="test_key",
            pinecone_environment="test",
            youtube_api_key="test_key",
            openai_api_key="test_key",
            jwt_secret_key="test_secret",
            session_secret="test_session",
        )
        assert settings.is_development is True
        assert settings.is_production is False
        assert settings.is_test is False

        # Production
        settings.environment = "production"
        assert settings.is_development is False
        assert settings.is_production is True
        assert settings.is_test is False

    def test_url_formatting(self):
        """Test URL formatting methods."""
        settings = Settings(
            database_url="user:pass@localhost:5432/db",
            redis_url="localhost:6379",
            airtable_api_key="test_key",
            airtable_base_id="test_base",
            supabase_url="https://test.supabase.co",
            supabase_key="test_key",
            pinecone_api_key="test_key",
            pinecone_environment="test",
            youtube_api_key="test_key",
            openai_api_key="test_key",
            jwt_secret_key="test_secret",
            session_secret="test_session",
        )
        
        assert settings.get_database_url() == "postgresql://user:pass@localhost:5432/db"
        assert settings.get_redis_url() == "redis://localhost:6379"

        # Test with existing prefixes
        settings.database_url = "postgresql://user:pass@localhost:5432/db"
        settings.redis_url = "redis://localhost:6379"
        assert settings.get_database_url() == "postgresql://user:pass@localhost:5432/db"
        assert settings.get_redis_url() == "redis://localhost:6379"

    @patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG",
        "AIRTABLE_API_KEY": "env_airtable_key",
        "AIRTABLE_BASE_ID": "env_base_id",
        "SUPABASE_URL": "https://env.supabase.co",
        "SUPABASE_KEY": "env_supabase_key",
        "PINECONE_API_KEY": "env_pinecone_key",
        "PINECONE_ENVIRONMENT": "env_pinecone_env",
        "YOUTUBE_API_KEY": "env_youtube_key",
        "OPENAI_API_KEY": "env_openai_key",
        "JWT_SECRET_KEY": "env_jwt_secret",
        "SESSION_SECRET": "env_session_secret",
    })
    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        settings = Settings()
        
        assert settings.environment == "production"
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        assert settings.airtable_api_key == "env_airtable_key"
        assert settings.pinecone_environment == "env_pinecone_env"

    def test_optional_fields(self):
        """Test optional fields can be None."""
        settings = Settings(
            airtable_api_key="test_key",
            airtable_base_id="test_base",
            supabase_url="https://test.supabase.co",
            supabase_key="test_key",
            pinecone_api_key="test_key",
            pinecone_environment="test",
            youtube_api_key="test_key",
            openai_api_key="test_key",
            jwt_secret_key="test_secret",
            session_secret="test_session",
        )
        
        assert settings.sentry_dsn is None
        assert settings.stripe_api_key is None
        assert settings.aws_access_key_id is None

    def test_get_settings_cache(self):
        """Test that get_settings returns cached instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2  # Same object reference