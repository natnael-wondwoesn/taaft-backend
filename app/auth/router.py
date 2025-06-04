import asyncio
from fastapi import APIRouter, HTTPException, status, Depends, Body, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.oauth import sync_to_company_ghl
from app.ghl.ghl_service import SignupType
from ..models.user import UserCreate, UserInDB, UserResponse, ServiceTier, UserUpdate
from ..database.database import database
from .utils import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from .dependencies import get_current_user, oauth2_scheme
from typing import Dict, Any, Optional, List
import datetime
from bson import ObjectId
from pydantic import EmailStr, BaseModel
from ..logger import logger
import os
import random

router = APIRouter(prefix="/auth", tags=["auth"])


# Pydantic model for changing password
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


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

    # Check if username exists (if provided)
    if user_data.username:
        existing_username = await database.users.find_one(
            {"username": user_data.username}
        )
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

    hashed_password = get_password_hash(user_data.password)
    new_user = UserInDB(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        username=user_data.username,
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
        data={"sub": str(result.inserted_id), "purpose": "email_verification"},
        expires_delta=datetime.timedelta(hours=24)
    )
    
    # Get the backend URL for verification
    base_url = os.getenv("BACKEND_URL", "https://taaft.zapto.org")
    if not base_url.startswith("http"):
        base_url = "https://" + base_url
    
    # Remove trailing slash if present
    if base_url.endswith("/"):
        base_url = base_url.rstrip("/")
    
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
        username=created_user.get("username"),
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

    # Check if user is verified
    if not user["is_verified"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required. Please verify your email before logging in.",
        )

    # Update last login time
    await database.users.update_one(
        {"_id": user["_id"]}, {"$set": {"last_login": datetime.datetime.utcnow()}}
    )

    # Get saved tools from separate collection
    saved_tools_doc = await database.user_saved_tools.find_one({"user_id": user["_id"]})
    saved_tools = saved_tools_doc["tools"] if saved_tools_doc else []

    # Create token data
    token_data = {
        "sub": str(user["_id"]),
        "service_tier": user["service_tier"],
        "is_verified": user["is_verified"],
        "saved_tools": saved_tools,
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

    # Get saved tools from separate collection
    saved_tools_doc = await database.user_saved_tools.find_one(
        {"user_id": ObjectId(token_data.sub)}
    )
    saved_tools = saved_tools_doc["tools"] if saved_tools_doc else []

    # Create new token data
    new_token_data = {
        "sub": str(user["_id"]),
        "service_tier": user["service_tier"],
        "is_verified": user["is_verified"],
        "saved_tools": saved_tools,
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
        username=current_user.username,
        bio=current_user.bio,
        profile_image=current_user.profile_image,
        service_tier=current_user.service_tier,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        usage=current_user.usage,
    )


@router.api_route("/verify-email", methods=["GET", "POST"], response_model=Dict[str, str])
async def verify_email(token: Optional[str] = None, request: Request = None):
    """Verify user email with verification token."""
    
    # Get token from query params (GET) or request body (POST)
    if not token and request:
        token = request.query_params.get("token")
    
    if not token:
        logger.error("[/verify-email] No token provided in request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token is required"
        )

    # Decode and validate token
    token_data = decode_token(token)
    if token_data is None or not hasattr(token_data, 'sub') or not hasattr(token_data, 'purpose'):
        logger.error(f"[/verify-email] Invalid or malformed token received. Token (first 20 chars): {token[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token"
        )
    
    if token_data.purpose != "email_verification":
        logger.error(f"[/verify-email] Invalid token purpose: '{token_data.purpose}' for user {token_data.sub}. Token (first 20 chars): {token[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type for email verification"
        )

    # Get user from database
    user = await database.users.find_one({"_id": ObjectId(token_data.sub)})
    if not user:
        logger.error(f"[/verify-email] User not found for verification. User ID from token: {token_data.sub}. Token (first 20 chars): {token[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found or verification failed",
        )

    # Check if user is already verified
    if user.get("is_verified", False):
        logger.info(f"[/verify-email] Email already verified for user {token_data.sub}. Token (first 20 chars): {token[:20]}...")
        # Return success with login redirect
        return {
            "message": "Email already verified. You can now log in.", 
            "redirect": os.getenv("FRONTEND_URL", "https://taaft-development.vercel.app") + "/login"
        }

    # Check if token is already used
    if user.get("verification_token_used", False):
        logger.info(f"[/verify-email] Verification token already used for user {token_data.sub}. Token (first 20 chars): {token[:20]}...")
        return {
            "message": "This verification link has already been used. Please login or request a new verification link if needed.",
            "redirect": os.getenv("FRONTEND_URL", "https://taaft-development.vercel.app") + "/login"
        }

    # Update user verification status and mark token as used
    result = await database.users.update_one(
        {"_id": ObjectId(token_data.sub)},
        {
            "$set": {
                "is_verified": True, 
                "verification_token_used": True,
                "updated_at": datetime.datetime.utcnow()
            }
        },
    )

    if result.modified_count == 0:
        logger.warning(f"[/verify-email] User {token_data.sub} found but not modified. Token (first 20 chars): {token[:20]}...")
        # This might indicate an issue - we should have been able to update
        return {
            "message": "Email verification failed. Please try again or request a new verification link.",
            "redirect": os.getenv("FRONTEND_URL", "https://taaft-development.vercel.app")
        }
    
    logger.info(f"[/verify-email] Email successfully verified for user {token_data.sub}. Token (first 20 chars): {token[:20]}...")
    # Return success with login redirect
    return {
        "message": "Email verified successfully. You can now log in.",
        "redirect": os.getenv("FRONTEND_URL", "https://taaft-development.vercel.app")
    }


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
        else os.getenv("BASE_URL", "https://taaft.zapto.org/")
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
async def reset_password(
    token: Optional[str] = Body(None),
    new_password: str = Body(...),
    request: Request = None,
):
    """Reset user password with a valid token.

    The token can be provided either in the request body or as a query parameter.
    """
    # Get token from request body or query parameters
    if not token and request:
        token = request.query_params.get("token")

    if not token:
        logger.error("Password reset failed: No token provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is required",
        )

    # Log token length for debugging (don't log the actual token for security)
    logger.info(f"Processing password reset with token length: {len(token)}")

    # Decode and validate token
    token_data = decode_token(token)
    if token_data is None:
        logger.error("Password reset failed: Invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Verify token purpose is for password reset
    if not token_data.purpose or token_data.purpose != "password_reset":
        logger.error(
            f"Password reset failed: Invalid token purpose '{token_data.purpose}'"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token purpose",
        )

    # Hash the new password
    hashed_password = get_password_hash(new_password)

    # Log user ID from token (for debugging)
    user_id = token_data.sub
    logger.info(f"Resetting password for user ID: {user_id}")

    # Update user password
    try:
        result = await database.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "hashed_password": hashed_password,
                    "updated_at": datetime.datetime.utcnow(),
                }
            },
        )

        if result.modified_count == 0:
            logger.error(f"Password reset failed: User not found with ID {user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="User not found"
            )

        logger.info(f"Password reset successful for user ID: {user_id}")
        return {"message": "Password reset successful"}

    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting the password",
        )


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

    # Get saved tools from separate collection
    saved_tools_doc = await database.user_saved_tools.find_one({"user_id": user["_id"]})
    saved_tools = saved_tools_doc["tools"] if saved_tools_doc else []

    # Create token data
    token_data = {
        "sub": str(user["_id"]),
        "service_tier": user["service_tier"],
        "is_verified": user["is_verified"],
        "saved_tools": saved_tools,
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

    # If user doesn't exist, return a generic message for security
    if not user:
        logger.info(f"[/resend-verification] Request for email '{email}' - User not found.")
        return {
            "message": "If the email exists and is not verified, a verification link will be sent",
            "status": "success"
        }

    # If user is already verified, inform the client
    if user.get("is_verified", False):
        logger.info(f"[/resend-verification] Email '{email}' is already verified (User ID: {user['_id']}).")
        return {
            "message": "This email is already verified. You can log in with your credentials.",
            "status": "already_verified"
        }

    # User exists and is not verified, proceed to resend
    logger.info(f"[/resend-verification] Attempting to resend verification for '{email}' (User ID: {user['_id']}).")
    
    # Reset the verification token usage flag if it exists
    await database.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"verification_token_used": False}}
    )
    
    # Create a new verification token
    verification_token = create_access_token(
        data={"sub": str(user["_id"]), "purpose": "email_verification"},
        expires_delta=datetime.timedelta(hours=24)
    )

    # Get base URL for the backend
    base_url = os.getenv("BACKEND_URL", "https://taaft.zapto.org")
    if not base_url.startswith("http"):
        base_url = "https://" + base_url
    
    # Remove trailing slash if present
    if base_url.endswith("/"):
        base_url = base_url.rstrip("/")

    # Import email service
    from ..services.email_service import send_verification_email

    # Send verification email
    email_sent = send_verification_email(email, verification_token, base_url)

    if not email_sent:
        logger.error(
            f"[/resend-verification] Failed to send verification email to {email} for user {user['_id']}. Token (first 20 chars for ref): {verification_token[:20]}..."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please try again later.",
        )
    else:
        logger.info(f"[/resend-verification] Verification email successfully resent to {email} for user {user['_id']}.")

    return {
        "message": "Verification email sent successfully. Please check your inbox.",
        "status": "success"
    }


# @router.get("/saved-tools", response_model=List[str])
# async def get_saved_tools(token: str = Depends(oauth2_scheme)):
#     """Get the user's saved tools directly from the token."""
#     token_data = decode_token(token)
#     if token_data is None:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Could not validate credentials",
#             headers={"WWW-Authenticate": "Bearer"},
#         )

#     return token_data.saved_tools


# @router.post("/update-saved-tools", response_model=Dict[str, str])
# async def update_saved_tools(
#     tools: List[str] = Body(...), current_user: UserInDB = Depends(get_current_user)
# ):
#     """Update the user's saved tools and return new tokens with updated data."""

#     # Update saved tools in a separate collection
#     await database.user_saved_tools.update_one(
#         {"user_id": current_user.id},
#         {
#             "$set": {
#                 "tools": tools,
#                 "updated_at": datetime.datetime.utcnow(),
#             }
#         },
#         upsert=True,
#     )

#     # Create new token data with updated saved tools
#     token_data = {
#         "sub": str(current_user.id),
#         "service_tier": current_user.service_tier,
#         "is_verified": current_user.is_verified,
#         "saved_tools": tools,
#     }

#     # Create new access and refresh tokens
#     access_token = create_access_token(data=token_data)
#     refresh_token = create_refresh_token(data=token_data)

#     logger.info(f"User {current_user.email} updated saved tools")

#     return {
#         "access_token": access_token,
#         "refresh_token": refresh_token,
#         "token_type": "bearer",
#     }


@router.post("/change-password", response_model=Dict[str, str])
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """Change the current user's password."""
    logger.info(f"[change_password] User {current_user.email} ({current_user.id}) is attempting to change their password.")
    if password_data.old_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the old password",
        )

    # Verify old password
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password",
        )

    # Hash the new password
    hashed_new_password = get_password_hash(password_data.new_password)

    # Update user password in database
    result = await database.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {
            "$set": {
                "hashed_password": hashed_new_password,
                "updated_at": datetime.datetime.utcnow(),
            }
        },
    )

    if result.modified_count == 0:
        logger.error(
            f"[change_password] Failed to update password for user {current_user.email} ({current_user.id})."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password. Please try again later.",
        )

    logger.info(
        f"[change_password] User {current_user.email} ({current_user.id}) changed their password successfully."
    )

    return {"message": "Password changed successfully"}


@router.post("/update-profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Update the user's profile information."""

    logger.info(f"[update_profile] User: {current_user.email} ({current_user.id}) is attempting to update profile with payload: {profile_data.dict()}")

    # Initialize update data
    update_data = {"updated_at": datetime.datetime.utcnow()}

    # Check if username is being updated and if it already exists
    if profile_data.username and profile_data.username != current_user.username:
        existing_username = await database.users.find_one(
            {"username": profile_data.username}
        )
        if existing_username:
            logger.warning(f"[update_profile] Username '{profile_data.username}' already taken for user {current_user.email} ({current_user.id})")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )
        update_data["username"] = profile_data.username

    # Add fields to update if they are provided
    if profile_data.full_name is not None:
        update_data["full_name"] = profile_data.full_name
    if profile_data.bio is not None:
        update_data["bio"] = profile_data.bio
    if profile_data.profile_image is not None:
        update_data["profile_image"] = profile_data.profile_image

    logger.info(f"[update_profile] Computed update_data for user {current_user.email} ({current_user.id}): {update_data}")

    # Update user in database
    result = await database.users.update_one(
        {"_id": ObjectId(current_user.id)}, {"$set": update_data}
    )

    logger.info(f"[update_profile] DB update result for user {current_user.email} ({current_user.id}): matched_count={result.matched_count}, modified_count={result.modified_count}")

    if (
        result.modified_count == 0 and len(update_data) > 1
    ):  # Only updated_at would mean length 1
        logger.warning(f"[update_profile] Failed to update profile for user {current_user.email} ({current_user.id}). update_data: {update_data}, matched_count={result.matched_count}, modified_count={result.modified_count}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update profile",
        )

    # Get updated user data
    updated_user = await database.users.find_one({"_id": ObjectId(current_user.id)})

    if updated_user is None:
        logger.error(f"[update_profile] CRITICAL: User {current_user.email} ({current_user.id}) with ObjectId {ObjectId(current_user.id)} NOT FOUND after update attempt. Update DB result was: matched={result.matched_count}, modified={result.modified_count}. Update data sent: {update_data}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve user information after update.",
        )

    logger.info(f"[update_profile] User {current_user.email} ({current_user.id}) updated profile information successfully. Found user post-update.")

    return UserResponse(
        id=str(updated_user["_id"]),
        email=updated_user["email"],
        full_name=updated_user.get("full_name"),
        username=updated_user.get("username"),
        bio=updated_user.get("bio"),
        profile_image=updated_user.get("profile_image"),
        service_tier=updated_user["service_tier"],
        is_active=updated_user["is_active"],
        is_verified=updated_user["is_verified"],
        subscribeToNewsletter=updated_user.get("subscribeToNewsletter", False),
        created_at=updated_user["created_at"],
        usage=updated_user["usage"],
    )
