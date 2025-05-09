import json
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.ghl.ghl_service import (
    GHLContactData,
    SignupType,
    create_ghl_contact,
    sync_user_to_ghl,
)
from ..logger import logger
import os
from dotenv import load_dotenv
import httpx
from bson import ObjectId
import datetime
from typing import Optional, Dict, Any, Tuple
from ..database.database import database
from ..models.user import UserInDB, ServiceTier
from fastapi import HTTPException, status

load_dotenv()

# OAuth configuration
config = Config()
oauth = OAuth()

# Google OAuth
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile", "prompt": "select_account"},
)

# GitHub OAuth
github = oauth.register(
    name="github",
    client_id=os.getenv("GITHUB_CLIENT_ID", ""),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET", ""),
    authorize_url="https://github.com/login/oauth/authorize",
    authorize_params=None,
    access_token_url="https://github.com/login/oauth/access_token",
    access_token_params=None,
    refresh_token_url=None,
    client_kwargs={"scope": "read:user"},
)


async def get_user_by_email(email: str) -> Optional[UserInDB]:
    """Get a user by email from the database."""
    user_data = await database.users.find_one({"email": email})
    if user_data:
        return UserInDB(**user_data)
    return None


async def create_sso_user(
    email: str,
    provider: str,
    provider_user_id: str,
    name: Optional[str] = None,
    subscribeToNewsletter: bool = False,
    provider_data: Optional[Dict[str, Any]] = None,
) -> UserInDB:
    """Create a new user from SSO provider data."""
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email not provided by {provider}",
        )

    # Check if user already exists
    existing_user = await get_user_by_email(email)
    if existing_user:
        # Update provider info with all provider data
        update_data = {
            f"oauth_providers.{provider}": {
                "id": provider_user_id,
                "connected_at": datetime.datetime.utcnow(),
                "profile_data": provider_data,
            },
            "last_login": datetime.datetime.utcnow(),
        }

        # Update name if it wasn't set before
        if name and not existing_user.full_name:
            update_data["full_name"] = name

        await database.users.update_one(
            {"email": email},
            {"$set": update_data},
        )
        # Get updated user
        user_data = await database.users.find_one({"email": email})
        return UserInDB(**user_data)

    # Create new user
    new_user = UserInDB(
        email=email,
        # For SSO users, we set a dummy hashed_password since they will use SSO
        hashed_password="SSO_USER",
        full_name=name,
        service_tier=ServiceTier.FREE,  # Default to free tier
        is_active=True,
        is_verified=True,  # SSO users are pre-verified
        subscribeToNewsletter=subscribeToNewsletter,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        oauth_providers={
            provider: {
                "id": provider_user_id,
                "connected_at": datetime.datetime.utcnow(),
                "profile_data": provider_data,
            }
        },
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
    user_data = await database.users.find_one({"_id": result.inserted_id})
    logger.info(f"New SSO user created: {email} via {provider}")

    return UserInDB(**user_data)


async def get_google_user(
    access_token: str,
) -> Tuple[str, str, Optional[str], Dict[str, Any]]:
    """Get user information from Google."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_data = resp.json()

        if not resp.is_success or "email" not in user_data:
            logger.error(f"Failed to get Google user data: {user_data}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user information from Google",
            )
        logger.info(f"Google user data: {user_data}")

        # Return all user data for storage
        return user_data["email"], user_data["id"], user_data.get("name"), user_data


async def get_github_user(
    access_token: str,
) -> Tuple[str, str, Optional[str], Dict[str, Any]]:
    """Get user information from GitHub."""
    async with httpx.AsyncClient() as client:
        # Get user profile
        headers = {"Authorization": f"token {access_token}"}
        resp = await client.get("https://api.github.com/user", headers=headers)
        user_data = resp.json()

        # Get email (GitHub may not provide email in profile)
        email_resp = await client.get(
            "https://api.github.com/user/emails", headers=headers
        )
        email_data = email_resp.json()

        # Find primary email
        primary_email = None
        if isinstance(email_data, list):
            for email_entry in email_data:
                if email_entry.get("primary") and email_entry.get("verified"):
                    primary_email = email_entry.get("email")
                    break

        if not primary_email:
            # Use any verified email or profile email as fallback
            if isinstance(email_data, list):
                for email_entry in email_data:
                    if email_entry.get("verified"):
                        primary_email = email_entry.get("email")
                        break

            if not primary_email and "email" in user_data and user_data["email"]:
                primary_email = user_data["email"]

        if not primary_email:
            logger.error(f"Failed to get GitHub email: {email_data}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub account doesn't have a verified email",
            )

        logger.info(f"Github Data {user_data}")

        # Add email data to user_data for completeness
        user_data["email_data"] = email_data

        return primary_email, str(user_data["id"]), user_data.get("name"), user_data


async def sync_to_company_ghl(user: Dict[str, Any], signup_type: SignupType):
    """Sync user data to company GHL account."""
    tags = []
    if signup_type in [SignupType.ACCOUNT, SignupType.BOTH]:
        tags.append("full_account")
    if signup_type in [SignupType.NEWSLETTER, SignupType.BOTH]:
        tags.append("newsletter")

    ghl_data = GHLContactData(
        email=user["email"], first_name=user.get("full_name"), tags=tags
    )
    try:
        ghl_contact = await create_ghl_contact(ghl_data)
        logger.info(f"Created GHL contact for {user['email']}: {ghl_contact}")
        return {"success": True, "data": ghl_contact}
    except Exception as e:
        logger.error(f"GHL contact creation failed for {user['email']}: {str(e)}")
        # Save to file for retry
        with open("failed_ghl_signups.txt", "a") as f:
            f.write(f"{json.dumps(ghl_data.dict())}\n")
        raise
