"""API endpoints for API key management."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...core.api_key_middleware import get_current_user_any_auth
from ...core.api_key_utils import APIKeyManager, APIKeyError
from ...core.auth_middleware import get_current_active_user, get_current_superuser
from ...core.config import get_settings
from ...core.logging import get_logger
from ...core.rate_limiter import api_key_rate_limiter
from ...db.database import get_db
from ...models.pydantic.api_key import (
    APIKeyCreate,
    APIKeyUpdate,
    APIKeyResponse,
    APIKeyCreateResponse,
    APIKeyUsageStats,
    APIKeyListResponse,
    APIKeyRotateResponse,
    APIKeyDeleteResponse,
    RateLimitInfo,
)
from ...models.pydantic.auth import SuccessResponse, ErrorResponse
from ...models.sqlalchemy.api_key import APIKey
from ...models.sqlalchemy.user import User

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter(prefix="/api-keys", tags=["API Key Management"])


@router.post("", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    api_key_data: APIKeyCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new API key for the current user.
    
    Creates a new API key with the specified configuration.
    Returns the API key (only shown once) and key information.
    """
    try:
        # Check if user has reached API key limit
        existing_keys = db.query(APIKey).filter(
            APIKey.user_id == current_user.id,
            APIKey.is_active == True
        ).count()
        
        # Set limits based on subscription tier
        max_keys = 5  # Default
        if current_user.subscription_tier == "free":
            max_keys = 2
        elif current_user.subscription_tier == "basic":
            max_keys = 5
        elif current_user.subscription_tier in ["premium", "enterprise"]:
            max_keys = 20
        elif current_user.is_superuser:
            max_keys = 100
        
        if existing_keys >= max_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum number of API keys reached ({max_keys})"
            )
        
        # Check for duplicate name
        existing_name = db.query(APIKey).filter(
            APIKey.user_id == current_user.id,
            APIKey.name == api_key_data.name
        ).first()
        
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key with this name already exists"
            )
        
        # Prepare rate limits
        rate_limits = {
            "rate_limit_per_minute": api_key_data.rate_limit_per_minute,
            "rate_limit_per_hour": api_key_data.rate_limit_per_hour,
            "rate_limit_per_day": api_key_data.rate_limit_per_day,
        }
        
        # Create the API key
        raw_key, api_key_obj = await APIKeyManager.create_api_key(
            db=db,
            user=current_user,
            name=api_key_data.name,
            description=api_key_data.description,
            scopes=api_key_data.scopes,
            expires_days=api_key_data.expires_days,
            rate_limits=rate_limits,
            metadata=api_key_data.key_metadata
        )
        
        logger.info(
            "API key created",
            user_id=current_user.id,
            user_email=current_user.email,
            key_name=api_key_data.name,
            key_prefix=api_key_obj.key_prefix,
            client_ip=request.client.host if request.client else None
        )
        
        # Convert to response model
        key_info = APIKeyResponse.model_validate(api_key_obj.to_safe_dict())
        
        return APIKeyCreateResponse(
            message="API key created successfully",
            api_key=raw_key,
            key_info=key_info
        )
        
    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error creating API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key creation failed due to data conflict"
        )
    except APIKeyError as e:
        logger.error(f"API key creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API key creation failed: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key creation failed due to server error"
        )


@router.get("", response_model=APIKeyListResponse)
async def list_api_keys(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    include_inactive: bool = Query(False, description="Include inactive keys"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List all API keys for the current user.
    
    Returns paginated list of API keys with safe information
    (no actual key values or hashes).
    """
    try:
        # Build query
        query = db.query(APIKey).filter(APIKey.user_id == current_user.id)
        
        if not include_inactive:
            query = query.filter(APIKey.is_active == True)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        api_keys = query.order_by(APIKey.created_at.desc()).offset(offset).limit(page_size).all()
        
        # Convert to response models
        key_responses = []
        for api_key in api_keys:
            key_data = api_key.to_safe_dict()
            key_responses.append(APIKeyResponse.model_validate(key_data))
        
        return APIKeyListResponse(
            api_keys=key_responses,
            total=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error listing API keys for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API keys"
        )


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific API key.
    
    Returns detailed information about the API key
    (no actual key value or hash).
    """
    try:
        # Find the API key
        api_key = db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == current_user.id
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Convert to response model
        key_data = api_key.to_safe_dict()
        return APIKeyResponse.model_validate(key_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API key {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API key"
        )


@router.put("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: str,
    api_key_update: APIKeyUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing API key.
    
    Updates the specified API key's configuration.
    Cannot update the actual key value (use rotation for that).
    """
    try:
        # Find the API key
        api_key = db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == current_user.id
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Check for name conflicts if name is being updated
        if api_key_update.name and api_key_update.name != api_key.name:
            existing_name = db.query(APIKey).filter(
                APIKey.user_id == current_user.id,
                APIKey.name == api_key_update.name,
                APIKey.id != key_id
            ).first()
            
            if existing_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="API key with this name already exists"
                )
        
        # Update the API key
        update_data = api_key_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(api_key, field, value)
        
        db.commit()
        db.refresh(api_key)
        
        logger.info(
            "API key updated",
            user_id=current_user.id,
            key_id=key_id,
            key_prefix=api_key.key_prefix,
            updated_fields=list(update_data.keys()),
            client_ip=request.client.host if request.client else None
        )
        
        # Convert to response model
        key_data = api_key.to_safe_dict()
        return APIKeyResponse.model_validate(key_data)
        
    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error updating API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key update failed due to data conflict"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating API key {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key update failed"
        )


@router.post("/{key_id}/rotate", response_model=APIKeyRotateResponse)
async def rotate_api_key(
    key_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Rotate an API key (generate new key value).
    
    Generates a new API key value while keeping all other settings.
    The old key becomes invalid immediately.
    Returns the new API key (only shown once).
    """
    try:
        # Find the API key
        api_key = db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == current_user.id
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Store old prefix for logging
        old_prefix = api_key.key_prefix
        
        # Rotate the key
        new_raw_key, updated_api_key = await APIKeyManager.rotate_api_key(db, api_key)
        
        logger.info(
            "API key rotated",
            user_id=current_user.id,
            key_id=key_id,
            old_prefix=old_prefix,
            new_prefix=updated_api_key.key_prefix,
            client_ip=request.client.host if request.client else None
        )
        
        # Convert to response model
        key_data = updated_api_key.to_safe_dict()
        key_info = APIKeyResponse.model_validate(key_data)
        
        return APIKeyRotateResponse(
            message="API key rotated successfully",
            new_api_key=new_raw_key,
            key_info=key_info
        )
        
    except HTTPException:
        raise
    except APIKeyError as e:
        logger.error(f"API key rotation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API key rotation failed: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error rotating API key {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key rotation failed"
        )


@router.delete("/{key_id}", response_model=APIKeyDeleteResponse)
async def delete_api_key(
    key_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete (revoke) an API key.
    
    Permanently deletes the API key. This action cannot be undone.
    The key becomes invalid immediately.
    """
    try:
        # Find the API key
        api_key = db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == current_user.id
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Store info for logging
        key_prefix = api_key.key_prefix
        key_name = api_key.name
        
        # Delete the API key
        db.delete(api_key)
        db.commit()
        
        # Clear any cached rate limit data
        await api_key_rate_limiter.reset_api_key_limits(key_id)
        
        logger.info(
            "API key deleted",
            user_id=current_user.id,
            key_id=key_id,
            key_name=key_name,
            key_prefix=key_prefix,
            client_ip=request.client.host if request.client else None
        )
        
        return APIKeyDeleteResponse(
            message=f"API key '{key_name}' deleted successfully",
            deleted_key_id=key_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting API key {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key deletion failed"
        )


@router.get("/{key_id}/usage", response_model=APIKeyUsageStats)
async def get_api_key_usage(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get usage statistics for an API key.
    
    Returns detailed usage information including rate limits
    and current usage counters.
    """
    try:
        # Find the API key
        api_key = db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == current_user.id
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Calculate remaining requests
        remaining_minute = max(0, api_key.rate_limit_per_minute - api_key.requests_this_minute)
        remaining_hour = max(0, api_key.rate_limit_per_hour - api_key.requests_this_hour)
        remaining_day = max(0, api_key.rate_limit_per_day - api_key.requests_today)
        
        # Create usage stats response
        usage_stats = APIKeyUsageStats(
            key_id=api_key.id,
            key_name=api_key.name,
            key_prefix=api_key.key_prefix,
            total_requests=api_key.total_requests,
            requests_today=api_key.requests_today,
            requests_this_hour=api_key.requests_this_hour,
            requests_this_minute=api_key.requests_this_minute,
            rate_limit_per_minute=api_key.rate_limit_per_minute,
            rate_limit_per_hour=api_key.rate_limit_per_hour,
            rate_limit_per_day=api_key.rate_limit_per_day,
            remaining_minute=remaining_minute,
            remaining_hour=remaining_hour,
            remaining_day=remaining_day,
            last_used_at=api_key.last_used_at,
            last_used_ip=api_key.last_used_ip,
            user_agent=api_key.user_agent
        )
        
        return usage_stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API key usage {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API key usage"
        )


@router.get("/{key_id}/rate-limit", response_model=RateLimitInfo)
async def get_api_key_rate_limit(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current rate limit information for an API key.
    
    Returns detailed rate limit status including reset times.
    """
    try:
        # Find the API key
        api_key = db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == current_user.id
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Get rate limit status from the rate limiter
        rate_limit_info = await APIKeyManager.get_api_key_rate_limit_status(api_key)
        
        # Convert to response model
        rate_limit_response = RateLimitInfo(
            limit_per_minute=api_key.rate_limit_per_minute,
            limit_per_hour=api_key.rate_limit_per_hour,
            limit_per_day=api_key.rate_limit_per_day,
            remaining_minute=rate_limit_info["remaining"]["this_minute"],
            remaining_hour=rate_limit_info["remaining"]["this_hour"],
            remaining_day=rate_limit_info["remaining"]["today"],
            reset_minute=rate_limit_info["reset_times"]["minute"],
            reset_hour=rate_limit_info["reset_times"]["hour"],
            reset_day=rate_limit_info["reset_times"]["day"]
        )
        
        return rate_limit_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API key rate limit {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve rate limit information"
        )


# Admin endpoints (superuser only)
@router.get("/admin/all", response_model=APIKeyListResponse)
async def admin_list_all_api_keys(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    include_inactive: bool = Query(False, description="Include inactive keys"),
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to list all API keys across all users.
    
    Requires superuser privileges.
    """
    try:
        # Build query
        query = db.query(APIKey)
        
        if user_id:
            query = query.filter(APIKey.user_id == user_id)
        
        if not include_inactive:
            query = query.filter(APIKey.is_active == True)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        api_keys = query.order_by(APIKey.created_at.desc()).offset(offset).limit(page_size).all()
        
        # Convert to response models
        key_responses = []
        for api_key in api_keys:
            key_data = api_key.to_safe_dict()
            key_responses.append(APIKeyResponse.model_validate(key_data))
        
        return APIKeyListResponse(
            api_keys=key_responses,
            total=total,
            page=page,
            page_size=page_size
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in admin list all API keys: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API keys"
        )


@router.post("/admin/{key_id}/reset-limits", response_model=SuccessResponse)
async def admin_reset_api_key_limits(
    key_id: str,
    request: Request,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to reset rate limits for an API key.
    
    Requires superuser privileges.
    """
    try:
        # Find the API key
        api_key = db.query(APIKey).filter(APIKey.id == key_id).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Reset database counters
        api_key.requests_today = 0
        api_key.requests_this_hour = 0
        api_key.requests_this_minute = 0
        db.commit()
        
        # Reset Redis rate limits
        await api_key_rate_limiter.reset_api_key_limits(key_id)
        
        logger.info(
            "Admin reset API key limits",
            admin_user_id=current_user.id,
            key_id=key_id,
            key_prefix=api_key.key_prefix,
            client_ip=request.client.host if request.client else None
        )
        
        return SuccessResponse(
            message=f"Rate limits reset for API key {api_key.key_prefix}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error resetting API key limits {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset API key limits"
        )