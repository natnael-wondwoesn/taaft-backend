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

# Load environment variables
load_dotenv()
GHL_CLIENT_ID = os.getenv("GHL_CLIENT_ID")
GHL_CLIENT_SECRET = os.getenv("GHL_CLIENT_SECRET")
GHL_REDIRECT_URI = os.getenv("GHL_REDIRECT_URI")
GHL_ACCESS_TOKEN = os.getenv("GHL_ACCESS_TOKEN")
GHL_REFRESH_TOKEN = os.getenv("GHL_REFRESH_TOKEN")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID")
print(GHL_CLIENT_ID)


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


async def refresh_ghl_token():
    """Refresh GHL access token using refresh token."""
    url = "https://services.leadconnectorhq.com/oauth/token"
    print(GHL_REFRESH_TOKEN)
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": GHL_REFRESH_TOKEN,
        "client_id": GHL_CLIENT_ID,
        "client_secret": GHL_CLIENT_SECRET,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=payload)
        if response.status_code != 200:
            logger.error(f"GHL refresh token error: {response.text}")
            raise HTTPException(status_code=400, detail="Token refresh failed")
        tokens = response.json()
        os.environ["GHL_ACCESS_TOKEN"] = tokens["access_token"]
        os.environ["GHL_REFRESH_TOKEN"] = tokens["refresh_token"]
        logger.info("GHL access token refreshed successfully")
        return tokens


async def get_ghl_access_token(
    code: str, client_id: str, client_secret: str, redirect_uri: str
):
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
        return response.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def create_ghl_contact(data: GHLContactData):
    """Create a contact in GHL with retry logic."""
    url = "https://services.leadconnectorhq.com/contacts"
    headers = {"Authorization": f"Bearer {GHL_ACCESS_TOKEN}", "Version": "2021-07-28"}
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
                await refresh_ghl_token()
                raise HTTPException(
                    status_code=503, detail="Retrying after token refresh"
                )
            raise HTTPException(
                status_code=500, detail="Failed to create contact in GHL"
            )
        except httpx.RequestError as e:
            logger.error(f"GHL connection error: {str(e)}")
            raise HTTPException(status_code=503, detail="GHL connection failed")


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
        self.api_key = GHL_ACCESS_TOKEN
        self.location_id = "oauth_mode"  # Not used in OAuth mode
        self.is_configured = bool(GHL_ACCESS_TOKEN and GHL_REFRESH_TOKEN)


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


# Backwards compatibility for sync_newsletter_subscriber_to_ghl
async def sync_newsletter_subscriber_to_ghl(
    email: str, name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Backward compatibility function for sync_newsletter_subscriber_to_ghl
    Maps to the new sync_to_company_ghl function with NEWSLETTER type
    """
    try:
        user_dict = {"email": email, "full_name": name if name else ""}

        result = await sync_to_company_ghl(user_dict, SignupType.NEWSLETTER)
        return {"success": True, "details": result}
    except Exception as e:
        logger.error(
            f"Error in backwards compatible sync_newsletter_subscriber_to_ghl: {str(e)}"
        )
        return {"success": False, "error": str(e)}


# Backwards compatibility for process_failed_syncs
async def process_failed_syncs() -> Dict[str, Any]:
    """
    Backward compatibility function for process_failed_syncs
    Maps to the new retry_failed_signups function
    """
    try:
        return await retry_failed_signups()
    except Exception as e:
        logger.error(f"Error in backwards compatible process_failed_syncs: {str(e)}")
        return {"success": False, "error": str(e)}
