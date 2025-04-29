from fastapi import APIRouter, HTTPException, status, Depends, Body, Request
from fastapi.security import OAuth2PasswordRequestForm
from ..models.user import UserCreate, UserInDB, UserResponse, ServiceTier
from ..database.database import database
from .utils import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from .dependencies import get_current_user
from typing import Dict, Any
import datetime
from bson import ObjectId
from pydantic import EmailStr
from ..logger import logger

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(user_data: UserCreate):
    """Register a new user and assign to free tier."""

    # Check if user with this email already exists
    existing_user = await database.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    # Hash the password
    hashed_password = get_password_hash(user_data.password)

    # Create user object with free tier
    new_user = UserInDB(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        subscribeToNewsletter=user_data.subscribeToNewsletter,
        service_tier=ServiceTier.FREE,  # Default to free tier
        is_active=True,
        is_verified=False,  # User needs to verify email
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        usage={
            "requests_today": 0,
            "requests_reset_date": datetime.datetime.utcnow(),
            "total_requests": 0,
            "storage_used_bytes": 0,
        },
    )

    # Insert user into database
    result = await database.users.insert_one(
        new_user.dict(by_alias=True, exclude={"id"})
    )

    # Get created user
    created_user = await database.users.find_one({"_id": result.inserted_id})

    logger.info(f"New user registered: {user_data.email}")

    # Convert to response model
    return UserResponse(
        id=str(created_user["_id"]),
        email=created_user["email"],
        full_name=created_user.get("full_name"),
        service_tier=created_user["service_tier"],
        is_active=created_user["is_active"],
        is_verified=created_user["is_verified"],
        subscribeToNewsletter=created_user.get("subscribeToNewsletter", False),
        created_at=created_user["created_at"],
        usage=created_user["usage"],
    )


@router.post("/token", response_model=Dict[str, str])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user and return access and refresh tokens."""

    # Get user from database
    user = await database.users.find_one({"email": form_data.username})

    # Validate user and password
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    # Update last login time
    await database.users.update_one(
        {"_id": user["_id"]}, {"$set": {"last_login": datetime.datetime.utcnow()}}
    )

    # Create token data
    token_data = {
        "sub": str(user["_id"]),
        "service_tier": user["service_tier"],
        "is_verified": user["is_verified"],
    }

    # Create access and refresh tokens
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)

    logger.info(f"User logged in: {form_data.username}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh-token", response_model=Dict[str, str])
async def refresh_access_token(refresh_token: str = Body(...)):
    """Get a new access token using refresh token."""

    # Decode and validate refresh token
    token_data = decode_token(refresh_token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if token is expired
    if datetime.datetime.utcnow() > token_data.exp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = await database.users.find_one({"_id": ObjectId(token_data.sub)})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create new token data
    new_token_data = {
        "sub": str(user["_id"]),
        "service_tier": user["service_tier"],
        "is_verified": user["is_verified"],
    }

    # Create new access token
    access_token = create_access_token(data=new_token_data)

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserInDB = Depends(get_current_user)):
    """Get information about the currently authenticated user."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        service_tier=current_user.service_tier,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        usage=current_user.usage,
    )


@router.post("/verify-email", response_model=Dict[str, str])
async def verify_email(token: str = Body(...)):
    """Verify user email with verification token."""

    # Decode and validate token
    token_data = decode_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token"
        )

    # Update user verification status
    result = await database.users.update_one(
        {"_id": ObjectId(token_data.sub)},
        {"$set": {"is_verified": True, "updated_at": datetime.datetime.utcnow()}},
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found or already verified",
        )

    return {"message": "Email verified successfully"}


@router.post("/request-password-reset", response_model=Dict[str, str])
async def request_password_reset(email: EmailStr = Body(..., embed=True)):
    """Request a password reset token."""

    # Find user
    user = await database.users.find_one({"email": email})
    if not user:
        # Always return success even if user doesn't exist (security)
        return {"message": "If the email exists, a password reset link will be sent"}

    # In a real system, you would send an email with reset link
    # For now, we'll just log it
    reset_token = create_access_token(
        data={"sub": str(user["_id"]), "purpose": "password_reset"}
    )

    logger.info(f"Password reset requested for {email}. Token: {reset_token}")

    return {"message": "If the email exists, a password reset link will be sent"}


@router.post("/reset-password", response_model=Dict[str, str])
async def reset_password(token: str = Body(...), new_password: str = Body(...)):
    """Reset user password with a valid token."""

    # Decode and validate token
    token_data = decode_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Hash the new password
    hashed_password = get_password_hash(new_password)

    # Update user password
    result = await database.users.update_one(
        {"_id": ObjectId(token_data.sub)},
        {
            "$set": {
                "hashed_password": hashed_password,
                "updated_at": datetime.datetime.utcnow(),
            }
        },
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User not found"
        )

    return {"message": "Password reset successful"}


@router.post("/update-newsletter-preference", response_model=Dict[str, str])
async def update_newsletter_preference(
    subscribeToNewsletter: bool = Body(...),
    current_user: UserInDB = Depends(get_current_user),
):
    """Update the user's newsletter subscription preference."""

    # Update user in database
    result = await database.users.update_one(
        {"_id": current_user.id},
        {
            "$set": {
                "subscribeToNewsletter": subscribeToNewsletter,
                "updated_at": datetime.datetime.utcnow(),
            }
        },
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update newsletter preference",
        )

    logger.info(
        f"User {current_user.email} updated newsletter preference to: {subscribeToNewsletter}"
    )

    return {"message": "Newsletter preference updated successfully"}
