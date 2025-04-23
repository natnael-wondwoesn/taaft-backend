from fastapi import HTTPException
from uuid import UUID, uuid4
from datetime import datetime
from typing import List, Optional, Union, Dict, Any

from ..database.database import tools
from .models import ToolCreate, ToolUpdate, ToolInDB, ToolResponse
from ..algolia.indexer import algolia_indexer
from ..categories.service import categories_service


def create_tool_response(tool: Dict[str, Any]) -> Optional[ToolResponse]:
    """
    Helper function to create a ToolResponse with default values for missing fields.
    """
    try:
        # Ensure we always have a valid ID
        tool_id = tool.get("id")
        if not tool_id:
            tool_id = str(uuid4())
            # Log this occurrence as it shouldn't normally happen
            from ..logger import logger

            logger.warning(f"Tool without ID found, generated new ID: {tool_id}")

        return ToolResponse(
            id=tool_id,
            price=tool.get("price") or "",
            name=tool.get("name") or "",
            description=tool.get("description") or "",
            link=tool.get("link") or "",
            unique_id=tool.get("unique_id") or "",
            rating=tool.get("rating"),
            saved_numbers=tool.get("saved_numbers"),
            created_at=tool.get("created_at") or datetime.utcnow(),
            updated_at=tool.get("updated_at") or datetime.utcnow(),
            category=tool.get("category"),
            features=tool.get("features"),
            is_featured=tool.get("is_featured", False),
            saved_by_user=False,  # Default value, will be set per-user when implemented
        )
    except Exception as e:
        # Log the error
        from ..logger import logger

        logger.error(f"Error creating ToolResponse: {str(e)}")
        return None


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
        tool_response = create_tool_response(tool)
        if tool_response:
            tools_list.append(tool_response)

    return tools_list


async def get_tool_by_id(tool_id: UUID) -> Optional[ToolResponse]:
    """
    Retrieve a tool by its UUID.
    """
    tool = await tools.find_one({"id": str(tool_id)})

    if not tool:
        return None

    return create_tool_response(tool)


async def get_tool_by_unique_id(unique_id: str) -> Optional[ToolResponse]:
    """
    Retrieve a tool by its unique_id.
    """
    tool = await tools.find_one({"unique_id": unique_id})

    if not tool:
        return None

    return create_tool_response(tool)


async def create_tool(tool_data: ToolCreate) -> ToolResponse:
    """
    Create a new tool.
    """
    try:
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

        # Ensure the UUID is stored as a string in MongoDB and is never null
        if not tool_dict.get("id"):
            tool_dict["id"] = str(uuid4())
        else:
            tool_dict["id"] = str(tool_dict["id"])

        # Process categories
        categories_list = []
        # Handle single category field
        if tool_dict.get("category"):
            # Process single category
            category_id = tool_dict["category"]
            category_name = category_id.replace("-", " ").title()
            category_slug = category_id.lower()

            # Create category data
            category_data = {
                "id": category_id,
                "name": category_name,
                "slug": category_slug,
            }

            # Update or create the category
            await categories_service.update_or_create_category(category_data)

            # Add to the list of categories
            categories_list.append(category_data)

        # Handle categories list (category_ids)
        if tool_dict.get("category_ids"):
            for category_id in tool_dict["category_ids"]:
                if not any(cat["id"] == category_id for cat in categories_list):
                    category_name = category_id.replace("-", " ").title()
                    category_slug = category_id.lower()

                    # Create category data
                    category_data = {
                        "id": category_id,
                        "name": category_name,
                        "slug": category_slug,
                    }

                    # Update or create the category
                    await categories_service.update_or_create_category(category_data)

                    # Add to the list of categories
                    categories_list.append(category_data)

        # Store categories in tool document
        if categories_list:
            tool_dict["categories"] = categories_list

        # Insert into MongoDB
        result = await tools.insert_one(tool_dict)

        # Return the created tool
        created_tool = await tools.find_one({"_id": result.inserted_id})

        # Index in Algolia
        await algolia_indexer.index_tool(created_tool)

        # Create and return the response
        tool_response = create_tool_response(created_tool)
        if not tool_response:
            raise HTTPException(
                status_code=500, detail="Failed to create tool response"
            )
        return tool_response
    except Exception as e:
        # Log the error for debugging
        from ..logger import logger

        logger.error(f"Tool creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create tool: {str(e)}")


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

        # Process categories if update includes category-related fields
        categories_list = existing_tool.get("categories", [])
        has_category_changes = False

        # Check for category updates
        if "category" in update_data:
            has_category_changes = True
            category_id = update_data["category"]

            # Only process if category is changed
            if not any(cat.get("id") == category_id for cat in categories_list):
                # Process single category
                category_name = category_id.replace("-", " ").title()
                category_slug = category_id.lower()

                # Create category data
                category_data = {
                    "id": category_id,
                    "name": category_name,
                    "slug": category_slug,
                }

                # Update or create the category
                await categories_service.update_or_create_category(category_data)

                # Replace with new category or add if none exists
                if categories_list:
                    categories_list = [
                        cat for cat in categories_list if cat.get("id") != category_id
                    ]
                    categories_list.append(category_data)
                else:
                    categories_list = [category_data]

        # Handle categories list (category_ids)
        if "category_ids" in update_data:
            has_category_changes = True
            new_categories = []

            for category_id in update_data["category_ids"]:
                # Check if the category is already in the list
                existing_category = next(
                    (cat for cat in categories_list if cat.get("id") == category_id),
                    None,
                )
                if existing_category:
                    new_categories.append(existing_category)
                else:
                    # Process new category
                    category_name = category_id.replace("-", " ").title()
                    category_slug = category_id.lower()

                    # Create category data
                    category_data = {
                        "id": category_id,
                        "name": category_name,
                        "slug": category_slug,
                    }

                    # Update or create the category
                    await categories_service.update_or_create_category(category_data)

                    # Add to the new list
                    new_categories.append(category_data)

            # Replace categories list with the new one
            categories_list = new_categories

        # Add updated categories to update data if changed
        if has_category_changes:
            update_data["categories"] = categories_list

        # Update the tool
        await tools.update_one({"id": str(tool_id)}, {"$set": update_data})

    # Return the updated tool
    updated_tool = await tools.find_one({"id": str(tool_id)})

    # Update in Algolia
    await algolia_indexer.index_tool(updated_tool)

    # Create and return the response
    return create_tool_response(updated_tool)


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
                # Convert Algolia result to a dictionary format compatible with our helper
                tool_dict = {
                    "id": tool.objectID,
                    "price": (
                        tool.pricing.type.value
                        if hasattr(tool, "pricing") and tool.pricing
                        else ""
                    ),
                    "name": tool.name,
                    "description": tool.description,
                    "link": tool.website if hasattr(tool, "website") else "",
                    "unique_id": tool.slug if hasattr(tool, "slug") else "",
                    "rating": (
                        str(tool.ratings.average)
                        if hasattr(tool, "ratings") and tool.ratings
                        else None
                    ),
                    "saved_numbers": None,
                    "created_at": tool.created_at,
                    "updated_at": tool.updated_at,
                    "category": (
                        tool.categories[0].name
                        if hasattr(tool, "categories") and tool.categories
                        else None
                    ),
                    "features": tool.features if hasattr(tool, "features") else None,
                    "is_featured": (
                        tool.is_featured if hasattr(tool, "is_featured") else False
                    ),
                }

                tool_response = create_tool_response(tool_dict)
                if tool_response:
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
        tool_response = create_tool_response(tool)
        if tool_response:
            tools_list.append(tool_response)

    return tools_list
