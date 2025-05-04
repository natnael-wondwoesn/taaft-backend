from fastapi import HTTPException
from uuid import UUID
from typing import List, Optional, Union, Dict, Any
from datetime import datetime
import os
from bson import ObjectId

from ..database.database import shares, tools
from ..models.shares import ShareCreate, ShareInDB, ShareResponse
from ..logger import logger


async def create_share(user_id: str, share_data: ShareCreate) -> ShareResponse:
    """
    Create a share for a tool.

    Args:
        user_id: ID of the user
        share_data: Data for the share to create

    Returns:
        Created share with share link
    """
    # Check if the tool exists
    tool = await tools.find_one({"unique_id": share_data.tool_unique_id})
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    # Create new share
    share_id = str(UUID(int=int(datetime.utcnow().timestamp())))
    share = {
        "user_id": str(user_id),
        "tool_unique_id": share_data.tool_unique_id,
        "share_id": share_id,
        "created_at": datetime.utcnow(),
    }

    # Insert into database
    result = await shares.insert_one(share)

    # Get the inserted share
    share["_id"] = result.inserted_id

    # Generate share link
    base_url = os.getenv("FRONTEND_URL", "https://taaft.ai")
    share_link = f"{base_url}/tool/{tool['unique_id']}?share={share_id}"

    # Convert to response model
    return ShareResponse(
        id=str(result.inserted_id),
        user_id=str(user_id),
        tool_unique_id=share_data.tool_unique_id,
        share_id=share_id,
        created_at=share["created_at"],
        share_link=share_link,
    )


async def get_share_by_id(share_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a share by its unique ID.

    Args:
        share_id: The unique share ID

    Returns:
        Share details or None if not found
    """
    share = await shares.find_one({"share_id": share_id})
    if not share:
        return None

    # Get the tool details
    tool = await tools.find_one({"unique_id": share["tool_unique_id"]})
    if not tool:
        return None

    return {"share": share, "tool": tool}


async def get_user_shares(
    user_id: str, skip: int = 0, limit: int = 100, count_only: bool = False
) -> Union[List[ShareResponse], int]:
    """
    Get a list of user's shares.

    Args:
        user_id: ID of the user
        skip: Number of items to skip
        limit: Maximum number of items to return
        count_only: If True, return only the count

    Returns:
        List of shares or count
    """
    # Create filter
    filter_query = {"user_id": str(user_id)}

    # Count mode
    if count_only:
        return await shares.count_documents(filter_query)

    # Get the shares
    cursor = shares.find(filter_query).sort("created_at", -1).skip(skip).limit(limit)

    # Convert to list of dictionaries
    shares_list = []
    async for share in cursor:
        # Generate share link
        base_url = os.getenv("FRONTEND_URL", "https://taaft.ai")
        tool = await tools.find_one({"unique_id": share["tool_unique_id"]})
        if tool:
            share_link = (
                f"{base_url}/tool/{tool['unique_id']}?share={share['share_id']}"
            )

            shares_list.append(
                ShareResponse(
                    id=str(share["_id"]),
                    user_id=str(share["user_id"]),
                    tool_unique_id=share["tool_unique_id"],
                    share_id=share["share_id"],
                    created_at=share["created_at"],
                    share_link=share_link,
                )
            )

    return shares_list
