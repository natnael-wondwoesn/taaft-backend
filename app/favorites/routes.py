from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import List, Optional
from uuid import UUID

from ..auth.dependencies import get_current_active_user
from ..models.user import UserResponse
from ..models.favorites import FavoriteCreate, FavoriteResponse, FavoritesListResponse
from ..services.favorites_service import (
    add_favorite,
    remove_favorite,
    get_user_favorites,
    is_tool_favorited,
)
from ..tools.tools_service import get_tool_by_unique_id, get_tools
from . import router


@router.post("/", response_model=FavoriteResponse)
async def add_to_favorites(
    favorite_data: FavoriteCreate,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    Add a tool to the user's favorites.
    """
    return await add_favorite(current_user.id, favorite_data)


@router.delete("/{tool_unique_id}", status_code=204)
async def remove_from_favorites(
    tool_unique_id: str = Path(
        ..., description="Unique ID of the tool to remove from favorites"
    ),
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    Remove a tool from the user's favorites.
    """
    await remove_favorite(current_user.id, tool_unique_id)
    return None


@router.get("/", response_model=FavoritesListResponse)
async def list_favorites(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    Get a list of user's favorite tools.
    """
    # Get favorite relations
    favorites = await get_user_favorites(
        user_id=current_user.id, skip=skip, limit=limit
    )

    # Get total count of favorites
    total = await get_user_favorites(user_id=current_user.id, count_only=True)

    return {"favorites": favorites, "total": total, "skip": skip, "limit": limit}


@router.get("/tools", response_model=List[dict])
async def list_favorite_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    Get a list of tools that the user has favorited, including full tool details.
    """
    # Get favorite relations
    favorites = await get_user_favorites(
        user_id=current_user.id, skip=skip, limit=limit
    )

    # Get tool details for each favorite
    favorite_tools = []
    for favorite in favorites:
        tool = await get_tool_by_unique_id(favorite.tool_unique_id)
        if tool:
            # Convert to dict and add favorite information
            tool_dict = tool.dict()
            tool_dict["favorited_at"] = favorite.created_at
            tool_dict["favorite_id"] = favorite.id
            tool_dict["saved_by_user"] = True
            favorite_tools.append(tool_dict)

    return favorite_tools
