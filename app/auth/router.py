import asyncio
from fastapi import APIRouter, HTTPException, status, Depends, Body, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.oauth import sync_to_company_ghl
from app.ghl.ghl_service import SignupType
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
import os
import random

router = APIRouter(prefix="/auth", tags=["auth"])


# app/auth/router.py (update existing /register endpoint)
@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(user_data: UserCreate, request: Request = None):
    existing_user = await database.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    hashed_password = get_password_hash(user_data.password)
    new_user = UserInDB(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        subscribeToNewsletter=user_data.subscribeToNewsletter,
        service_tier=ServiceTier.FREE,
        is_active=True,
        is_verified=False,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        usage={
            "requests_today": 0,
            "requests_reset_date": datetime.datetime.utcnow(),
            "total_requests": 0,
            "storage_used_bytes": 0,
        },
    )

    result = await database.users.insert_one(
        new_user.dict(by_alias=True, exclude={"id"})
    )
    created_user = await database.users.find_one({"_id": result.inserted_id})
    logger.info(f"New user registered: {user_data.email}")

    verification_token = create_access_token(
        data={"sub": str(result.inserted_id), "purpose": "email_verification"}
    )
    base_url = (
        str(request.base_url)
        if request
        else os.getenv("BASE_URL", "https://taaft-backend.onrender.com")
    )
    logger.info(f"Base URL for verification email: {base_url}")
    logger.info(f"Attempting to send verification email to {user_data.email}")

    try:
        from ..services.email_service import send_verification_email

        email_sent = send_verification_email(
            user_data.email, verification_token, base_url
        )
        if not email_sent:
            logger.info(
                f"Verification email not sent to {user_data.email}. Token: {verification_token}"
            )
            logger.warning(f"Failed to send verification email to {user_data.email}")
        else:
            logger.info(f"Verification email successfully sent to {user_data.email}")
    except Exception as e:
        logger.error(
            f"Exception while sending verification email to {user_data.email}: {str(e)}"
        )
        logger.info(f"Verification token for manual verification: {verification_token}")

    try:
        signup_type = (
            SignupType.BOTH if user_data.subscribeToNewsletter else SignupType.ACCOUNT
        )
        asyncio.create_task(sync_to_company_ghl(created_user, signup_type))
    except Exception as e:
        logger.error(f"Failed to sync user to company GoHighLevel account: {str(e)}")

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
async def request_password_reset(
    email: EmailStr = Body(..., embed=True), request: Request = None
):
    """Request a password reset token."""

    # Find user
    user = await database.users.find_one({"email": email})
    if not user:
        # Always return success even if user doesn't exist (security)
        return {"message": "If the email exists, a password reset link will be sent"}

    # Create a reset token
    reset_token = create_access_token(
        data={"sub": str(user["_id"]), "purpose": "password_reset"}
    )

    # Get base URL from request or settings
    base_url = (
        str(request.base_url)
        if request
        else os.getenv("BASE_URL", "http://localhost:8000")
    )

    # Import here to avoid circular imports
    from ..services.email_service import send_password_reset_email

    # Send password reset email
    email_sent = send_password_reset_email(email, reset_token, base_url)

    if not email_sent:
        # Email sending failed, log the token for debugging
        logger.info(f"Password reset requested for {email}. Token: {reset_token}")
        logger.warning(f"Failed to send password reset email to {email}")

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


@router.post("/request-login-code", response_model=Dict[str, str])
async def request_login_code(email: EmailStr = Body(..., embed=True)):
    """
    Request a one-time login code for passwordless login.

    This endpoint generates a numeric code and sends it to the user's email.
    The code is valid for 10 minutes.
    """
    # Find user
    user = await database.users.find_one({"email": email})
    if not user:
        # For security, don't reveal if email exists or not
        return {"message": "If the email exists, a login code will be sent"}

    # Generate a 6-digit login code
    login_code = "".join(random.choice("0123456789") for _ in range(6))

    # Hash the login code for storage
    hashed_code = get_password_hash(login_code)

    # Calculate expiration time (10 minutes from now)
    expiration_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)

    # Store the login code in the database
    await database.login_codes.update_one(
        {"user_id": ObjectId(user["_id"])},
        {
            "$set": {
                "hashed_code": hashed_code,
                "expires_at": expiration_time,
                "created_at": datetime.datetime.utcnow(),
            }
        },
        upsert=True,
    )

    # Import email service
    from ..services.email_service import send_login_code_email

    # Send the login code via email
    email_sent = send_login_code_email(email, login_code)

    if not email_sent:
        logger.warning(f"Failed to send login code email to {email}")

    return {"message": "If the email exists, a login code will be sent"}


@router.post("/verify-login-code", response_model=Dict[str, str])
async def verify_login_code(email: EmailStr = Body(...), code: str = Body(...)):
    """
    Verify a one-time login code and return access tokens.

    This endpoint validates the provided login code and returns JWT tokens if valid.
    """
    # Find user
    user = await database.users.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or login code",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Retrieve stored login code
    login_code_doc = await database.login_codes.find_one(
        {"user_id": ObjectId(user["_id"])}
    )
    if not login_code_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or login code",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if code is expired
    if datetime.datetime.utcnow() > login_code_doc["expires_at"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login code has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify the code
    if not verify_password(code, login_code_doc["hashed_code"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or login code",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Delete the used code
    await database.login_codes.delete_one({"user_id": ObjectId(user["_id"])})

    # Create token data
    token_data = {
        "sub": str(user["_id"]),
        "service_tier": user["service_tier"],
        "is_verified": user["is_verified"],
    }

    # Create access and refresh tokens
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)

    logger.info(f"User logged in via one-time code: {email}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/resend-verification", response_model=Dict[str, str])
async def resend_verification_email(
    email: EmailStr = Body(..., embed=True), request: Request = None
):
    """
    Resend verification email to a user who hasn't verified their email yet.
    """
    # Find user
    user = await database.users.find_one({"email": email})

    # If user doesn't exist or is already verified, return generic message
    if not user or user.get("is_verified", False):
        return {
            "message": "If the email exists and is not verified, a verification link will be sent"
        }

    # Create a verification token
    verification_token = create_access_token(
        data={"sub": str(user["_id"]), "purpose": "email_verification"}
    )

    # Get base URL from request or settings
    base_url = (
        str(request.base_url)
        if request
        else os.getenv("BASE_URL", "http://localhost:8000")
    )

    # Import email service
    from ..services.email_service import send_verification_email

    # Send verification email
    email_sent = send_verification_email(email, verification_token, base_url)

    if not email_sent:
        logger.warning(f"Failed to send verification email to {email}")

    return {
        "message": "If the email exists and is not verified, a verification link will be sent"
    }
