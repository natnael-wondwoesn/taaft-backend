from fastapi import APIRouter, HTTPException, status, Depends, Query, Path, Body
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from ..models.user import UserInDB, UserResponse, UserUpdate, ServiceTier
from ..database.database import database
from .dependencies import (
    get_current_user,
    check_tier_access,
    RATE_LIMIT_EXEMPT_USERS,
    is_exempt_from_rate_limits,
)
from ..logger import logger
from .utils import get_password_hash

router = APIRouter(prefix="/admin", tags=["admin"])


# Only allow enterprise users to access admin endpoints
get_admin_user = check_tier_access(ServiceTier.ENTERPRISE)


@router.get("/users", response_model=List[UserResponse])
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


@router.get("/users/{user_id}", response_model=UserResponse)
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


@router.patch("/users/{user_id}", response_model=UserResponse)
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


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
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


@router.post("/promote-admin", response_model=UserResponse)
async def promote_to_admin(
    email: str = Body(..., embed=True),
    current_user: UserInDB = Depends(get_admin_user),
):
    """Promote a user to admin (ENTERPRISE tier) by email."""

    # Find user by email
    user = await database.users.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Update user's service tier to ENTERPRISE
    result = await database.users.update_one(
        {"email": email},
        {
            "$set": {
                "service_tier": ServiceTier.ENTERPRISE,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    if result.modified_count == 0:
        # Check if already an admin
        if user.get("service_tier") == ServiceTier.ENTERPRISE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already an admin (ENTERPRISE tier)",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to promote user",
            )

    # Get updated user
    updated_user = await database.users.find_one({"email": email})

    logger.info(f"User {email} promoted to admin by {current_user.email}")

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


@router.post("/create-admin", response_model=UserResponse)
async def create_admin_user(
    email: str = Body(...),
    password: str = Body(...),
    full_name: Optional[str] = Body(None),
    current_user: UserInDB = Depends(get_admin_user),
):
    """Create a new admin user with ENTERPRISE tier."""

    # Check if user already exists
    existing_user = await database.users.find_one({"email": email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    # Hash the password
    hashed_password = get_password_hash(password)

    # Create new user with ENTERPRISE tier
    new_user = {
        "email": email,
        "hashed_password": hashed_password,
        "full_name": full_name,
        "service_tier": ServiceTier.ENTERPRISE,
        "is_active": True,
        "is_verified": True,  # Auto-verify admin users
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "usage": {
            "requests_today": 0,
            "requests_reset_date": datetime.utcnow(),
            "total_requests": 0,
            "storage_used_bytes": 0,
        },
    }

    result = await database.users.insert_one(new_user)

    # Get created user
    created_user = await database.users.find_one({"_id": result.inserted_id})

    logger.info(f"New admin user created: {email} by {current_user.email}")

    # Convert to response model
    return UserResponse(
        id=str(created_user["_id"]),
        email=created_user["email"],
        full_name=created_user.get("full_name"),
        service_tier=created_user["service_tier"],
        is_active=created_user["is_active"],
        is_verified=created_user["is_verified"],
        created_at=created_user["created_at"],
        usage=created_user["usage"],
    )


@router.post("/init-admin", status_code=status.HTTP_201_CREATED)
async def initialize_first_admin(
    email: str = Body(...),
    password: str = Body(...),
    full_name: Optional[str] = Body(None),
):
    """
    Initialize the first admin user. This endpoint should be disabled after initial setup.
    Can only be used when no admin users exist in the system.
    """

    try:
        # Check if any ENTERPRISE tier users exist
        admin_count = await database.users.count_documents(
            {"service_tier": ServiceTier.ENTERPRISE}
        )

        if admin_count > 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin users already exist. This endpoint is disabled.",
            )

        # Check if user already exists
        existing_user = await database.users.find_one({"email": email})
        if existing_user:
            # If user exists, promote to admin
            result = await database.users.update_one(
                {"email": email},
                {
                    "$set": {
                        "service_tier": ServiceTier.ENTERPRISE,
                        "updated_at": datetime.utcnow(),
                        "is_verified": True,
                        "is_active": True,
                    }
                },
            )
            logger.info(f"Existing user {email} promoted to first admin")
            return {
                "detail": "Existing user promoted to admin successfully",
                "email": email,
            }
        else:
            # Create new admin user
            hashed_password = get_password_hash(password)

            new_user = {
                "email": email,
                "hashed_password": hashed_password,
                "full_name": full_name,
                "service_tier": ServiceTier.ENTERPRISE,
                "is_active": True,
                "is_verified": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "usage": {
                    "requests_today": 0,
                    "requests_reset_date": datetime.utcnow(),
                    "total_requests": 0,
                    "storage_used_bytes": 0,
                },
            }

            result = await database.users.insert_one(new_user)
            logger.info(f"First admin user created: {email}")
            return {
                "detail": "First admin user created successfully",
                "email": email,
                "user_id": str(result.inserted_id),
            }
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating admin user: {str(e)}",
        )


@router.get("/system/info", response_model=Dict[str, Any])
async def get_system_info(current_user: UserInDB = Depends(get_admin_user)):
    """Get system information and statistics."""

    # Get user counts
    total_users = await database.users.count_documents({})
    active_users = await database.users.count_documents({"is_active": True})
    verified_users = await database.users.count_documents({"is_verified": True})

    # Get tier counts
    tier_counts = {}
    for tier in ServiceTier:
        count = await database.users.count_documents({"service_tier": tier})
        tier_counts[tier] = count

    # Get OAuth provider statistics
    google_users = await database.users.count_documents(
        {"oauth_providers.google": {"$exists": True}}
    )
    github_users = await database.users.count_documents(
        {"oauth_providers.github": {"$exists": True}}
    )

    # Get other collection stats
    collections_stats = {}
    for collection_name in await database.db.list_collection_names():
        count = await database.db[collection_name].count_documents({})
        collections_stats[collection_name] = count

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "verified": verified_users,
            "by_tier": tier_counts,
            "oauth": {"google": google_users, "github": github_users},
        },
        "collections": collections_stats,
        "server_time": datetime.utcnow(),
    }


@router.patch("/users/{user_id}/tier", response_model=UserResponse)
async def update_user_tier(
    user_id: str,
    tier: ServiceTier = Body(..., embed=True),
    current_user: UserInDB = Depends(get_admin_user),
):
    """Update a user's service tier."""

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

    # Update user's tier
    result = await database.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"service_tier": tier, "updated_at": datetime.utcnow()}},
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user tier",
        )

    # If changing to a higher tier, also reset the rate limit counter
    if tier != user.get("service_tier"):
        await database.users.update_one(
            {"_id": ObjectId(user_id)}, {"$set": {"usage.requests_today": 0}}
        )

    # Get updated user
    updated_user = await database.users.find_one({"_id": ObjectId(user_id)})

    logger.info(f"User {user_id} tier changed to {tier} by admin {current_user.email}")

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


@router.post("/users/{user_id}/exempt-from-rate-limits", status_code=status.HTTP_200_OK)
async def exempt_user_from_rate_limits(
    user_id: str,
    exempt: bool = Body(..., embed=True),
    current_user: UserInDB = Depends(get_admin_user),
):
    """Add or remove a user from the rate limit exemption list."""

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

    # Check current exemption status
    currently_exempt = is_exempt_from_rate_limits(user_id)

    # Update exemption status if needed
    if exempt and not currently_exempt:
        # Add to exemption list
        RATE_LIMIT_EXEMPT_USERS.append(user_id)
        logger.info(
            f"User {user_id} exempted from rate limits by admin {current_user.email}"
        )
        return {
            "message": f"User {user_id} is now exempt from rate limits",
            "exempt": True,
        }
    elif not exempt and currently_exempt:
        # Remove from exemption list
        RATE_LIMIT_EXEMPT_USERS.remove(user_id)
        logger.info(
            f"User {user_id} exemption from rate limits removed by admin {current_user.email}"
        )
        return {
            "message": f"User {user_id} is no longer exempt from rate limits",
            "exempt": False,
        }
    else:
        # No change needed
        status_msg = "already exempt" if exempt else "already not exempt"
        return {
            "message": f"User {user_id} is {status_msg} from rate limits",
            "exempt": exempt,
        }


@router.get("/rate-limits/exempt-users", status_code=status.HTTP_200_OK)
async def get_rate_limit_exempt_users(
    current_user: UserInDB = Depends(get_admin_user),
):
    """Get the list of exempt users."""
    return {"exempt_users": RATE_LIMIT_EXEMPT_USERS}


@router.patch("/users/{user_id}/verification", response_model=UserResponse)
async def update_user_verification_status(
    user_id: str,
    is_verified: bool = Body(..., embed=True),
    current_user: UserInDB = Depends(get_admin_user),
):
    """Update a user's verification status."""

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

    # Update verification status
    update_data = {"is_verified": is_verified, "updated_at": datetime.utcnow()}

    # Update user
    result = await database.users.update_one(
        {"_id": ObjectId(user_id)}, {"$set": update_data}
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user verification status",
        )

    # Get updated user
    updated_user = await database.users.find_one({"_id": ObjectId(user_id)})

    logger.info(
        f"User {user_id} verification status updated to {is_verified} by admin {current_user.email}"
    )

    # Convert to response model
    return UserResponse(
        id=str(updated_user["_id"]),
        email=updated_user["email"],
        full_name=updated_user.get("full_name"),
        service_tier=updated_user["service_tier"],
        is_active=updated_user["is_active"],
        is_verified=updated_user["is_verified"],
        subscribeToNewsletter=updated_user.get("subscribeToNewsletter", False),
        created_at=updated_user["created_at"],
        oauth_providers=updated_user.get("oauth_providers", {}),
        usage=updated_user["usage"],
    )
