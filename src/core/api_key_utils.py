"""API key generation, validation, and management utilities."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any

from sqlalchemy.orm import Session

from ..db.redis_client import cache
from ..models.sqlalchemy.api_key import APIKey
from ..models.sqlalchemy.user import User
from .config import get_settings
from .logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class APIKeyError(Exception):
    """Base exception for API key operations."""
    pass


class APIKeyNotFoundError(APIKeyError):
    """API key not found error."""
    pass


class APIKeyExpiredError(APIKeyError):
    """API key expired error."""
    pass


class APIKeyInactiveError(APIKeyError):
    """API key inactive error."""
    pass


class APIKeyRateLimitError(APIKeyError):
    """API key rate limit exceeded error."""
    pass


class APIKeyScopeError(APIKeyError):
    """API key insufficient scope error."""
    pass


class APIKeyManager:
    """API key management utilities."""
    
    @staticmethod
    def generate_api_key() -> str:
        """
        Generate a new API key.
        
        Format: llk_[32_random_chars] (lit law411 key)
        Total length: 36 characters
        
        Returns:
            Generated API key string
        """
        return APIKey.generate_key()
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """
        Hash an API key for secure storage.
        
        Args:
            api_key: The raw API key to hash
            
        Returns:
            Hashed API key
        """
        return APIKey.hash_key(api_key)
    
    @staticmethod
    def get_key_prefix(api_key: str) -> str:
        """
        Get the prefix of an API key for identification.
        
        Args:
            api_key: The API key to get prefix from
            
        Returns:
            First 8 characters of the API key
        """
        return APIKey.get_key_prefix(api_key)
    
    @staticmethod
    def validate_api_key_format(api_key: str) -> bool:
        """
        Validate API key format.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            True if format is valid, False otherwise
        """
        if not api_key:
            return False
        
        # Check if it starts with our prefix
        if not api_key.startswith("llk_"):
            return False
        
        # Check length (should be around 36 characters)
        if len(api_key) < 20 or len(api_key) > 50:
            return False
        
        # Check if the remaining part is base64-like
        remaining = api_key[4:]  # Remove "llk_" prefix
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        return all(c in valid_chars for c in remaining)
    
    @staticmethod
    async def find_api_key_by_hash(db: Session, key_hash: str) -> Optional[APIKey]:
        """
        Find API key by hash.
        
        Args:
            db: Database session
            key_hash: Hashed API key
            
        Returns:
            APIKey object if found, None otherwise
        """
        return db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()
    
    @staticmethod
    async def find_api_key_by_raw_key(db: Session, api_key: str) -> Optional[APIKey]:
        """
        Find API key by raw key (will hash it first).
        
        Args:
            db: Database session
            api_key: Raw API key
            
        Returns:
            APIKey object if found, None otherwise
        """
        key_hash = APIKeyManager.hash_api_key(api_key)
        return await APIKeyManager.find_api_key_by_hash(db, key_hash)
    
    @staticmethod
    async def validate_api_key(
        db: Session,
        api_key: str,
        required_scope: Optional[str] = None,
        check_rate_limit: bool = True
    ) -> Tuple[APIKey, User]:
        """
        Validate API key and return the associated API key and user.
        
        Args:
            db: Database session
            api_key: Raw API key to validate
            required_scope: Required scope for the operation
            check_rate_limit: Whether to check rate limits
            
        Returns:
            Tuple of (APIKey, User) objects
            
        Raises:
            APIKeyError: If validation fails
        """
        # Validate format
        if not APIKeyManager.validate_api_key_format(api_key):
            raise APIKeyError("Invalid API key format")
        
        # Find API key in database
        api_key_obj = await APIKeyManager.find_api_key_by_raw_key(db, api_key)
        if not api_key_obj:
            logger.warning(f"API key not found: {APIKeyManager.get_key_prefix(api_key)}")
            raise APIKeyNotFoundError("API key not found")
        
        # Check if key is active
        if not api_key_obj.is_active:
            logger.warning(f"Inactive API key used: {api_key_obj.key_prefix}")
            raise APIKeyInactiveError("API key is inactive")
        
        # Check if key has expired
        if api_key_obj.is_expired:
            logger.warning(f"Expired API key used: {api_key_obj.key_prefix}")
            raise APIKeyExpiredError("API key has expired")
        
        # Get associated user
        user = db.query(User).filter(User.id == api_key_obj.user_id).first()
        if not user or not user.is_active:
            logger.warning(f"API key with invalid user: {api_key_obj.key_prefix}")
            raise APIKeyError("Associated user not found or inactive")
        
        # Check required scope
        if required_scope and not api_key_obj.has_scope(required_scope):
            logger.warning(f"API key missing scope '{required_scope}': {api_key_obj.key_prefix}")
            raise APIKeyScopeError(f"API key missing required scope: {required_scope}")
        
        # Check rate limits if requested
        if check_rate_limit:
            if api_key_obj.is_rate_limited("minute"):
                logger.warning(f"API key rate limited (minute): {api_key_obj.key_prefix}")
                raise APIKeyRateLimitError("Rate limit exceeded: too many requests per minute")
            
            if api_key_obj.is_rate_limited("hour"):
                logger.warning(f"API key rate limited (hour): {api_key_obj.key_prefix}")
                raise APIKeyRateLimitError("Rate limit exceeded: too many requests per hour")
            
            if api_key_obj.is_rate_limited("day"):
                logger.warning(f"API key rate limited (day): {api_key_obj.key_prefix}")
                raise APIKeyRateLimitError("Rate limit exceeded: too many requests per day")
        
        logger.debug(f"API key validated successfully: {api_key_obj.key_prefix}")
        return api_key_obj, user
    
    @staticmethod
    async def create_api_key(
        db: Session,
        user: User,
        name: str,
        description: Optional[str] = None,
        scopes: Optional[list] = None,
        expires_days: Optional[int] = None,
        rate_limits: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, APIKey]:
        """
        Create a new API key for a user.
        
        Args:
            db: Database session
            user: User to create the key for
            name: Human-readable name for the key
            description: Optional description
            scopes: List of allowed scopes
            expires_days: Number of days until expiration
            rate_limits: Rate limit configuration
            metadata: Additional metadata
            
        Returns:
            Tuple of (raw_api_key, APIKey_object)
        """
        # Generate the API key
        raw_key = APIKeyManager.generate_api_key()
        key_hash = APIKeyManager.hash_api_key(raw_key)
        key_prefix = APIKeyManager.get_key_prefix(raw_key)
        
        # Calculate expiration
        expires_at = None
        if expires_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
        
        # Set default rate limits based on user tier
        default_rate_limits = {
            "rate_limit_per_minute": 60,
            "rate_limit_per_hour": 1000,
            "rate_limit_per_day": 10000
        }
        
        if user.subscription_tier == "free":
            default_rate_limits = {
                "rate_limit_per_minute": 10,
                "rate_limit_per_hour": 100,
                "rate_limit_per_day": 1000
            }
        elif user.subscription_tier == "basic":
            default_rate_limits = {
                "rate_limit_per_minute": 30,
                "rate_limit_per_hour": 500,
                "rate_limit_per_day": 5000
            }
        elif user.subscription_tier in ["premium", "enterprise"]:
            default_rate_limits = {
                "rate_limit_per_minute": 100,
                "rate_limit_per_hour": 5000,
                "rate_limit_per_day": 50000
            }
        
        # Override with provided rate limits
        if rate_limits:
            default_rate_limits.update(rate_limits)
        
        # Create API key object
        api_key_obj = APIKey(
            name=name,
            description=description,
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=user.id,
            scopes=scopes or [],
            expires_at=expires_at,
            key_metadata=metadata or {},
            **default_rate_limits
        )
        
        db.add(api_key_obj)
        db.commit()
        db.refresh(api_key_obj)
        
        logger.info(f"API key created for user {user.email}: {key_prefix}")
        
        return raw_key, api_key_obj
    
    @staticmethod
    async def rotate_api_key(db: Session, api_key_obj: APIKey) -> Tuple[str, APIKey]:
        """
        Rotate an existing API key (generate new key, keep same settings).
        
        Args:
            db: Database session
            api_key_obj: Existing API key to rotate
            
        Returns:
            Tuple of (new_raw_api_key, updated_APIKey_object)
        """
        # Generate new key
        new_raw_key = APIKeyManager.generate_api_key()
        new_key_hash = APIKeyManager.hash_api_key(new_raw_key)
        new_key_prefix = APIKeyManager.get_key_prefix(new_raw_key)
        
        # Update the existing API key object
        api_key_obj.key_hash = new_key_hash
        api_key_obj.key_prefix = new_key_prefix
        api_key_obj.last_used_at = None
        api_key_obj.last_used_ip = None
        api_key_obj.user_agent = None
        
        # Reset usage counters
        api_key_obj.requests_today = 0
        api_key_obj.requests_this_hour = 0
        api_key_obj.requests_this_minute = 0
        
        db.commit()
        db.refresh(api_key_obj)
        
        logger.info(f"API key rotated: {new_key_prefix}")
        
        return new_raw_key, api_key_obj
    
    @staticmethod
    async def increment_api_key_usage(
        db: Session,
        api_key_obj: APIKey,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Increment API key usage counters.
        
        Args:
            db: Database session
            api_key_obj: API key to increment usage for
            user_agent: User agent from request
            ip_address: IP address from request
        """
        # Update usage counters
        api_key_obj.increment_usage()
        
        # Update metadata
        api_key_obj.update_metadata(user_agent, ip_address)
        
        db.commit()
        
        # Also cache the rate limit counters in Redis for fast access
        cache_key_base = f"api_key_rate_limit:{api_key_obj.id}"
        
        # Cache minute counter (expires in 60 seconds)
        await cache.set(
            f"{cache_key_base}:minute",
            api_key_obj.requests_this_minute,
            ttl=60
        )
        
        # Cache hour counter (expires in 3600 seconds)
        await cache.set(
            f"{cache_key_base}:hour",
            api_key_obj.requests_this_hour,
            ttl=3600
        )
        
        # Cache day counter (expires in 86400 seconds)
        await cache.set(
            f"{cache_key_base}:day",
            api_key_obj.requests_today,
            ttl=86400
        )
    
    @staticmethod
    async def get_api_key_rate_limit_status(api_key_obj: APIKey) -> Dict[str, Any]:
        """
        Get current rate limit status for an API key.
        
        Args:
            api_key_obj: API key to check
            
        Returns:
            Dictionary with rate limit information
        """
        now = datetime.now(timezone.utc)
        
        return {
            "limits": {
                "per_minute": api_key_obj.rate_limit_per_minute,
                "per_hour": api_key_obj.rate_limit_per_hour,
                "per_day": api_key_obj.rate_limit_per_day,
            },
            "current": {
                "requests_this_minute": api_key_obj.requests_this_minute,
                "requests_this_hour": api_key_obj.requests_this_hour,
                "requests_today": api_key_obj.requests_today,
            },
            "remaining": {
                "this_minute": max(0, api_key_obj.rate_limit_per_minute - api_key_obj.requests_this_minute),
                "this_hour": max(0, api_key_obj.rate_limit_per_hour - api_key_obj.requests_this_hour),
                "today": max(0, api_key_obj.rate_limit_per_day - api_key_obj.requests_today),
            },
            "reset_times": {
                # Reset times are calculated based on the current minute/hour/day
                "minute": now.replace(second=0, microsecond=0) + timedelta(minutes=1),
                "hour": now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1),
                "day": now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
            },
            "is_rate_limited": {
                "minute": api_key_obj.is_rate_limited("minute"),
                "hour": api_key_obj.is_rate_limited("hour"),
                "day": api_key_obj.is_rate_limited("day"),
            },
        }