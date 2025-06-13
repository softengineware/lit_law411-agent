"""Authentication API endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...core.auth_middleware import get_current_active_user, get_current_user
from ...core.config import get_settings
from ...core.logging import get_logger
from ...core.security import (
    create_access_token,
    create_refresh_token,
    generate_email_verification_token,
    generate_password_reset_token,
    hash_password,
    is_token_expired,
    verify_password,
    verify_token,
    TokenError,
    PasswordError,
)
from ...db.database import get_db
from ...models.pydantic.auth import (
    AuthStatus,
    EmailVerification,
    ErrorResponse,
    LoginResponse,
    LogoutResponse,
    PasswordChange,
    PasswordReset,
    PasswordResetConfirm,
    RegistrationResponse,
    SuccessResponse,
    TokenRefresh,
    TokenResponse,
    UserLogin,
    UserProfile,
    UserRegistration,
    UserUpdate,
)
from ...models.sqlalchemy.user import User

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


@router.post("/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegistration,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    
    Creates a new user account with email verification required.
    Returns user profile and registration status.
    """
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Check username uniqueness if provided
        if user_data.username:
            existing_username = db.query(User).filter(User.username == user_data.username).first()
            if existing_username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
        
        # Hash password
        password_hash = hash_password(user_data.password)
        
        # Generate email verification token
        verification_token = generate_email_verification_token()
        verification_expires = datetime.now(timezone.utc) + timedelta(hours=24)
        
        # Create new user
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            password_hash=password_hash,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            organization=user_data.organization,
            job_title=user_data.job_title,
            is_active=True,
            is_verified=False,  # Require email verification
            email_verification_token=verification_token,
            email_verification_expires_at=verification_expires,
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(
            "New user registered",
            user_id=new_user.id,
            email=new_user.email,
            client_ip=request.client.host if request.client else None
        )
        
        # TODO: Send verification email
        # await send_verification_email(new_user.email, verification_token)
        
        user_profile = UserProfile.from_orm(new_user)
        
        return RegistrationResponse(
            message="User registered successfully. Please check your email for verification.",
            user=user_profile,
            verification_required=True
        )
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed due to data conflict"
        )
    except PasswordError as e:
        logger.error(f"Password hashing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to security error"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to server error"
        )


@router.post("/login", response_model=LoginResponse)
async def login_user(
    user_credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens.
    
    Validates user credentials and returns access and refresh tokens.
    Updates last login information.
    """
    try:
        # Get user by email
        user = db.query(User).filter(User.email == user_credentials.email).first()
        if not user:
            logger.warning(f"Login attempt with non-existent email: {user_credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Check if account is locked
        if user.is_account_locked:
            logger.warning(f"Login attempt on locked account: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is locked due to too many failed login attempts"
            )
        
        # Verify password
        if not verify_password(user_credentials.password, user.password_hash):
            # Increment failed login attempts
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
                logger.warning(f"Account locked due to failed attempts: {user.email}")
            
            db.commit()
            
            logger.warning(f"Failed login attempt: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Login attempt on inactive account: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive"
            )
        
        # Reset failed login attempts on successful login
        user.failed_login_attempts = 0
        user.locked_until = None
        
        # Update last login information
        user.last_login_at = datetime.now(timezone.utc)
        user.last_login_ip = request.client.host if request.client else None
        
        db.commit()
        
        # Create JWT tokens
        token_data = {"sub": user.email, "user_id": user.id}
        
        # Adjust token expiration for "remember me"
        access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        refresh_token_expires = timedelta(days=settings.jwt_refresh_token_expire_days)
        
        if user_credentials.remember_me:
            access_token_expires = timedelta(hours=24)  # Longer access token
            refresh_token_expires = timedelta(days=30)  # Longer refresh token
        
        access_token = create_access_token(token_data, access_token_expires)
        refresh_token = create_refresh_token(token_data, refresh_token_expires)
        
        logger.info(
            "User logged in successfully",
            user_id=user.id,
            email=user.email,
            client_ip=request.client.host if request.client else None
        )
        
        user_profile = UserProfile.from_orm(user)
        tokens = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=int(access_token_expires.total_seconds())
        )
        
        return LoginResponse(
            message="Login successful",
            user=user_profile,
            tokens=tokens
        )
        
    except HTTPException:
        raise
    except PasswordError as e:
        logger.error(f"Password verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )
    except TokenError as e:
        logger.error(f"Token creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db)
):
    """
    Refresh JWT access token using refresh token.
    
    Validates refresh token and returns new access token.
    """
    try:
        # Verify refresh token
        payload = verify_token(token_data.refresh_token, token_type="refresh")
        
        # Get user email from token
        user_email = payload.get("sub")
        if not user_email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Get user from database
        user = db.query(User).filter(User.email == user_email).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new access token
        token_payload = {"sub": user.email, "user_id": user.id}
        access_token = create_access_token(token_payload)
        
        logger.info(f"Token refreshed for user: {user.email}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=token_data.refresh_token,  # Keep same refresh token
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60
        )
        
    except TokenError as e:
        logger.warning(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh service error"
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout_user(
    current_user: User = Depends(get_current_active_user)
):
    """
    Logout current user.
    
    In a stateless JWT system, logout is handled client-side by discarding tokens.
    This endpoint provides confirmation and can be used for logging purposes.
    """
    logger.info(f"User logged out: {current_user.email}")
    
    # TODO: Add token blacklisting for enhanced security
    # For now, we rely on client-side token removal
    
    return LogoutResponse(message="Successfully logged out")


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user profile information.
    
    Returns detailed profile information for the authenticated user.
    """
    return UserProfile.from_orm(current_user)


@router.put("/me", response_model=UserProfile)
async def update_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update current user profile.
    
    Updates user profile information for the authenticated user.
    """
    try:
        # Check username uniqueness if being updated
        if user_update.username and user_update.username != current_user.username:
            existing_username = db.query(User).filter(
                User.username == user_update.username,
                User.id != current_user.id
            ).first()
            if existing_username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
        
        # Update user fields
        update_data = user_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(current_user, field, value)
        
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"User profile updated: {current_user.email}")
        
        return UserProfile.from_orm(current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed"
        )


@router.post("/change-password", response_model=SuccessResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Change user password.
    
    Validates current password and updates to new password.
    """
    try:
        # Verify current password
        if not verify_password(password_data.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Hash new password
        new_password_hash = hash_password(password_data.new_password)
        
        # Update password
        current_user.password_hash = new_password_hash
        db.commit()
        
        logger.info(f"Password changed for user: {current_user.email}")
        
        return SuccessResponse(message="Password changed successfully")
        
    except HTTPException:
        raise
    except PasswordError as e:
        logger.error(f"Password hashing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error changing password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.post("/verify-email", response_model=SuccessResponse)
async def verify_email(
    verification_data: EmailVerification,
    db: Session = Depends(get_db)
):
    """
    Verify user email address.
    
    Validates email verification token and marks email as verified.
    """
    try:
        # Find user by verification token
        user = db.query(User).filter(
            User.email_verification_token == verification_data.token
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification token"
            )
        
        # Check if token has expired
        if user.email_verification_expires_at and is_token_expired(user.email_verification_expires_at):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has expired"
            )
        
        # Mark email as verified
        user.is_verified = True
        user.email_verification_token = None
        user.email_verification_expires_at = None
        
        db.commit()
        
        logger.info(f"Email verified for user: {user.email}")
        
        return SuccessResponse(message="Email verified successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Email verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email verification failed"
        )


@router.post("/forgot-password", response_model=SuccessResponse)
async def forgot_password(
    reset_data: PasswordReset,
    db: Session = Depends(get_db)
):
    """
    Request password reset.
    
    Generates password reset token and sends reset email.
    """
    try:
        # Find user by email
        user = db.query(User).filter(User.email == reset_data.email).first()
        
        # Always return success to prevent email enumeration
        if not user:
            logger.warning(f"Password reset requested for non-existent email: {reset_data.email}")
            return SuccessResponse(message="If the email exists, a password reset link has been sent")
        
        # Generate reset token
        reset_token = generate_password_reset_token()
        reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Update user with reset token
        user.password_reset_token = reset_token
        user.password_reset_expires_at = reset_expires
        
        db.commit()
        
        logger.info(f"Password reset requested for user: {user.email}")
        
        # TODO: Send password reset email
        # await send_password_reset_email(user.email, reset_token)
        
        return SuccessResponse(message="If the email exists, a password reset link has been sent")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Password reset request error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset request failed"
        )


@router.post("/reset-password", response_model=SuccessResponse)
async def reset_password(
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Reset password with token.
    
    Validates reset token and updates user password.
    """
    try:
        # Find user by reset token
        user = db.query(User).filter(
            User.password_reset_token == reset_data.token
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )
        
        # Check if token has expired
        if user.password_reset_expires_at and is_token_expired(user.password_reset_expires_at):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired"
            )
        
        # Hash new password
        new_password_hash = hash_password(reset_data.new_password)
        
        # Update password and clear reset token
        user.password_hash = new_password_hash
        user.password_reset_token = None
        user.password_reset_expires_at = None
        user.failed_login_attempts = 0  # Reset failed attempts
        user.locked_until = None  # Unlock account
        
        db.commit()
        
        logger.info(f"Password reset completed for user: {user.email}")
        
        return SuccessResponse(message="Password reset successfully")
        
    except HTTPException:
        raise
    except PasswordError as e:
        logger.error(f"Password hashing error during reset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )


@router.get("/status", response_model=AuthStatus)
async def get_auth_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authentication status.
    
    Returns authentication status and user information if authenticated.
    """
    if not current_user:
        return AuthStatus(
            authenticated=False,
            user=None,
            permissions=[],
            subscription_active=False,
            api_quota_remaining=0
        )
    
    # Calculate remaining API quota based on subscription tier
    api_quota_remaining = 0
    if current_user.subscription_tier == "free":
        api_quota_remaining = max(0, 100 - current_user.api_calls_today)
    elif current_user.subscription_tier == "basic":
        api_quota_remaining = max(0, 1000 - current_user.api_calls_today)
    elif current_user.subscription_tier in ["premium", "enterprise"]:
        api_quota_remaining = 10000  # High limit for premium users
    
    user_profile = UserProfile.from_orm(current_user)
    
    return AuthStatus(
        authenticated=True,
        user=user_profile,
        permissions=current_user.permissions or [],
        subscription_active=current_user.is_premium,
        api_quota_remaining=api_quota_remaining
    )