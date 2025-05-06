from fastapi import HTTPException
from uuid import UUID
from typing import List, Optional, Union, Dict, Any
from datetime import datetime
from bson import ObjectId

from ..database.database import favorites, tools, users
from ..models.favorites import FavoriteCreate, FavoriteInDB, FavoriteResponse
from ..logger import logger


async def add_favorite(
    user_id: str,
    favorite_data: FavoriteCreate,
) -> FavoriteResponse:
    """
    Add a tool to user's favorites.

    Args:
        user_id: ID of the user
        favorite_data: Data for the favorite to create

    Returns:
        Created favorite
    """
    # Check if the tool exists
    tool = await tools.find_one({"unique_id": favorite_data.tool_unique_id})
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    # Check if the favorite already exists
    existing_favorite = await favorites.find_one(
        {"user_id": str(user_id), "tool_unique_id": favorite_data.tool_unique_id}
    )

    if existing_favorite:
        raise HTTPException(status_code=409, detail="Tool is already in favorites")

    # Create new favorite
    favorite = {
        "user_id": str(user_id),
        "tool_unique_id": favorite_data.tool_unique_id,
        "created_at": datetime.utcnow(),
    }

    # Insert into database
    result = await favorites.insert_one(favorite)

    # Add the tool's unique_id to the user's saved_tools array
    await users.update_one(
        {"_id": ObjectId(user_id)},
        {"$addToSet": {"saved_tools": favorite_data.tool_unique_id}},
    )

    # Get the inserted favorite
    favorite["_id"] = result.inserted_id

    # Convert to response model
    return FavoriteResponse(
        id=str(result.inserted_id),
        user_id=str(user_id),
        tool_unique_id=favorite_data.tool_unique_id,
        created_at=favorite["created_at"],
    )


async def remove_favorite(user_id: str, tool_unique_id: str) -> bool:
    """
    Remove a tool from user's favorites.

    Args:
        user_id: ID of the user
        tool_unique_id: Unique ID of the tool to remove from favorites

    Returns:
        True if successful, raises exception otherwise
    """
    logger.info(
        f"Attempting to remove favorite: user_id={user_id}, tool_unique_id={tool_unique_id}"
    )

    # Find and delete the favorite
    result = await favorites.delete_one(
        {"user_id": str(user_id), "tool_unique_id": tool_unique_id}
    )

    if result.deleted_count == 0:
        logger.warning(
            f"Favorite not found: user_id={user_id}, tool_unique_id={tool_unique_id}"
        )
        raise HTTPException(status_code=404, detail="Favorite not found")

    # Remove the tool's unique_id from the user's saved_tools array
    await users.update_one(
        {"_id": ObjectId(user_id)}, {"$pull": {"saved_tools": tool_unique_id}}
    )

    logger.info(
        f"Successfully removed favorite: user_id={user_id}, tool_unique_id={tool_unique_id}"
    )
    return True


async def get_user_favorites(
    user_id: str, skip: int = 0, limit: int = 100, count_only: bool = False
) -> Union[List[FavoriteResponse], int]:
    """
    Get a list of user's favorite tools.

    Args:
        user_id: ID of the user
        skip: Number of items to skip
        limit: Maximum number of items to return
        count_only: If True, return only the count

    Returns:
        List of favorites or count
    """
    # Create filter
    filter_query = {"user_id": str(user_id)}

    # Count mode
    if count_only:
        return await favorites.count_documents(filter_query)

    # Get the favorites
    cursor = favorites.find(filter_query).sort("created_at", -1).skip(skip).limit(limit)

    # Convert to list of dictionaries
    favorites_list = []
    async for favorite in cursor:
        favorites_list.append(
            FavoriteResponse(
                id=str(favorite["_id"]),
                user_id=favorite["user_id"],
                tool_unique_id=favorite["tool_unique_id"],
                created_at=favorite["created_at"],
            )
        )

    return favorites_list


async def is_tool_favorited(user_id: str, tool_unique_id: str) -> bool:
    """
    Check if a tool is in the user's favorites.

    Args:
        user_id: ID of the user
        tool_unique_id: Unique ID of the tool

    Returns:
        True if the tool is in favorites, False otherwise
    """
    favorite = await favorites.find_one(
        {"user_id": str(user_id), "tool_unique_id": tool_unique_id}
    )

    return favorite is not None
