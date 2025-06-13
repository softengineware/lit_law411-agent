"""CSRF (Cross-Site Request Forgery) protection for FastAPI.

This module provides CSRF protection middleware and utilities
for securing state-changing operations.
"""

import secrets
import hmac
import hashlib
from typing import Optional, Tuple
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException, status
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class CSRFToken(BaseModel):
    """CSRF token model."""
    token: str
    timestamp: datetime
    session_id: str


class CSRFProtection:
    """CSRF protection utility class."""
    
    def __init__(
        self,
        secret_key: str,
        token_length: int = 32,
        max_age: int = 3600,  # 1 hour
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        form_field: str = "csrf_token"
    ):
        """Initialize CSRF protection.
        
        Args:
            secret_key: Secret key for token generation
            token_length: Length of generated tokens
            max_age: Token validity in seconds
            cookie_name: Name of CSRF cookie
            header_name: Name of CSRF header
            form_field: Name of form field for CSRF token
        """
        self.secret_key = secret_key
        self.token_length = token_length
        self.max_age = max_age
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.form_field = form_field
    
    def generate_token(self, session_id: str) -> str:
        """Generate a CSRF token.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Generated CSRF token
        """
        # Generate random token
        random_token = secrets.token_urlsafe(self.token_length)
        
        # Create timestamp
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Create token data
        token_data = f"{random_token}|{timestamp}|{session_id}"
        
        # Sign the token
        signature = self._sign_token(token_data)
        
        # Combine token and signature
        csrf_token = f"{token_data}|{signature}"
        
        return csrf_token
    
    def _sign_token(self, token_data: str) -> str:
        """Sign token data with HMAC.
        
        Args:
            token_data: Token data to sign
            
        Returns:
            HMAC signature
        """
        return hmac.new(
            self.secret_key.encode(),
            token_data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def validate_token(self, token: str, session_id: str) -> bool:
        """Validate a CSRF token.
        
        Args:
            token: CSRF token to validate
            session_id: Session identifier
            
        Returns:
            True if token is valid
        """
        try:
            # Parse token
            parts = token.split('|')
            if len(parts) != 4:
                return False
            
            random_token, timestamp_str, token_session_id, signature = parts
            
            # Verify session ID
            if token_session_id != session_id:
                logger.warning("CSRF token session mismatch")
                return False
            
            # Verify signature
            token_data = f"{random_token}|{timestamp_str}|{token_session_id}"
            expected_signature = self._sign_token(token_data)
            
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("CSRF token signature mismatch")
                return False
            
            # Check token age
            timestamp = datetime.fromisoformat(timestamp_str)
            age = datetime.now(timezone.utc) - timestamp
            
            if age.total_seconds() > self.max_age:
                logger.warning("CSRF token expired")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"CSRF token validation error: {e}")
            return False
    
    def get_token_from_request(self, request: Request) -> Optional[str]:
        """Extract CSRF token from request.
        
        Args:
            request: The incoming request
            
        Returns:
            CSRF token if found
        """
        # Check header first
        token = request.headers.get(self.header_name)
        if token:
            return token
        
        # Check form data
        if hasattr(request, 'form'):
            form_data = request.form()
            if self.form_field in form_data:
                return form_data[self.form_field]
        
        # Check JSON body
        if request.headers.get('content-type') == 'application/json':
            try:
                body = request.json()
                if isinstance(body, dict) and self.form_field in body:
                    return body[self.form_field]
            except:
                pass
        
        return None


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware."""
    
    def __init__(
        self,
        app,
        csrf_protection: CSRFProtection,
        exempt_paths: Optional[list] = None,
        safe_methods: Optional[list] = None
    ):
        """Initialize CSRF middleware.
        
        Args:
            app: The ASGI application
            csrf_protection: CSRF protection instance
            exempt_paths: Paths to exempt from CSRF
            safe_methods: HTTP methods to exempt
        """
        super().__init__(app)
        self.csrf = csrf_protection
        self.exempt_paths = exempt_paths or []
        self.safe_methods = safe_methods or ["GET", "HEAD", "OPTIONS", "TRACE"]
    
    async def dispatch(self, request: Request, call_next):
        """Process request with CSRF protection.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler
            
        Returns:
            Response with CSRF cookie if needed
        """
        # Skip CSRF for safe methods
        if request.method in self.safe_methods:
            return await call_next(request)
        
        # Skip CSRF for exempt paths
        for path in self.exempt_paths:
            if request.url.path.startswith(path):
                return await call_next(request)
        
        # Get session ID (from cookie or generate)
        session_id = request.cookies.get("session_id")
        if not session_id:
            # For APIs, CSRF might not be needed without sessions
            # This is a simplified example
            return await call_next(request)
        
        # Validate CSRF token
        csrf_token = self.csrf.get_token_from_request(request)
        if not csrf_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing"
            )
        
        if not self.csrf.validate_token(csrf_token, session_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token"
            )
        
        # Process request
        response = await call_next(request)
        
        # Generate new token for response
        new_token = self.csrf.generate_token(session_id)
        response.set_cookie(
            key=self.csrf.cookie_name,
            value=new_token,
            httponly=True,
            secure=True,  # Only over HTTPS
            samesite="strict",
            max_age=self.csrf.max_age
        )
        
        return response


def get_csrf_token(request: Request, csrf_protection: CSRFProtection) -> str:
    """Get or generate CSRF token for a request.
    
    Args:
        request: The incoming request
        csrf_protection: CSRF protection instance
        
    Returns:
        CSRF token
    """
    session_id = request.cookies.get("session_id", "default")
    return csrf_protection.generate_token(session_id)