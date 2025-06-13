"""Authentication middleware for JWT token validation."""

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..models.sqlalchemy.user import User
from .logging import get_logger
from .security import TokenError, verify_token

logger = get_logger(__name__)

# Security scheme for Bearer token
security = HTTPBearer(auto_error=False)


class AuthenticationError(Exception):
    """Authentication error."""
    pass


class AuthorizationError(Exception):
    """Authorization error."""
    pass


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials
        db: Database session
        
    Returns:
        User object if authenticated, None otherwise
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    if not credentials:
        return None
    
    try:
        # Verify the token
        payload = verify_token(credentials.credentials, token_type="access")
        
        # Extract user email from token
        user_email = payload.get("sub")
        if not user_email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user identifier",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user from database
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            logger.warning(f"User not found for email: {user_email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Inactive user attempted access: {user_email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if account is locked
        if user.is_account_locked:
            logger.warning(f"Locked user attempted access: {user_email}")
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is locked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except TokenError as e:
        logger.warning(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error",
        )


async def get_current_active_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """
    Get current active user, raising exception if not authenticated.
    
    Args:
        current_user: Current user from authentication
        
    Returns:
        Active user object
        
    Raises:
        HTTPException: If user is not authenticated
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current verified user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Verified user object
        
    Raises:
        HTTPException: If user is not verified
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )
    
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current superuser.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Superuser object
        
    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    
    return current_user


async def get_current_premium_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current premium user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Premium user object
        
    Raises:
        HTTPException: If user is not premium
    """
    if not current_user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium subscription required",
        )
    
    return current_user


def require_role(required_role: str):
    """
    Decorator to require specific user role.
    
    Args:
        required_role: Required user role
        
    Returns:
        Dependency function
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return current_user
    
    return role_checker


def require_permissions(required_permissions: list[str]):
    """
    Decorator to require specific permissions.
    
    Args:
        required_permissions: List of required permissions
        
    Returns:
        Dependency function
    """
    async def permission_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        user_permissions = current_user.permissions or []
        
        # Superusers have all permissions
        if current_user.is_superuser:
            return current_user
        
        # Check if user has all required permissions
        missing_permissions = set(required_permissions) - set(user_permissions)
        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(missing_permissions)}",
            )
        
        return current_user
    
    return permission_checker


class RateLimitMiddleware:
    """Rate limiting middleware for API endpoints."""
    
    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.requests = {}  # In production, use Redis
    
    async def __call__(self, request: Request, call_next):
        """Process rate limiting."""
        # This is a simplified implementation
        # In production, use Redis for distributed rate limiting
        client_ip = request.client.host if request.client else "unknown"
        
        # For now, just log and continue
        logger.debug(f"Rate limit check for IP: {client_ip}")
        
        response = await call_next(request)
        return response


def create_auth_dependency(
    require_verification: bool = False,
    require_premium: bool = False,
    required_role: Optional[str] = None,
    required_permissions: Optional[list[str]] = None
):
    """
    Create a custom authentication dependency with specific requirements.
    
    Args:
        require_verification: Require email verification
        require_premium: Require premium subscription
        required_role: Required user role
        required_permissions: Required permissions
        
    Returns:
        Authentication dependency function
    """
    async def auth_dependency(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        # Check verification requirement
        if require_verification and not current_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email verification required",
            )
        
        # Check premium requirement
        if require_premium and not current_user.is_premium:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Premium subscription required",
            )
        
        # Check role requirement
        if required_role and current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        
        # Check permissions requirement
        if required_permissions:
            user_permissions = current_user.permissions or []
            
            # Superusers have all permissions
            if not current_user.is_superuser:
                missing_permissions = set(required_permissions) - set(user_permissions)
                if missing_permissions:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Missing permissions: {', '.join(missing_permissions)}",
                    )
        
        return current_user
    
    return auth_dependency