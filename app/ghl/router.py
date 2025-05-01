"""
API router for GoHighLevel CRM integration
Handles endpoints for managing GHL synchronization and status
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Body,
    status,
    BackgroundTasks,
    Request,
)
from typing import Dict, Any, Optional
import os

from app.auth.dependencies import get_admin_user
from app.models.user import UserInDB, UserResponse
from .ghl_service import (
    SignupType,
    sync_to_company_ghl,
    refresh_ghl_token,
    retry_failed_signups,
    get_ghl_access_token,
)
from app.logger import logger

router = APIRouter(
    prefix="/api/integrations/ghl",
    tags=["integrations"],
)


@router.get("/status")
async def get_ghl_integration_status():
    """
    Get the current status of the GoHighLevel integration
    """
    ghl_client_id = os.getenv("GHL_CLIENT_ID")
    ghl_client_secret = os.getenv("GHL_CLIENT_SECRET")
    ghl_access_token = os.getenv("GHL_ACCESS_TOKEN")
    ghl_refresh_token = os.getenv("GHL_REFRESH_TOKEN")

    is_configured = bool(ghl_client_id and ghl_client_secret)
    has_tokens = bool(ghl_access_token and ghl_refresh_token)

    return {
        "is_configured": is_configured,
        "client_id_configured": bool(ghl_client_id),
        "client_secret_configured": bool(ghl_client_secret),
        "has_access_token": bool(ghl_access_token),
        "has_refresh_token": bool(ghl_refresh_token),
        "auth_status": "authenticated" if has_tokens else "not_authenticated",
    }


@router.post("/sync-user", status_code=status.HTTP_200_OK)
async def sync_user(
    user_id: str = Body(...),
    sync_type: SignupType = Body(SignupType.ACCOUNT),
    background_tasks: BackgroundTasks = None,
    current_user: UserResponse = Depends(get_admin_user),
):
    """
    Manually sync a user to GoHighLevel (admin only)
    """
    from app.database.database import database
    from bson import ObjectId

    # Verify GHL is configured
    ghl_access_token = os.getenv("GHL_ACCESS_TOKEN")
    ghl_refresh_token = os.getenv("GHL_REFRESH_TOKEN")

    if not ghl_access_token or not ghl_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GoHighLevel integration not configured or not authenticated",
        )

    # Find the user
    user_data = await database.users.find_one({"_id": ObjectId(user_id)})
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user = UserInDB(**user_data)

    # Convert to dict for sync function
    user_dict = {
        "id": str(user.id),
        "email": user.email,
        "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
    }

    # If background tasks is provided, run in background
    if background_tasks:
        background_tasks.add_task(sync_to_company_ghl, user_dict, sync_type)
        return {"status": "sync_scheduled", "user_id": user_id}

    # Otherwise run synchronously
    try:
        await sync_to_company_ghl(user_dict, sync_type)
        return {
            "status": "completed",
            "success": True,
            "details": {"message": "User synced to GHL successfully"},
        }
    except Exception as e:
        logger.error(f"Error syncing user to GHL: {str(e)}")
        return {"status": "error", "success": False, "details": {"error": str(e)}}


@router.post("/sync-newsletter", status_code=status.HTTP_200_OK)
async def sync_newsletter_subscriber(
    email: str = Body(...),
    name: Optional[str] = Body(None),
    background_tasks: BackgroundTasks = None,
    current_user: UserResponse = Depends(get_admin_user),
):
    """
    Manually sync a newsletter subscriber to GoHighLevel (admin only)
    """
    # Verify GHL is configured
    ghl_access_token = os.getenv("GHL_ACCESS_TOKEN")
    ghl_refresh_token = os.getenv("GHL_REFRESH_TOKEN")

    if not ghl_access_token or not ghl_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GoHighLevel integration not configured or not authenticated",
        )

    # Create user dict
    user_dict = {"email": email, "full_name": name if name else ""}

    # If background tasks is provided, run in background
    if background_tasks:
        background_tasks.add_task(sync_to_company_ghl, user_dict, SignupType.NEWSLETTER)
        return {"status": "sync_scheduled", "email": email}

    # Otherwise run synchronously
    try:
        await sync_to_company_ghl(user_dict, SignupType.NEWSLETTER)
        return {
            "status": "completed",
            "success": True,
            "details": {"message": "Newsletter subscriber synced to GHL successfully"},
        }
    except Exception as e:
        logger.error(f"Error syncing newsletter subscriber to GHL: {str(e)}")
        return {"status": "error", "success": False, "details": {"error": str(e)}}


@router.post("/process-failed-syncs", status_code=status.HTTP_200_OK)
async def handle_failed_syncs(
    background_tasks: BackgroundTasks = None,
    current_user: UserResponse = Depends(get_admin_user),
):
    """
    Process failed GoHighLevel synchronizations (admin only)
    """
    # Verify GHL is configured
    ghl_access_token = os.getenv("GHL_ACCESS_TOKEN")
    ghl_refresh_token = os.getenv("GHL_REFRESH_TOKEN")

    if not ghl_access_token or not ghl_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GoHighLevel integration not configured or not authenticated",
        )

    # If background tasks is provided, run in background
    if background_tasks:
        background_tasks.add_task(retry_failed_signups)
        return {"status": "processing_scheduled"}

    # Otherwise run synchronously
    try:
        await retry_failed_signups()
        return {"status": "completed", "message": "Failed syncs processed"}
    except Exception as e:
        logger.error(f"Error processing failed syncs: {str(e)}")
        return {"status": "error", "error": str(e)}


@router.post("/refresh-token", status_code=status.HTTP_200_OK)
async def refresh_token(
    current_user: UserResponse = Depends(get_admin_user),
):
    """
    Refresh the GHL access token (admin only)
    """
    try:
        result = await refresh_ghl_token()
        return {
            "status": "success",
            "message": "GHL token refreshed successfully",
            "expires_in": result.get("expires_in"),
        }
    except Exception as e:
        logger.error(f"Error refreshing GHL token: {str(e)}")
        return {"status": "error", "error": str(e)}


@router.get("/auth-url")
async def get_auth_url(
    current_user: UserResponse = Depends(get_admin_user),
):
    """
    Get the URL for GHL OAuth authentication (admin only)
    """
    client_id = os.getenv("GHL_CLIENT_ID")
    redirect_uri = os.getenv("GHL_REDIRECT_URI")

    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GHL_CLIENT_ID or GHL_REDIRECT_URI not configured",
        )

    auth_url = f"https://marketplace.gohighlevel.com/oauth/chooselocation?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope=contacts.readonly contacts.write"

    return {"auth_url": auth_url}


@router.get("/oauth-callback")
async def oauth_callback(
    request: Request,
    code: str,
):
    """
    Handle GoHighLevel OAuth callback
    """
    client_id = os.getenv("GHL_CLIENT_ID")
    client_secret = os.getenv("GHL_CLIENT_SECRET")
    redirect_uri = os.getenv("GHL_REDIRECT_URI")

    if not all([client_id, client_secret, redirect_uri]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GHL OAuth credentials not fully configured",
        )

    try:
        tokens = await get_ghl_access_token(
            code, client_id, client_secret, redirect_uri
        )

        # Store tokens in environment variables
        os.environ["GHL_ACCESS_TOKEN"] = tokens["access_token"]
        os.environ["GHL_REFRESH_TOKEN"] = tokens["refresh_token"]

        # Optionally store in database for persistence
        # from app.database.database import database
        # await database.ghl_tokens.update_one(
        #     {"_id": "ghl_tokens"},
        #     {"$set": tokens},
        #     upsert=True
        # )

        return {
            "message": "GHL authentication successful",
            "expires_in": tokens.get("expires_in"),
        }
    except Exception as e:
        logger.error(f"GHL OAuth callback error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during GHL authentication: {str(e)}",
        )
