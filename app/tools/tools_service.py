from fastapi import HTTPException
from uuid import UUID
from datetime import datetime
from typing import List, Optional, Union, Dict, Any

from ..database.database import tools
from .models import ToolCreate, ToolUpdate, ToolInDB, ToolResponse
from ..algolia.indexer import algolia_indexer


async def get_tools(
    skip: int = 0, limit: int = 100, count_only: bool = False
) -> Union[List[ToolResponse], int]:
    """
    Retrieve a list of tools with pagination.
    If count_only is True, returns only the total count of tools.
    """
    if count_only:
        return await tools.count_documents({})

    cursor = tools.find().skip(skip).limit(limit)
    tools_list = []

    async for tool in cursor:
        tool_response = ToolResponse(
            id=tool.get("id"),
            price=tool.get("price"),
            name=tool.get("name"),
            description=tool.get("description"),
            link=tool.get("link"),
            unique_id=tool.get("unique_id"),
            rating=tool.get("rating"),
            saved_numbers=tool.get("saved_numbers"),
            created_at=tool.get("created_at"),
            updated_at=tool.get("updated_at"),
            category=tool.get("category"),
            features=tool.get("features"),
            is_featured=tool.get("is_featured", False),
            saved_by_user=False,  # Default value, will be set per-user when implemented
        )
        tools_list.append(tool_response)

    return tools_list


async def get_tool_by_id(tool_id: UUID) -> Optional[ToolResponse]:
    """
    Retrieve a tool by its UUID.
    """
    tool = await tools.find_one({"id": str(tool_id)})

    if not tool:
        return None

    return ToolResponse(
        id=tool.get("id"),
        price=tool.get("price"),
        name=tool.get("name"),
        description=tool.get("description"),
        link=tool.get("link"),
        unique_id=tool.get("unique_id"),
        rating=tool.get("rating"),
        saved_numbers=tool.get("saved_numbers"),
        created_at=tool.get("created_at"),
        updated_at=tool.get("updated_at"),
        category=tool.get("category"),
        features=tool.get("features"),
        is_featured=tool.get("is_featured", False),
        saved_by_user=False,  # Default value, will be set per-user when implemented
    )


async def get_tool_by_unique_id(unique_id: str) -> Optional[ToolResponse]:
    """
    Retrieve a tool by its unique_id.
    """
    tool = await tools.find_one({"unique_id": unique_id})

    if not tool:
        return None

    return ToolResponse(
        id=tool.get("id"),
        price=tool.get("price"),
        name=tool.get("name"),
        description=tool.get("description"),
        link=tool.get("link"),
        unique_id=tool.get("unique_id"),
        rating=tool.get("rating"),
        saved_numbers=tool.get("saved_numbers"),
        created_at=tool.get("created_at"),
        updated_at=tool.get("updated_at"),
        category=tool.get("category"),
        features=tool.get("features"),
        is_featured=tool.get("is_featured", False),
        saved_by_user=False,  # Default value, will be set per-user when implemented
    )


async def create_tool(tool_data: ToolCreate) -> ToolResponse:
    """
    Create a new tool.
    """
    # Check if a tool with the unique_id already exists
    existing_tool = await tools.find_one({"unique_id": tool_data.unique_id})
    if existing_tool:
        raise HTTPException(
            status_code=400, detail="Tool with this unique_id already exists"
        )

    # Create the tool
    now = datetime.utcnow()
    tool_dict = tool_data.model_dump()
    tool_dict["created_at"] = now
    tool_dict["updated_at"] = now

    # Ensure the UUID is stored as a string in MongoDB
    tool_dict["id"] = str(tool_dict["id"])

    # Insert into MongoDB
    result = await tools.insert_one(tool_dict)

    # Return the created tool
    created_tool = await tools.find_one({"_id": result.inserted_id})

    # Index in Algolia
    await algolia_indexer.index_tool(created_tool)

    return ToolResponse(
        id=created_tool.get("id"),
        price=created_tool.get("price"),
        name=created_tool.get("name"),
        description=created_tool.get("description"),
        link=created_tool.get("link"),
        unique_id=created_tool.get("unique_id"),
        rating=created_tool.get("rating"),
        saved_numbers=created_tool.get("saved_numbers"),
        created_at=created_tool.get("created_at"),
        updated_at=created_tool.get("updated_at"),
        category=created_tool.get("category"),
        features=created_tool.get("features"),
        is_featured=created_tool.get("is_featured", False),
        saved_by_user=False,  # Default value, will be set per-user when implemented
    )


async def update_tool(tool_id: UUID, tool_update: ToolUpdate) -> Optional[ToolResponse]:
    """
    Update a tool by UUID.
    """
    # Check if the tool exists
    existing_tool = await tools.find_one({"id": str(tool_id)})
    if not existing_tool:
        return None

    # Prepare update data
    update_data = tool_update.model_dump(exclude_unset=True)

    if update_data:
        update_data["updated_at"] = datetime.utcnow()

        # Update the tool
        await tools.update_one({"id": str(tool_id)}, {"$set": update_data})

    # Return the updated tool
    updated_tool = await tools.find_one({"id": str(tool_id)})

    # Update in Algolia
    await algolia_indexer.index_tool(updated_tool)

    return ToolResponse(
        id=updated_tool.get("id"),
        price=updated_tool.get("price"),
        name=updated_tool.get("name"),
        description=updated_tool.get("description"),
        link=updated_tool.get("link"),
        unique_id=updated_tool.get("unique_id"),
        rating=updated_tool.get("rating"),
        saved_numbers=updated_tool.get("saved_numbers"),
        created_at=updated_tool.get("created_at"),
        updated_at=updated_tool.get("updated_at"),
        category=updated_tool.get("category"),
        features=updated_tool.get("features"),
        is_featured=updated_tool.get("is_featured", False),
        saved_by_user=False,  # Default value, will be set per-user when implemented
    )


async def delete_tool(tool_id: UUID) -> bool:
    """
    Delete a tool by UUID.
    """
    # Check if the tool exists
    existing_tool = await tools.find_one({"id": str(tool_id)})
    if not existing_tool:
        return False

    # Delete from Algolia first
    await algolia_indexer.delete_tool(existing_tool.get("_id"))

    # Delete from MongoDB
    result = await tools.delete_one({"id": str(tool_id)})

    return result.deleted_count > 0


async def search_tools(
    query: str, skip: int = 0, limit: int = 100, count_only: bool = False
) -> Union[List[ToolResponse], int]:
    """
    Search for tools by name or description.
    Uses Algolia search when available, falls back to MongoDB text search.
    If count_only is True, returns only the total count of matching tools.
    """
    from ..algolia.config import algolia_config
    from ..algolia.models import SearchParams
    from ..algolia.search import algolia_search

    # Try using Algolia first if configured
    if algolia_config.is_configured():
        try:
            # Create search parameters
            params = SearchParams(
                query=query,
                page=(
                    skip // limit + 1 if not count_only else 1
                ),  # Convert skip/limit to page-based pagination
                per_page=(
                    1 if count_only else limit
                ),  # Only need one result if just counting
            )

            # Execute search with Algolia
            result = await algolia_search.search_tools(params)

            if count_only:
                return result.total

            # Convert Algolia results to ToolResponse objects
            tools_list = []
            for tool in result.tools:
                tool_response = ToolResponse(
                    id=tool.objectID,
                    price=(
                        tool.pricing.type.value
                        if hasattr(tool, "pricing") and tool.pricing
                        else None
                    ),
                    name=tool.name,
                    description=tool.description,
                    link=tool.website if hasattr(tool, "website") else None,
                    unique_id=tool.slug if hasattr(tool, "slug") else None,
                    rating=(
                        str(tool.ratings.average)
                        if hasattr(tool, "ratings") and tool.ratings
                        else None
                    ),
                    saved_numbers=None,
                    created_at=tool.created_at,
                    updated_at=tool.updated_at,
                    category=(
                        tool.categories[0].name
                        if hasattr(tool, "categories") and tool.categories
                        else None
                    ),
                    features=tool.features if hasattr(tool, "features") else None,
                    is_featured=(
                        tool.is_featured if hasattr(tool, "is_featured") else False
                    ),
                    saved_by_user=False,  # Default value, will be set per-user when implemented
                )
                tools_list.append(tool_response)
            return tools_list
        except Exception as e:
            # Log the error and fall back to MongoDB
            from ..logger import logger

            logger.error(
                f"Error searching with Algolia, falling back to MongoDB: {str(e)}"
            )

    # Fall back to MongoDB text search
    if count_only:
        return await tools.count_documents({"$text": {"$search": query}})

    cursor = tools.find({"$text": {"$search": query}}).skip(skip).limit(limit)

    tools_list = []

    async for tool in cursor:
        tool_response = ToolResponse(
            id=tool.get("id"),
            price=tool.get("price"),
            name=tool.get("name"),
            description=tool.get("description"),
            link=tool.get("link"),
            unique_id=tool.get("unique_id"),
            rating=tool.get("rating"),
            saved_numbers=tool.get("saved_numbers"),
            created_at=tool.get("created_at"),
            updated_at=tool.get("updated_at"),
            category=tool.get("category"),
            features=tool.get("features"),
            is_featured=tool.get("is_featured", False),
            saved_by_user=False,  # Default value, will be set per-user when implemented
        )
        tools_list.append(tool_response)

    return tools_list
