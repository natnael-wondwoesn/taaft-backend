from fastapi import APIRouter, HTTPException, status, Depends, Query, Path
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from ..models.user import UserInDB, UserResponse, UserUpdate, ServiceTier
from ..database.database import database
from .dependencies import get_current_user, check_tier_access
from ..logger import logger

router = APIRouter(prefix="/admin/users", tags=["admin"])


# Only allow enterprise users to access admin endpoints
get_admin_user = check_tier_access(ServiceTier.ENTERPRISE)


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    service_tier: Optional[ServiceTier] = None,
    is_active: Optional[bool] = None,
    is_verified: Optional[bool] = None,
    current_user: UserInDB = Depends(get_admin_user),
):
    """List all users with pagination and filtering."""

    # Build filter
    filter_query = {}
    if service_tier:
        filter_query["service_tier"] = service_tier
    if is_active is not None:
        filter_query["is_active"] = is_active
    if is_verified is not None:
        filter_query["is_verified"] = is_verified

    # Get users
    cursor = (
        database.users.find(filter_query).skip(skip).limit(limit).sort("created_at", -1)
    )
    users = await cursor.to_list(length=limit)

    # Convert to response model
    user_responses = []
    for user in users:
        user_responses.append(
            UserResponse(
                id=str(user["_id"]),
                email=user["email"],
                full_name=user.get("full_name"),
                service_tier=user["service_tier"],
                is_active=user["is_active"],
                is_verified=user["is_verified"],
                created_at=user["created_at"],
                usage=user["usage"],
            )
        )

    return user_responses


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str = Path(...), current_user: UserInDB = Depends(get_admin_user)
):
    """Get a specific user by ID."""

    # Check if valid ObjectId
    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )

    # Get user
    user = await database.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Convert to response model
    return UserResponse(
        id=str(user["_id"]),
        email=user["email"],
        full_name=user.get("full_name"),
        service_tier=user["service_tier"],
        is_active=user["is_active"],
        is_verified=user["is_verified"],
        created_at=user["created_at"],
        usage=user["usage"],
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: UserInDB = Depends(get_admin_user),
):
    """Update a user."""

    # Check if valid ObjectId
    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )

    # Check if user exists
    user = await database.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Build update document
    update_data = user_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )

    # Add updated_at field
    update_data["updated_at"] = datetime.utcnow()

    # Update user
    result = await database.users.update_one(
        {"_id": ObjectId(user_id)}, {"$set": update_data}
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        )

    # Get updated user
    updated_user = await database.users.find_one({"_id": ObjectId(user_id)})

    logger.info(f"User {user_id} updated by admin {current_user.email}")

    # Convert to response model
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


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, current_user: UserInDB = Depends(get_admin_user)):
    """Delete a user."""

    # Check if valid ObjectId
    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )

    # Cannot delete yourself
    if str(current_user.id) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself"
        )

    # Delete user
    result = await database.users.delete_one({"_id": ObjectId(user_id)})

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    logger.info(f"User {user_id} deleted by admin {current_user.email}")

    # No content response
    return None


@router.get("/stats/tiers", response_model=dict)
async def get_tier_statistics(current_user: UserInDB = Depends(get_admin_user)):
    """Get statistics about user tiers."""

    # Get count of users by tier
    pipeline = [
        {"$group": {"_id": "$service_tier", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]

    result = await database.users.aggregate(pipeline).to_list(length=10)

    # Convert to dict
    tier_stats = {tier.value: 0 for tier in ServiceTier}
    for item in result:
        tier_stats[item["_id"]] = item["count"]

    return {"tier_counts": tier_stats, "total_users": sum(tier_stats.values())}
