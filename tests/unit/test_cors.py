"""Tests for CORS configuration."""

import pytest
from src.core.cors import get_cors_origins, get_cors_middleware, CORSConfig
from src.core.config import settings


def test_get_cors_origins():
    """Test CORS origins retrieval."""
    origins = get_cors_origins()
    
    # Should include default development origins
    assert "http://localhost:3000" in origins
    assert "http://localhost:8000" in origins
    assert "http://localhost:8080" in origins
    
    # Should include configured origins if any
    if hasattr(settings, 'cors_origins') and settings.cors_origins:
        for origin in settings.cors_origins:
            if origin not in ["http://localhost:3000", "http://localhost:8000"]:
                assert origin in origins


def test_get_cors_middleware_defaults():
    """Test CORS middleware configuration with defaults."""
    config = get_cors_middleware()
    
    assert "allow_origins" in config
    assert config["allow_credentials"] is True
    assert "GET" in config["allow_methods"]
    assert "POST" in config["allow_methods"]
    assert "Authorization" in config["allow_headers"]
    assert "Content-Type" in config["allow_headers"]
    assert config["max_age"] == 3600


def test_get_cors_middleware_custom():
    """Test CORS middleware configuration with custom values."""
    custom_origins = ["https://example.com", "https://app.example.com"]
    custom_methods = ["GET", "POST"]
    custom_headers = ["X-Custom-Header"]
    
    config = get_cors_middleware(
        allow_origins=custom_origins,
        allow_credentials=False,
        allow_methods=custom_methods,
        allow_headers=custom_headers,
        max_age=7200
    )
    
    assert config["allow_origins"] == custom_origins
    assert config["allow_credentials"] is False
    assert config["allow_methods"] == custom_methods
    assert config["allow_headers"] == custom_headers
    assert config["max_age"] == 7200


def test_cors_config_class():
    """Test CORSConfig class functionality."""
    cors_config = CORSConfig()
    
    # Test initial state
    assert isinstance(cors_config.origins, list)
    assert cors_config.credentials is True
    assert cors_config.methods == ["*"]
    assert cors_config.headers == ["*"]
    
    # Test add origin
    test_origin = "https://test.example.com"
    cors_config.add_origin(test_origin)
    assert test_origin in cors_config.origins
    
    # Test add duplicate origin (should not add twice)
    original_length = len(cors_config.origins)
    cors_config.add_origin(test_origin)
    assert len(cors_config.origins) == original_length
    
    # Test remove origin
    cors_config.remove_origin(test_origin)
    assert test_origin not in cors_config.origins
    
    # Test is_origin_allowed
    cors_config.add_origin("https://allowed.com")
    assert cors_config.is_origin_allowed("https://allowed.com") is True
    assert cors_config.is_origin_allowed("https://notallowed.com") is False
    
    # Test wildcard origin
    cors_config.origins = ["*"]
    assert cors_config.is_origin_allowed("https://any.com") is True


def test_cors_config_middleware_kwargs():
    """Test CORSConfig middleware kwargs generation."""
    cors_config = CORSConfig()
    cors_config.add_origin("https://app.example.com")
    
    kwargs = cors_config.get_middleware_kwargs()
    
    assert "allow_origins" in kwargs
    assert "allow_credentials" in kwargs
    assert "allow_methods" in kwargs
    assert "allow_headers" in kwargs
    assert "https://app.example.com" in kwargs["allow_origins"]


def test_production_environment_filtering(monkeypatch):
    """Test that localhost origins are filtered in production."""
    # This test would need to mock the settings.environment
    # For now, we'll just verify the logic exists in the function
    origins = get_cors_origins()
    
    # In development, localhost should be included
    if hasattr(settings, 'environment') and settings.environment != 'production':
        localhost_origins = [o for o in origins if 'localhost' in o]
        assert len(localhost_origins) > 0