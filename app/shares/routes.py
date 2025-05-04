from fastapi import APIRouter, HTTPException, Depends, Query, Request
from typing import List, Optional, Dict, Any
from uuid import UUID

from ..auth.dependencies import get_current_active_user
from ..models.user import UserResponse
from ..models.shares import ShareCreate, ShareResponse
from ..services.shares_service import create_share, get_share_by_id, get_user_shares
from ..tools.tools_service import get_tool_by_unique_id
from . import router


@router.post("/", response_model=ShareResponse)
async def share_tool(
    share_data: ShareCreate,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    Create a shareable link for a tool.
    """
    return await create_share(current_user.id, share_data)


@router.get("/by-id/{share_id}")
async def get_share(share_id: str, request: Request):
    """
    Get tool details by share ID.
    This endpoint is public and does not require authentication.
    """
    share_data = await get_share_by_id(share_id)
    if not share_data:
        raise HTTPException(status_code=404, detail="Share not found")

    # Return the tool data with share information
    tool = share_data["tool"]
    share = share_data["share"]

    return {
        "tool": tool,
        "share": {
            "id": share["share_id"],
            "created_at": share["created_at"],
            "shared_by": share["user_id"],
        },
    }


@router.get("/my-shares", response_model=List[ShareResponse])
async def list_user_shares(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    Get a list of tools that the user has shared.
    """
    shares = await get_user_shares(user_id=current_user.id, skip=skip, limit=limit)

    return shares
