from enum import Enum
from pydantic import BaseModel
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from fastapi import HTTPException
from typing import Dict, Any, Optional, Union
from ..logger import logger
from dotenv import load_dotenv
import os
import json
from app.models.user import UserInDB  # Add import for backward compatibility
import asyncio
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
GHL_CLIENT_ID = os.getenv("GHL_CLIENT_ID")
GHL_CLIENT_SECRET = os.getenv("GHL_CLIENT_SECRET")
GHL_REDIRECT_URI = os.getenv("GHL_REDIRECT_URI")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID")

# Initial token values
_GHL_ACCESS_TOKEN = os.getenv("GHL_ACCESS_TOKEN")
_GHL_REFRESH_TOKEN = os.getenv("GHL_REFRESH_TOKEN")
_TOKEN_EXPIRES_AT = None
_TOKEN_LOCK = asyncio.Lock()

print(f"GHL Client ID: {GHL_CLIENT_ID}")


class SignupType(str, Enum):
    """Enum for signup types."""

    ACCOUNT = "full_account"
    NEWSLETTER = "newsletter"
    BOTH = "both"


class GHLContactData(BaseModel):
    """Model for GHL contact data."""

    email: str
    first_name: str | None = None
    last_name: str | None = None
    tags: list[str]


class GHLTokenManager:
    """Manages GHL access tokens with automatic refresh."""
    
    def __init__(self):
        self.access_token = _GHL_ACCESS_TOKEN
        self.refresh_token = _GHL_REFRESH_TOKEN
        self.expires_at = _TOKEN_EXPIRES_AT
        self.lock = _TOKEN_LOCK
        self._refresh_token_invalid = False  # Track if refresh token is invalid
    
    def is_configured(self) -> bool:
        """Check if GHL is properly configured with required tokens."""
        return bool(
            GHL_CLIENT_ID and 
            GHL_CLIENT_SECRET and 
            self.refresh_token and 
            GHL_LOCATION_ID and
            not self._refresh_token_invalid  # Don't consider configured if refresh token is invalid
        )
    
    def mark_refresh_token_invalid(self):
        """Mark the refresh token as invalid to stop further refresh attempts."""
        self._refresh_token_invalid = True
        logger.warning("GHL refresh token marked as invalid - re-authentication required")
    
    def reset_refresh_token_status(self):
        """Reset the refresh token status (call this after successful re-authentication)."""
        self._refresh_token_invalid = False
        logger.info("GHL refresh token status reset - ready for use")
    
    async def get_valid_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        async with self.lock:
            # Check if GHL is properly configured first
            if not self.is_configured():
                if self._refresh_token_invalid:
                    logger.warning("GHL refresh token is invalid - re-authentication required via OAuth")
                    raise HTTPException(
                        status_code=401, 
                        detail="GHL refresh token invalid - re-authentication required"
                    )
                else:
                    logger.warning("GHL not properly configured - missing client credentials or refresh token")
                    raise HTTPException(
                        status_code=503, 
                        detail="GHL integration not configured"
                    )
            
            # Don't try to refresh if we know the refresh token is invalid
            if self._refresh_token_invalid:
                logger.warning("Skipping token refresh attempt - refresh token is invalid")
                if self.access_token:
                    logger.info("Using existing access token despite invalid refresh token")
                    return self.access_token
                else:
                    raise HTTPException(
                        status_code=401, 
                        detail="GHL refresh token invalid and no access token available"
                    )
            
            # Always refresh the token before each API call as requested
            try:
                await self._refresh_token()
                logger.info("GHL token refreshed proactively before API call")
            except HTTPException as e:
                if "invalid" in str(e.detail).lower() or "invalid_grant" in str(e.detail).lower():
                    # Mark refresh token as invalid to stop further attempts
                    self.mark_refresh_token_invalid()
                
                logger.warning(f"Failed to refresh token proactively: {str(e)}")
                # If refresh fails, try to use existing token
                if not self.access_token:
                    raise HTTPException(
                        status_code=401, 
                        detail="No valid GHL access token available and refresh failed"
                    )
            except Exception as e:
                logger.warning(f"Failed to refresh token proactively: {str(e)}")
                if not self.access_token:
                    raise HTTPException(
                        status_code=401, 
                        detail="No valid GHL access token available and refresh failed"
                    )
            
            return self.access_token
    
    async def _refresh_token(self):
        """Internal method to refresh the access token."""
        if not self.refresh_token:
            raise HTTPException(
                status_code=401,
                detail="No GHL refresh token available"
            )
        
        if self._refresh_token_invalid:
            raise HTTPException(
                status_code=401,
                detail="GHL refresh token is invalid - re-authentication required"
            )
        
        url = "https://services.leadconnectorhq.com/oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": GHL_CLIENT_ID,
            "client_secret": GHL_CLIENT_SECRET,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=payload)
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"GHL refresh token error: {error_text}")
                
                # Check if this is an invalid grant error
                if "invalid_grant" in error_text.lower():
                    self.mark_refresh_token_invalid()
                    raise HTTPException(
                        status_code=401, 
                        detail="GHL refresh token expired/invalid - re-authentication required"
                    )
                else:
                    raise HTTPException(status_code=401, detail="Token refresh failed")
            
            tokens = response.json()
            self.access_token = tokens["access_token"]
            self.refresh_token = tokens.get("refresh_token", self.refresh_token)
            
            # Calculate expiration time (default to 1 hour if not provided)
            expires_in = tokens.get("expires_in", 3600)
            self.expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 300)  # 5 min buffer
            
            # Update environment variables for persistence
            os.environ["GHL_ACCESS_TOKEN"] = self.access_token
            if tokens.get("refresh_token"):
                os.environ["GHL_REFRESH_TOKEN"] = self.refresh_token
            
            # Reset invalid status on successful refresh
            if self._refresh_token_invalid:
                self.reset_refresh_token_status()
            
            logger.info("GHL access token refreshed successfully")
            return tokens
    
    async def force_refresh(self):
        """Force a token refresh (public method)."""
        async with self.lock:
            return await self._refresh_token()
    
    def get_status(self) -> dict:
        """Get detailed status information about the token manager."""
        return {
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token),
            "refresh_token_invalid": self._refresh_token_invalid,
            "is_configured": self.is_configured(),
            "needs_reauth": self._refresh_token_invalid,
        }


# Global token manager instance
token_manager = GHLTokenManager()


async def refresh_ghl_token():
    """Legacy function for backward compatibility."""
    return await token_manager.force_refresh()


async def get_ghl_access_token(
    code: str, client_id: str, client_secret: str, redirect_uri: str
):
    """Get initial access token from authorization code."""
    token_url = "https://services.leadconnectorhq.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=payload)
        if response.status_code != 200:
            raise HTTPException(
                status_code=400, detail="Failed to obtain GHL access token"
            )
        
        # Update token manager with new tokens
        tokens = response.json()
        token_manager.access_token = tokens["access_token"]
        token_manager.refresh_token = tokens.get("refresh_token")
        
        # Update environment variables
        os.environ["GHL_ACCESS_TOKEN"] = tokens["access_token"]
        if tokens.get("refresh_token"):
            os.environ["GHL_REFRESH_TOKEN"] = tokens["refresh_token"]
        
        return tokens


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def create_ghl_contact(data: GHLContactData):
    """Create a contact in GHL with automatic token refresh and retry logic."""
    # Check if GHL is configured before attempting API call
    if not token_manager.is_configured():
        logger.warning(f"GHL not configured, skipping contact creation for {data.email}")
        raise HTTPException(
            status_code=503, 
            detail="GHL integration not configured"
        )
    
    # Get a fresh token before making the API call
    access_token = await token_manager.get_valid_token()
    
    url = "https://services.leadconnectorhq.com/contacts"
    headers = {"Authorization": f"Bearer {access_token}", "Version": "2021-07-28"}
    
    first_name, last_name = None, None
    if data.first_name:
        names = data.first_name.split(" ", 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else None
    
    payload = {
        "email": data.email,
        "firstName": first_name,
        "lastName": last_name or data.last_name,
        "tags": data.tags,
        "locationId": GHL_LOCATION_ID,
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Check for existing contact to avoid duplicates
            lookup_url = (
                f"https://rest.gohighlevel.com/v1/contacts/lookup?email={data.email}"
            )
            lookup_response = await client.get(lookup_url, headers=headers)
            if lookup_response.status_code == 200 and lookup_response.json().get(
                "contacts"
            ):
                logger.info(f"Contact already exists for {data.email}")
                return lookup_response.json()

            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"GHL API error: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 401:
                # If we still get 401 after token refresh, it's a more serious issue
                logger.error("Still getting 401 after token refresh - may need to re-authenticate")
                raise HTTPException(
                    status_code=401, 
                    detail="GHL authentication failed - may need to re-authenticate"
                )
            raise HTTPException(
                status_code=500, detail="Failed to create contact in GHL"
            )
        except httpx.RequestError as e:
            logger.error(f"GHL connection error: {str(e)}")
            raise HTTPException(status_code=503, detail="GHL connection failed")


async def sync_to_company_ghl(user: Dict[str, Any], signup_type: SignupType):
    """Sync user data to company GHL account with graceful error handling."""
    # Check if GHL is configured before attempting sync
    if not token_manager.is_configured():
        logger.info(f"GHL not configured, skipping sync for {user.get('email', 'unknown')}")
        return {"success": False, "message": "GHL not configured", "skipped": True}
    
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
    except HTTPException as e:
        if e.status_code == 503:  # Service unavailable (not configured)
            logger.info(f"GHL service unavailable, skipping sync for {user['email']}")
            return {"success": False, "message": "GHL not configured", "skipped": True}
        else:
            logger.error(f"GHL contact creation failed for {user['email']}: {str(e)}")
            # Save to file for retry
            with open("failed_ghl_signups.txt", "a") as f:
                f.write(f"{json.dumps(ghl_data.dict())}\n")
            raise
    except Exception as e:
        logger.error(f"GHL contact creation failed for {user['email']}: {str(e)}")
        # Save to file for retry
        with open("failed_ghl_signups.txt", "a") as f:
            f.write(f"{json.dumps(ghl_data.dict())}\n")
        raise


async def retry_failed_signups():
    """Retry failed GHL signup attempts."""
    try:
        with open("failed_ghl_signups.txt", "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        logger.info("No failed GHL signups to retry")
        return {"success": True, "message": "No failed signups to retry"}

    successful = 0
    failed = 0
    with open("failed_ghl_signups.txt", "w") as f:
        for line in lines:
            try:
                ghl_data = GHLContactData(**json.loads(line))
                await create_ghl_contact(ghl_data)
                logger.info(f"Retried GHL contact for {ghl_data.email}")
                successful += 1
            except Exception as e:
                logger.error(f"Retry failed for {ghl_data.email}: {str(e)}")
                f.write(line)
                failed += 1

    return {
        "success": True,
        "statistics": {
            "successful_retries": successful,
            "failed_retries": failed,
            "total_processed": successful + failed,
        },
    }


# =========================================
# BACKWARD COMPATIBILITY FUNCTIONS
# These functions provide backward compatibility with the old GHL integration
# =========================================


# Mock GHLService class to maintain compatibility
class GHLService:
    def __init__(self):
        self.api_key = None  # Will be dynamically retrieved
        self.location_id = "oauth_mode"  # Not used in OAuth mode
        self.is_configured = bool(GHL_CLIENT_ID and GHL_CLIENT_SECRET and _GHL_REFRESH_TOKEN)
    
    async def get_api_key(self):
        """Get current API key (access token)."""
        return await token_manager.get_valid_token()


# Create a singleton instance of the service
ghl_service = GHLService()


# Backwards compatibility for sync_user_to_ghl
async def sync_user_to_ghl(
    user: UserInDB, sync_type: SignupType = SignupType.ACCOUNT
) -> Dict[str, Any]:
    """
    Backward compatibility function for sync_user_to_ghl
    Maps to the new sync_to_company_ghl function
    """
    try:
        # Convert UserInDB to the dict format expected by sync_to_company_ghl
        user_dict = {
            "id": str(user.id),
            "email": user.email,
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
        }

        result = await sync_to_company_ghl(user_dict, sync_type)
        return {"success": True, "details": result}
    except Exception as e:
        logger.error(f"Error in backwards compatible sync_user_to_ghl: {str(e)}")
        return {"success": False, "error": str(e)}


# Backwards compatibility for newsletter sync
async def sync_newsletter_subscriber_to_ghl(
    email: str, name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Backward compatibility function for newsletter subscriber sync
    """
    try:
        user_dict = {"email": email, "full_name": name if name else ""}
        result = await sync_to_company_ghl(user_dict, SignupType.NEWSLETTER)
        return {"success": True, "details": result}
    except Exception as e:
        logger.error(f"Error in sync_newsletter_subscriber_to_ghl: {str(e)}")
        return {"success": False, "error": str(e)}


# Backwards compatibility for failed sync processing
async def process_failed_syncs() -> Dict[str, Any]:
    """
    Backward compatibility function for processing failed syncs
    """
    try:
        result = await retry_failed_signups()
        return {"success": True, "details": result}
    except Exception as e:
        logger.error(f"Error in process_failed_syncs: {str(e)}")
        return {"success": False, "error": str(e)}
