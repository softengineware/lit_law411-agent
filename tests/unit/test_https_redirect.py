"""Tests for HTTPS redirect middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.core.https_redirect import HTTPSRedirectMiddleware, get_https_redirect_middleware


@pytest.fixture
def app_with_https_redirect():
    """Create FastAPI app with HTTPS redirect middleware."""
    app = FastAPI()
    
    # Add HTTPS redirect middleware
    middleware = HTTPSRedirectMiddleware(
        app=app,
        enabled=True,
        redirect_status_code=301,
        exclude_paths=["/health", "/metrics"],
        exclude_hosts=["testserver"]  # TestClient uses 'testserver' as host
    )
    app.add_middleware(type(middleware), **middleware.__dict__)
    
    @app.get("/test")
    def test_endpoint():
        return {"message": "test"}
    
    @app.get("/health")
    def health_endpoint():
        return {"status": "healthy"}
    
    return app


@pytest.fixture
def client(app_with_https_redirect):
    """Create test client."""
    return TestClient(app_with_https_redirect)


def test_https_redirect_disabled():
    """Test HTTPS redirect when disabled."""
    app = FastAPI()
    middleware = HTTPSRedirectMiddleware(app=app, enabled=False)
    app.add_middleware(type(middleware), **middleware.__dict__)
    
    @app.get("/test")
    def test_endpoint():
        return {"message": "test"}
    
    client = TestClient(app)
    response = client.get("/test")
    
    # Should not redirect when disabled
    assert response.status_code == 200
    assert response.json() == {"message": "test"}


def test_excluded_paths(client):
    """Test that excluded paths are not redirected."""
    # Health endpoint should not be redirected
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_excluded_hosts():
    """Test that excluded hosts are not redirected."""
    # TestClient uses 'testserver' as host which we excluded
    # So regular endpoints should work without redirect
    app = FastAPI()
    middleware = HTTPSRedirectMiddleware(
        app=app,
        enabled=True,
        exclude_hosts=["testserver"]
    )
    app.add_middleware(type(middleware), **middleware.__dict__)
    
    @app.get("/test")
    def test_endpoint():
        return {"message": "test"}
    
    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200


def test_https_request_not_redirected():
    """Test that HTTPS requests are not redirected."""
    app = FastAPI()
    middleware = HTTPSRedirectMiddleware(app=app, enabled=True)
    app.add_middleware(type(middleware), **middleware.__dict__)
    
    @app.get("/test")
    def test_endpoint():
        return {"message": "test"}
    
    client = TestClient(app)
    # Simulate HTTPS request with headers
    response = client.get(
        "/test",
        headers={"X-Forwarded-Proto": "https"}
    )
    assert response.status_code == 200
    assert response.json() == {"message": "test"}


def test_factory_function_production():
    """Test factory function for production environment."""
    middleware = get_https_redirect_middleware(
        environment="production",
        exclude_paths=["/health"]
    )
    assert middleware.enabled is True
    assert "/health" in middleware.exclude_paths


def test_factory_function_development():
    """Test factory function for development environment."""
    middleware = get_https_redirect_middleware(environment="development")
    assert middleware.enabled is False


def test_factory_function_force_enabled():
    """Test factory function with force_enabled."""
    middleware = get_https_redirect_middleware(
        environment="development",
        force_enabled=True
    )
    assert middleware.enabled is True


def test_various_https_headers():
    """Test detection of HTTPS via various headers."""
    app = FastAPI()
    middleware = HTTPSRedirectMiddleware(app=app, enabled=True)
    app.add_middleware(type(middleware), **middleware.__dict__)
    
    @app.get("/test")
    def test_endpoint():
        return {"message": "test"}
    
    client = TestClient(app)
    
    # Test various HTTPS detection headers
    https_headers = [
        {"X-Forwarded-Proto": "https"},
        {"X-Forwarded-SSL": "on"},
        {"X-URL-Scheme": "https"},
    ]
    
    for headers in https_headers:
        response = client.get("/test", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "test"}