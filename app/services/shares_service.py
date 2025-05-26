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
    # Validate tool_unique_id
    if not share_data.tool_unique_id or share_data.tool_unique_id.strip() == "":
        raise HTTPException(status_code=400, detail="Tool unique ID cannot be empty")

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
    base_url = os.getenv("FRONTEND_URL", "https://taaft-development.vercel.app")
    share_link = f"{base_url}/tools/{tool['id']}?share={share_id}"

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

    # Convert ObjectId to string to avoid serialization issues
    serialized_share = {
        "share_id": share["share_id"],
        "user_id": share["user_id"],
        "tool_unique_id": share["tool_unique_id"],
        "created_at": share["created_at"],
        "_id": str(share["_id"]),
    }

    # Convert ObjectId to string in tool document
    serialized_tool = dict(tool)
    if "_id" in serialized_tool:
        serialized_tool["_id"] = str(serialized_tool["_id"])

    # Handle any other potential ObjectId fields in the tool object recursively
    def convert_objectid_to_str(obj):
        if isinstance(obj, dict):
            return {k: convert_objectid_to_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_objectid_to_str(item) for item in obj]
        elif isinstance(obj, ObjectId):
            return str(obj)
        else:
            return obj

    serialized_tool = convert_objectid_to_str(serialized_tool)

    return {"share": serialized_share, "tool": serialized_tool}


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
        base_url = os.getenv("FRONTEND_URL", "https://taaft-development.vercel.app")
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


async def delete_share(user_id: str, share_id: str) -> bool:
    """
    Delete a share by ID.

    Args:
        user_id: ID of the user (for authorization)
        share_id: ID of the share to delete

    Returns:
        True if the share was deleted, False otherwise
    """
    # Find the share to verify ownership
    share = await shares.find_one({"share_id": share_id})

    if not share:
        return False

    # Check if the user is the owner of the share
    if str(share["user_id"]) != str(user_id):
        return False

    # Delete the share
    result = await shares.delete_one({"share_id": share_id})

    # Return success based on if something was deleted
    return result.deleted_count > 0
