from fastapi import APIRouter, HTTPException, status, Depends, Body
from typing import Dict, Any, List
from bson import ObjectId
import datetime

from ..models.user import UserInDB, UserResponse, ServiceTier
from ..database.database import database
from .dependencies import get_current_active_user, TIER_LIMITS
from ..logger import logger

router = APIRouter(prefix="/tiers", tags=["service_tiers"])


@router.get("/limits", response_model=Dict[str, Any])
async def get_tier_limits(current_user: UserInDB = Depends(get_current_active_user)):
    """Get the limits for the current user's tier."""
    return TIER_LIMITS[current_user.service_tier]


@router.get("/all", response_model=Dict[str, Any])
async def get_all_tiers():
    """Get information about all available service tiers."""
    return {tier.value: TIER_LIMITS[tier] for tier in ServiceTier}


@router.post("/upgrade", response_model=UserResponse)
async def upgrade_tier(
    service_tier: ServiceTier = Body(..., embed=True),
    current_user: UserInDB = Depends(get_current_active_user),
):
    """Upgrade user to a different service tier."""

    # Check that the target tier is valid
    tier_hierarchy = list(ServiceTier)
    current_tier_index = tier_hierarchy.index(current_user.service_tier)
    target_tier_index = tier_hierarchy.index(service_tier)

    # Ensure it's an upgrade
    if target_tier_index <= current_tier_index:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot downgrade tier using upgrade endpoint. Use /tiers/downgrade instead.",
        )

    # In a real system, this is where you would handle payment processing
    # For now, we'll just update the tier directly

    # Update the user tier
    result = await database.users.update_one(
        {"_id": current_user.id},
        {
            "$set": {
                "service_tier": service_tier,
                "updated_at": datetime.datetime.utcnow(),
            }
        },
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update service tier",
        )

    # Get updated user
    updated_user = await database.users.find_one({"_id": current_user.id})

    logger.info(
        f"User {current_user.email} upgraded from {current_user.service_tier} to {service_tier}"
    )

    # Return updated user
    return UserResponse(
        id=str(updated_user["_id"]),
        email=updated_user["email"],
        full_name=updated_user.get("full_name"),
        service_tier=updated_user["service_tier"],
        is_active=updated_user["is_active"],
        is_verified=updated_user["is_verified"],
        created_at=updated_user["created_at"],
        usage=updated_user["usage"],
    )


@router.post("/downgrade", response_model=UserResponse)
async def downgrade_tier(
    service_tier: ServiceTier = Body(..., embed=True),
    current_user: UserInDB = Depends(get_current_active_user),
):
    """Downgrade user to a lower service tier."""

    # Check that the target tier is valid
    tier_hierarchy = list(ServiceTier)
    current_tier_index = tier_hierarchy.index(current_user.service_tier)
    target_tier_index = tier_hierarchy.index(service_tier)

    # Ensure it's a downgrade
    if target_tier_index >= current_tier_index:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upgrade tier using downgrade endpoint. Use /tiers/upgrade instead.",
        )

    # Update the user tier
    result = await database.users.update_one(
        {"_id": current_user.id},
        {
            "$set": {
                "service_tier": service_tier,
                "updated_at": datetime.datetime.utcnow(),
            }
        },
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update service tier",
        )

    # Get updated user
    updated_user = await database.users.find_one({"_id": current_user.id})

    logger.info(
        f"User {current_user.email} downgraded from {current_user.service_tier} to {service_tier}"
    )

    # Return updated user
    return UserResponse(
        id=str(updated_user["_id"]),
        email=updated_user["email"],
        full_name=updated_user.get("full_name"),
        service_tier=updated_user["service_tier"],
        is_active=updated_user["is_active"],
        is_verified=updated_user["is_verified"],
        created_at=updated_user["created_at"],
        usage=updated_user["usage"],
    )
