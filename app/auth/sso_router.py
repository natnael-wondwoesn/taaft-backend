from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from .oauth import (
    oauth,
    google,
    github,
    create_sso_user,
    get_google_user,
    get_github_user,
)
from .utils import create_access_token, create_refresh_token
from ..logger import logger
from ..models.user import UserResponse, OAuthProvider, ServiceTier
from typing import Dict, Optional
import os
from dotenv import load_dotenv

load_dotenv()

# Frontend URLs for redirection after OAuth
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://taaft-deploy-18xw.vercel.app/")
FRONTEND_SUCCESS_URL = os.getenv("FRONTEND_SUCCESS_URL", f"{FRONTEND_URL}/auth/success")
FRONTEND_ERROR_URL = os.getenv("FRONTEND_ERROR_URL", f"{FRONTEND_URL}/auth/error")

router = APIRouter(prefix="/sso", tags=["sso"])


@router.get("/login/{provider}")
async def login(request: Request, provider: str):
    """Redirect to the OAuth provider login page."""
    # Validate provider
    try:
        provider_enum = OAuthProvider(provider)
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": f"Unsupported provider: {provider}"},
        )

    # Get redirect URL
    redirect_uri = request.url_for(f"auth_callback", provider=provider)

    # State for security
    if provider == OAuthProvider.GOOGLE:
        return await google.authorize_redirect(request, redirect_uri)
    elif provider == OAuthProvider.GITHUB:
        return await github.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}", name="auth_callback")
async def auth_callback(request: Request, provider: str):
    """Handle the OAuth callback and create/login the user."""
    try:
        # Validate provider
        try:
            provider_enum = OAuthProvider(provider)
        except ValueError:
            logger.error(f"Invalid provider in callback: {provider}")
            return RedirectResponse(
                f"{FRONTEND_ERROR_URL}?error=invalid_provider&message=Unsupported+provider"
            )

        # Get the token
        if provider == OAuthProvider.GOOGLE:
            token = await google.authorize_access_token(request)
            email, provider_user_id, name, provider_data = await get_google_user(
                token["access_token"]
            )
        elif provider == OAuthProvider.GITHUB:
            token = await github.authorize_access_token(request)
            email, provider_user_id, name, provider_data = await get_github_user(
                token["access_token"]
            )
        else:
            logger.error(f"Unsupported provider in callback: {provider}")
            return RedirectResponse(
                f"{FRONTEND_ERROR_URL}?error=invalid_provider&message=Unsupported+provider"
            )

        # Create or update user
        user = await create_sso_user(
            email,
            provider,
            provider_user_id,
            name,
            subscribeToNewsletter=False,
            provider_data=provider_data,
        )

        # Create access token
        token_data = {
            "sub": str(user.id),
            "service_tier": user.service_tier,
            "is_verified": user.is_verified,
        }
        access_token = create_access_token(data=token_data)
        refresh_token = create_refresh_token(data=token_data)

        # Redirect to frontend with tokens
        return RedirectResponse(
            f"{FRONTEND_SUCCESS_URL}?access_token={access_token}&refresh_token={refresh_token}"
        )

    except Exception as e:
        logger.error(f"Error in OAuth callback: {str(e)}")
        return RedirectResponse(
            f"{FRONTEND_ERROR_URL}?error=server_error&message=Authentication+failed"
        )


@router.get("/providers", response_model=Dict[str, Dict[str, str]])
async def get_providers():
    """Get available OAuth providers."""
    providers = {}

    if os.getenv("GOOGLE_CLIENT_ID"):
        providers["google"] = {
            "name": "Google",
            "url": "/api/auth/sso/login/google",
        }

    if os.getenv("GITHUB_CLIENT_ID"):
        providers["github"] = {
            "name": "GitHub",
            "url": "/api/auth/sso/login/github",
        }

    return {"providers": providers}
