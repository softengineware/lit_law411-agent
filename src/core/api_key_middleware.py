"""API key authentication middleware for alternative authentication."""

from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..models.sqlalchemy.api_key import APIKey
from ..models.sqlalchemy.user import User
from .api_key_utils import (
    APIKeyManager,
    APIKeyError,
    APIKeyNotFoundError,
    APIKeyExpiredError,
    APIKeyInactiveError,
    APIKeyRateLimitError,
    APIKeyScopeError,
)
from .auth_middleware import get_current_user  # For fallback to JWT
from .logging import get_logger

logger = get_logger(__name__)

# Security scheme for API key (can also use HTTPBearer for X-API-Key header)
api_key_security = HTTPBearer(auto_error=False)


class APIKeyAuthenticationError(Exception):
    """API key authentication error."""
    pass


class APIKeyAuthorizationError(Exception):
    """API key authorization error."""
    pass


async def get_api_key_from_request(request: Request) -> Optional[str]:
    """
    Extract API key from request headers.
    
    Looks for API key in multiple locations:
    1. Authorization header (Bearer token)
    2. X-API-Key header
    3. Query parameter 'api_key'
    
    Args:
        request: FastAPI request object
        
    Returns:
        API key string if found, None otherwise
    """
    # Try Authorization header first (Bearer)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
        # Check if it's an API key (starts with llk_) vs JWT
        if token.startswith("llk_"):
            return token
    
    # Try X-API-Key header
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        return api_key_header
    
    # Try query parameter (less secure, but sometimes needed)
    api_key_param = request.query_params.get("api_key")
    if api_key_param:
        return api_key_param
    
    return None


async def get_current_user_from_api_key(
    request: Request,
    db: Session = Depends(get_db),
    required_scope: Optional[str] = None
) -> Optional[Tuple[User, APIKey]]:
    """
    Get current user from API key authentication.
    
    Args:
        request: FastAPI request object
        db: Database session
        required_scope: Required scope for the operation
        
    Returns:
        Tuple of (User, APIKey) if authenticated, None otherwise
        
    Raises:
        HTTPException: If API key is invalid or insufficient permissions
    """
    try:
        # Extract API key from request
        api_key = await get_api_key_from_request(request)
        if not api_key:
            return None
        
        # Validate API key
        api_key_obj, user = await APIKeyManager.validate_api_key(
            db=db,
            api_key=api_key,
            required_scope=required_scope,
            check_rate_limit=True
        )
        
        # Increment usage counters
        user_agent = request.headers.get("user-agent")
        client_ip = request.client.host if request.client else None
        
        await APIKeyManager.increment_api_key_usage(
            db=db,
            api_key_obj=api_key_obj,
            user_agent=user_agent,
            ip_address=client_ip
        )
        
        logger.debug(f"API key authentication successful: {api_key_obj.key_prefix}")
        return user, api_key_obj
        
    except APIKeyNotFoundError:
        logger.warning("API key not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except APIKeyExpiredError:
        logger.warning("Expired API key used")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except APIKeyInactiveError:
        logger.warning("Inactive API key used")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except APIKeyRateLimitError as e:
        logger.warning(f"API key rate limited: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": "60"},
        )
    except APIKeyScopeError as e:
        logger.warning(f"API key insufficient scope: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except APIKeyError as e:
        logger.error(f"API key authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected error during API key authentication: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error",
        )


async def get_current_user_flexible(
    request: Request,
    db: Session = Depends(get_db),
    required_scope: Optional[str] = None
) -> Optional[Tuple[User, Optional[APIKey]]]:
    """
    Get current user using either JWT or API key authentication.
    
    Tries API key authentication first, then falls back to JWT.
    
    Args:
        request: FastAPI request object
        db: Database session
        required_scope: Required scope for API key authentication
        
    Returns:
        Tuple of (User, APIKey) if API key auth, or (User, None) if JWT auth
        None if no authentication provided
        
    Raises:
        HTTPException: If authentication fails
    """
    # Try API key authentication first
    try:
        api_key_result = await get_current_user_from_api_key(
            request=request,
            db=db,
            required_scope=required_scope
        )
        if api_key_result:
            user, api_key_obj = api_key_result
            logger.debug(f"Flexible auth: API key successful for user {user.email}")
            return user, api_key_obj
    except HTTPException as e:
        # If it's a rate limit error, don't fall back to JWT
        if e.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            raise
        # For other API key errors, we'll try JWT fallback
        logger.debug(f"API key auth failed, trying JWT fallback: {e.detail}")
    
    # Fall back to JWT authentication
    try:
        # Use the existing JWT authentication
        credentials = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # Only use JWT if it's not an API key
            if not token.startswith("llk_"):
                from fastapi.security import HTTPAuthorizationCredentials
                credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        
        if credentials:
            # Import here to avoid circular imports
            from .auth_middleware import get_current_user
            user = await get_current_user(credentials=credentials, db=db)
            if user:
                logger.debug(f"Flexible auth: JWT successful for user {user.email}")
                return user, None
    except Exception as e:
        logger.debug(f"JWT auth also failed: {str(e)}")
    
    return None


async def get_current_user_api_key_only(
    request: Request,
    db: Session = Depends(get_db),
    required_scope: Optional[str] = None
) -> Tuple[User, APIKey]:
    """
    Get current user using API key authentication only (no JWT fallback).
    
    Args:
        request: FastAPI request object
        db: Database session
        required_scope: Required scope for the operation
        
    Returns:
        Tuple of (User, APIKey)
        
    Raises:
        HTTPException: If API key authentication fails
    """
    result = await get_current_user_from_api_key(
        request=request,
        db=db,
        required_scope=required_scope
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return result


async def get_current_user_any_auth(
    request: Request,
    db: Session = Depends(get_db),
    required_scope: Optional[str] = None
) -> Tuple[User, Optional[APIKey]]:
    """
    Get current user using any authentication method (JWT or API key).
    Requires authentication.
    
    Args:
        request: FastAPI request object
        db: Database session
        required_scope: Required scope for API key authentication
        
    Returns:
        Tuple of (User, APIKey) if API key auth, or (User, None) if JWT auth
        
    Raises:
        HTTPException: If no authentication provided or authentication fails
    """
    result = await get_current_user_flexible(
        request=request,
        db=db,
        required_scope=required_scope
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (JWT or API key)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return result


def require_api_key_scope(required_scope: str):
    """
    Decorator to require specific API key scope.
    
    Args:
        required_scope: Required API key scope
        
    Returns:
        Dependency function
    """
    async def scope_checker(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Tuple[User, APIKey]:
        return await get_current_user_api_key_only(
            request=request,
            db=db,
            required_scope=required_scope
        )
    
    return scope_checker


def require_any_auth_with_scope(required_scope: Optional[str] = None):
    """
    Decorator to require authentication (JWT or API key) with optional scope.
    
    Args:
        required_scope: Required scope for API key authentication
        
    Returns:
        Dependency function
    """
    async def auth_checker(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Tuple[User, Optional[APIKey]]:
        return await get_current_user_any_auth(
            request=request,
            db=db,
            required_scope=required_scope
        )
    
    return auth_checker


class APIKeyRateLimitMiddleware:
    """Rate limiting middleware specifically for API keys."""
    
    def __init__(self):
        pass
    
    async def __call__(self, request: Request, call_next):
        """Process API key rate limiting."""
        # Get API key from request
        api_key = await get_api_key_from_request(request)
        
        if api_key:
            # Check if it's a valid API key format
            if APIKeyManager.validate_api_key_format(api_key):
                # Add rate limit headers if it's an API key request
                response = await call_next(request)
                
                # Try to add rate limit info to response headers
                try:
                    # Get database session (simplified for middleware)
                    from ..db.database import SessionLocal
                    db = SessionLocal()
                    try:
                        api_key_obj = await APIKeyManager.find_api_key_by_raw_key(db, api_key)
                        if api_key_obj:
                            rate_limit_info = await APIKeyManager.get_api_key_rate_limit_status(api_key_obj)
                            
                            # Add rate limit headers
                            response.headers["X-RateLimit-Limit-Minute"] = str(api_key_obj.rate_limit_per_minute)
                            response.headers["X-RateLimit-Limit-Hour"] = str(api_key_obj.rate_limit_per_hour)
                            response.headers["X-RateLimit-Limit-Day"] = str(api_key_obj.rate_limit_per_day)
                            
                            response.headers["X-RateLimit-Remaining-Minute"] = str(
                                rate_limit_info["remaining"]["this_minute"]
                            )
                            response.headers["X-RateLimit-Remaining-Hour"] = str(
                                rate_limit_info["remaining"]["this_hour"]
                            )
                            response.headers["X-RateLimit-Remaining-Day"] = str(
                                rate_limit_info["remaining"]["today"]
                            )
                            
                            response.headers["X-RateLimit-Reset-Minute"] = str(
                                int(rate_limit_info["reset_times"]["minute"].timestamp())
                            )
                            response.headers["X-RateLimit-Reset-Hour"] = str(
                                int(rate_limit_info["reset_times"]["hour"].timestamp())
                            )
                            response.headers["X-RateLimit-Reset-Day"] = str(
                                int(rate_limit_info["reset_times"]["day"].timestamp())
                            )
                    finally:
                        db.close()
                except Exception as e:
                    logger.error(f"Error adding rate limit headers: {str(e)}")
                
                return response
        
        # Not an API key request, continue normally
        return await call_next(request)