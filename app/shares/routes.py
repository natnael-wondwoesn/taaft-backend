from fastapi import APIRouter, HTTPException, Depends, Query, Request, status
from typing import List, Optional, Dict, Any
from uuid import UUID

from ..auth.dependencies import get_current_active_user
from ..models.user import UserResponse
from ..models.shares import (
    ShareCreate,
    ShareResponse,
    ShareWithToolResponse,
    ShareInfoResponse,
)
from ..services.shares_service import (
    create_share,
    get_share_by_id,
    get_user_shares,
    delete_share,
)
from ..tools.tools_service import get_tool_by_unique_id
from . import router


@router.post(
    "/",
    response_model=ShareResponse,
    status_code=201,
    responses={
        400: {"description": "Bad Request - Tool unique ID cannot be empty"},
        404: {"description": "Not Found - Tool not found"},
        401: {"description": "Unauthorized"},
    },
)
async def share_tool(
    share_data: ShareCreate,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    Create a shareable link for a tool.

    - **share_data**: The data for creating the share, including the tool's unique identifier
    - Returns the created share with a shareable link
    - Errors: 400 if tool_unique_id is empty, 404 if tool not found
    """
    return await create_share(current_user.id, share_data)


@router.get("/by-id/{share_id}", response_model=ShareWithToolResponse)
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

    return ShareWithToolResponse(
        tool=tool,
        share=ShareInfoResponse(
            id=share["share_id"],
            created_at=share["created_at"],
            shared_by=share["user_id"],
        ),
    )


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


@router.delete(
    "/{share_id}",
    status_code=204,
    responses={
        403: {"description": "Forbidden - Not the owner of the share"},
        404: {"description": "Not Found - Share not found"},
        401: {"description": "Unauthorized"},
    },
)
async def remove_share(
    share_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    Delete a share by ID.

    - **share_id**: The unique identifier of the share to delete
    - Only the owner of the share can delete it
    - Returns 204 No Content on success
    - Errors: 404 if share not found, 403 if not the owner
    """
    success = await delete_share(current_user.id, share_id)

    if not success:
        # Check if the share exists
        share_data = await get_share_by_id(share_id)
        if not share_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Share not found"
            )
        else:
            # If share exists but couldn't delete, user is not the owner
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this share",
            )

    return None  # 204 No Content
