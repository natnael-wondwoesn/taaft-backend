from fastapi import HTTPException
from uuid import UUID, uuid4, uuid5, NAMESPACE_OID
from datetime import datetime
import asyncio
from typing import List, Optional, Union, Dict, Any
from bson import ObjectId

from app.algolia.models import AlgoliaToolRecord

from ..database.database import tools, database, favorites
from .models import ToolCreate, ToolUpdate, ToolInDB, ToolResponse
from ..algolia.indexer import algolia_indexer
from ..categories.service import categories_service
from collections import Counter
from ..services.redis_cache import redis_cache, invalidate_cache

from ..logger import logger

# Keywords collection
keywords_collection = database.get_collection("keywords")


def objectid_to_uuid(objectid_str: str) -> UUID:
    """
    Converts an ObjectId string to a deterministic UUID.
    Uses UUID v5 with the ObjectId as the name and NAMESPACE_OID as namespace.
    """
    try:
        # Ensure we have a string representation of the ObjectId
        if hasattr(objectid_str, "_id"):
            objectid_str = str(objectid_str._id)
        elif hasattr(objectid_str, "__str__"):
            objectid_str = str(objectid_str)

        # Create a UUID5 (name-based) using the ObjectId string
        return uuid5(NAMESPACE_OID, objectid_str)
    except Exception as e:
        # Fall back to a random UUID if conversion fails
        logger.error(f"Failed to convert ObjectId to UUID: {e}")
        return uuid4()


def extract_keywords_from_text(text: str) -> List[str]:
    """
    Extract meaningful keywords from text using basic techniques.
    Simplified implementation that doesn't use NLTK.

    Args:
        text: The text to extract keywords from

    Returns:
        List of keywords extracted from the text
    """
    if not text:
        return []

    try:
        # Basic stopwords list
        common_stopwords = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "if",
            "then",
            "else",
            "when",
            "at",
            "from",
            "by",
            "for",
            "with",
            "about",
            "against",
            "between",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "to",
            "of",
            "in",
            "on",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "where",
            "why",
            "how",
            "all",
            "any",
            "both",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "can",
            "will",
            "just",
            "should",
            "now",
            "tool",
            "tools",
            "ai",
            "intelligence",
            "artificial",
            "model",
            "models",
            "system",
            "platform",
            "app",
            "application",
            "software",
            "service",
            "solution",
            "technology",
        }

        # Simple tokenization by splitting on whitespace
        tokens = text.lower().split()

        # Filter out stopwords, short words, and non-alphanumeric tokens
        filtered_tokens = [
            token
            for token in tokens
            if token not in common_stopwords and len(token) > 2 and token.isalnum()
        ]

        # Count term frequency
        token_counts = Counter(filtered_tokens)

        # Get the most common terms (limit to 10)
        keywords = [token for token, count in token_counts.most_common(10)]

        return keywords
    except Exception as e:
        logger.error(f"Keyword extraction failed: {str(e)}")
        # Ultra-basic fallback
        if not text:
            return []
        words = text.lower().split()
        basic_keywords = list(set([w for w in words if len(w) > 3]))[:10]
        return basic_keywords


def extract_keywords(tool: Dict[str, Any]) -> List[str]:
    """
    Extract keywords from a tool document.

    Args:
        tool: The tool document from MongoDB

    Returns:
        List of keywords extracted from the tool
    """
    all_keywords = set()

    # Use existing keywords if available
    if "keywords" in tool and tool["keywords"]:
        all_keywords.update(tool["keywords"])
        return list(all_keywords)

    # Extract keywords from name
    if "name" in tool and tool["name"]:
        name_keywords = extract_keywords_from_text(tool["name"])
        all_keywords.update(name_keywords)

    # Extract keywords from description
    if "description" in tool and tool["description"]:
        desc_keywords = extract_keywords_from_text(tool["description"])
        all_keywords.update(desc_keywords)

    # Include category as a keyword
    if "category" in tool and tool["category"]:
        if isinstance(tool["category"], str):
            category_words = extract_keywords_from_text(tool["category"])
            all_keywords.update(category_words)

    # Include features as keywords
    if "features" in tool and tool["features"]:
        for feature in tool["features"]:
            if isinstance(feature, str):
                feature_keywords = extract_keywords_from_text(feature)
                all_keywords.update(feature_keywords)

    # Include tags as keywords
    if "tags" in tool and tool["tags"]:
        for tag in tool["tags"]:
            if isinstance(tag, str):
                all_keywords.add(tag.lower())

    # For pricing_type specifically, include it as a keyword
    if "pricing_type" in tool and tool["pricing_type"]:
        pricing_type = tool["pricing_type"].lower()
        all_keywords.add(pricing_type)

    return list(all_keywords)


async def update_tool_keywords(tool_id: str, tool_name: str, keywords: List[str]):
    """
    Update the keywords collection with tool keywords.

    Args:
        tool_id: The tool ID
        tool_name: The tool name
        keywords: List of keywords
    """
    # Store each keyword in keywords collection
    for keyword in keywords:
        await keywords_collection.update_one(
            {"keyword": keyword},
            {
                "$set": {"updated_at": datetime.utcnow()},
                "$setOnInsert": {"created_at": datetime.utcnow()},
                "$inc": {"frequency": 1},
                "$addToSet": {
                    "tools": {"tool_id": str(tool_id), "tool_name": tool_name}
                },
            },
            upsert=True,
        )


async def create_tool_response(tool: Dict[str, Any]) -> Optional[ToolResponse]:
    """
    Helper function to create a ToolResponse with default values for missing fields.
    Uses the string representation of _id if the primary 'id' field is missing.
    """
    try:
        # Prioritize the primary 'id' field (string UUID)
        tool_id = tool.get("id")

        # If 'id' is missing or empty, use a UUID derived from '_id'
        if not tool_id or tool_id == "":
            if "_id" in tool:
                # Get the ObjectId - can be a string or an actual ObjectId object
                objectid = tool.get("_id")
                # Convert ObjectId to a UUID
                derived_uuid = objectid_to_uuid(objectid)
                tool_id = str(derived_uuid)
                # Optionally log that we're deriving a UUID from _id
                logger.info(
                    f"Derived UUID {tool_id} from ObjectId {objectid} for tool '{tool.get('name')}'"
                )

                # Update the tool with the derived UUID to avoid future conversion
                try:
                    await tools.update_one({"_id": objectid}, {"$set": {"id": tool_id}})
                    logger.info(
                        f"Updated tool {tool.get('name')} with derived UUID {tool_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to update tool with derived UUID: {e}")
            else:
                # If both 'id' is empty/missing and '_id' is missing, generate a new UUID
                tool_id = str(uuid4())
                # No error log since we're handling this case now
                logger.info(
                    f"Tool has empty or missing 'id' and no '_id' field. Generated new ID: {tool_id}. Tool: {tool.get('name')}"
                )

        # Extract keywords if not already present and update in the background
        if not tool.get("keywords"):
            # Extract keywords
            keywords = extract_keywords(tool)

            # Update in background to avoid blocking the response
            if "_id" in tool:
                # Update the tool with keywords
                async def update_tool_task():
                    await tools.update_one(
                        {"_id": tool["_id"]},
                        {
                            "$set": {
                                "keywords": keywords,
                                "updated_at": datetime.utcnow(),
                            }
                        },
                    )

                asyncio.create_task(update_tool_task())

                # Update keywords collection in background
                async def update_keywords_task():
                    await update_tool_keywords(
                        str(tool["_id"]), tool.get("name", "Unknown"), keywords
                    )

                asyncio.create_task(update_keywords_task())

            # Add the keywords to the response
            tool["keywords"] = keywords

        # Ensure logo_url is a string
        logo_url = tool.get("logo_url")
        if logo_url is None:
            logo_url = ""

        return ToolResponse(
            id=tool_id,  # Use the determined ID (valid UUID string)
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
            keywords=tool.get("keywords", []),  # Include keywords in the response
            categories=tool.get("categories"),
            logo_url=logo_url,
            user_reviews=tool.get("user_reviews"),
            feature_list=tool.get("feature_list"),
            referral_allow=tool.get("referral_allow", False),
            generated_description=tool.get("generated_description"),
            industry=tool.get("industry"),
            image_url=tool.get("image_url"),
            carriers=tool.get("carriers"),
            task=tool.get("task"),
        )
    except Exception as e:
        logger.error(f"Error creating tool response: {str(e)}")
        return None


@redis_cache(prefix="tools_list")
async def get_tools(
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
    filters: Optional[Dict[str, Any]] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc",
    user_id: Optional[str] = None,
) -> Union[List[ToolResponse], int]:
    """
    Get a list of tools with pagination, filtering and sorting.

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return
        count_only: If True, return only the count of items
        filters: Dictionary of filters to apply
        sort_by: Field to sort by
        sort_order: Sort order ('asc' or 'desc')
        user_id: Optional user ID to check favorite status

    Returns:
        List of tools or count of tools
    """
    # Build the query
    query = {}

    # Apply filters if provided
    if filters:
        for field, value in filters.items():
            # Handle special filter cases
            if field == "category":
                # Look for category in both the "category" field and the "categories" array
                query["$or"] = [
                    {"category": value},  # Direct match on category field
                    {"categories.id": value},  # Match on categories.id in array
                ]
            elif field == "is_featured":
                # Correctly convert string values from query parameters to boolean
                if isinstance(value, str):
                    if value.lower() == "true":
                        query["is_featured"] = True
                    elif value.lower() == "false":
                        # When looking for non-featured tools, need to handle tools
                        # where the field doesn't exist (count as non-featured)
                        query["$or"] = [
                            {"is_featured": False},
                            {"is_featured": {"$exists": False}},
                        ]
                    else:
                        # If it's not a valid boolean string, use the value as-is
                        query["is_featured"] = value
                else:
                    # For boolean values
                    if value is False:
                        # Include both explicit False and missing field
                        query["$or"] = [
                            {"is_featured": False},
                            {"is_featured": {"$exists": False}},
                        ]
                    else:
                        query["is_featured"] = bool(value)

                # Log the value for debugging
                logger.info(
                    f"Applying is_featured filter with value: {value} (type: {type(value)}), query: {query}"
                )
            elif field == "price":
                query["price"] = value
            elif field == "features":
                if isinstance(value, list):
                    query["features"] = {"$all": value}
                else:
                    query["features"] = value
            else:
                # Default to exact match for other fields
                query[field] = value

    # Count documents if requested
    if count_only:
        return await tools.count_documents(query)

    # Create the cursor with efficient sorting in MongoDB
    # Use aggregation pipeline for more complex sorting logic
    pipeline = [{"$match": query}]

    # Add a stage to create a new field indicating if description is empty
    pipeline.append(
        {
            "$addFields": {
                "has_description": {
                    "$cond": [
                        {
                            "$or": [
                                {"$eq": ["$description", ""]},
                                {"$eq": ["$description", None]},
                            ]
                        },
                        0,  # description is empty or null
                        1,  # description has content
                    ]
                }
            }
        }
    )

    # Create a sort object that combines both sorts
    sort_obj = {"has_description": -1}  # Always prioritize tools with descriptions

    # Add the requested sort if provided
    if sort_by:
        sort_direction = -1 if sort_order.lower() == "desc" else 1
        sort_obj[sort_by] = sort_direction

    # Apply the combined sort in a single stage
    pipeline.append({"$sort": sort_obj})

    # Apply pagination after sorting
    pipeline.append({"$skip": skip})
    pipeline.append({"$limit": limit})

    # Log the pipeline for debugging
    logger.debug(f"MongoDB aggregation pipeline: {pipeline}")

    # Execute the aggregation pipeline
    cursor = tools.aggregate(pipeline)

    # Process results
    tools_list = []
    saved_tools_list = []

    # If user_id is provided, get the user's saved tools
    if user_id and not count_only:
        # Check if the user exists and has saved tools
        user = await database.users.find_one({"_id": ObjectId(user_id)})
        if user and "saved_tools" in user:
            # Convert all items to strings for consistent comparison
            saved_tools_list = [str(tool_id) for tool_id in user["saved_tools"]]
        else:
            # If user doesn't have saved_tools field, check favorites collection
            fav_cursor = favorites.find({"user_id": str(user_id)})
            saved_tools_list = []
            async for favorite in fav_cursor:
                saved_tools_list.append(str(favorite["tool_unique_id"]))

        # For debugging
        logger.info(f"User {user_id} has saved tools: {saved_tools_list}")

    async for tool in cursor:
        tool_response = await create_tool_response(tool)
        if tool_response:
            # Check if this tool is saved by the user
            if user_id and not count_only:
                unique_id = str(tool.get("unique_id", ""))
                tool_response.saved_by_user = unique_id in saved_tools_list
            tools_list.append(tool_response)

    # Convert to dict for proper serialization in cache
    if not count_only:
        return tools_list

    # return tools_list


@redis_cache(prefix="tool_by_id")
async def get_tool_by_id(
    tool_id: UUID, user_id: Optional[str] = None
) -> Optional[ToolResponse]:
    """
    Get a tool by its UUID.

    Args:
        tool_id: The UUID of the tool
        user_id: Optional user ID to check favorite status

    Returns:
        Tool object or None if not found
    """
    tool = await tools.find_one({"id": str(tool_id)})
    if not tool:
        return None

    tool_response = await create_tool_response(tool)

    # If user_id is provided, check if the tool is saved by the user
    if user_id and tool_response:
        # Check if user has saved_tools array
        user = await database.users.find_one({"_id": ObjectId(user_id)})
        if user and "saved_tools" in user:
            # Convert to strings for consistent comparison
            saved_tools = [str(t) for t in user["saved_tools"]]
            unique_id = str(tool.get("unique_id", ""))
            tool_response.saved_by_user = unique_id in saved_tools
            logger.info(
                f"Tool {unique_id} saved status for user {user_id}: {tool_response.saved_by_user}"
            )
        else:
            # Check favorites collection
            favorite = await favorites.find_one(
                {
                    "user_id": str(user_id),
                    "tool_unique_id": str(tool.get("unique_id", "")),
                }
            )
            tool_response.saved_by_user = favorite is not None
            logger.info(
                f"Tool saved status from favorites: {tool_response.saved_by_user}"
            )

    return tool_response


@redis_cache(prefix="tool_by_unique_id")
async def get_tool_by_unique_id(
    unique_id: str, user_id: Optional[str] = None
) -> Optional[ToolResponse]:
    """
    Get a tool by its unique_id.

    Args:
        unique_id: The unique_id of the tool
        user_id: Optional user ID to check favorite status

    Returns:
        Tool object or None if not found
    """
    tool = await tools.find_one({"unique_id": unique_id})
    if not tool:
        return None

    tool_response = await create_tool_response(tool)

    # If user_id is provided, check if the tool is saved by the user
    if user_id and tool_response:
        # Check if user has saved_tools array
        user = await database.users.find_one({"_id": ObjectId(user_id)})
        if user and "saved_tools" in user:
            # Convert to strings for consistent comparison
            saved_tools = [str(t) for t in user["saved_tools"]]
            unique_id_str = str(unique_id)
            tool_response.saved_by_user = unique_id_str in saved_tools
            logger.info(
                f"Tool {unique_id_str} saved status for user {user_id}: {tool_response.saved_by_user}"
            )
        else:
            # Check favorites collection
            favorite = await favorites.find_one(
                {"user_id": str(user_id), "tool_unique_id": str(unique_id)}
            )
            tool_response.saved_by_user = favorite is not None
            logger.info(
                f"Tool {unique_id} saved status from favorites: {tool_response.saved_by_user}"
            )

    return tool_response


async def create_tool(tool_data: ToolCreate) -> ToolResponse:
    """
    Create a new tool.

    Args:
        tool_data: The data for the tool to create

    Returns:
        The created tool
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

        # Extract keywords
        keywords = extract_keywords(tool_dict)
        tool_dict["keywords"] = keywords

        # Insert into MongoDB
        result = await tools.insert_one(tool_dict)

        # Update keywords collection in background
        async def update_keywords_task():
            await update_tool_keywords(
                str(result.inserted_id), tool_dict.get("name", "Unknown"), keywords
            )

        asyncio.create_task(update_keywords_task())

        # Return the created tool
        created_tool = await tools.find_one({"_id": result.inserted_id})

        # Index in Algolia
        await algolia_indexer.index_tool(created_tool)

        # Create and return the response
        tool_response = await create_tool_response(created_tool)
        if not tool_response:
            raise HTTPException(
                status_code=500, detail="Failed to create tool response"
            )

        # Invalidate cache after creating a new tool
        invalidate_cache("tools_list")

        return tool_response
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Tool creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create tool: {str(e)}")


async def update_tool(tool_id: UUID, tool_update: ToolUpdate) -> Optional[ToolResponse]:
    """
    Update a tool.

    Args:
        tool_id: The UUID of the tool to update
        tool_update: The data to update

    Returns:
        The updated tool or None if not found
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

        # Extract keywords if name, description, features or category changed
        keyword_fields = [
            "name",
            "description",
            "features",
            "category",
            "tags",
            "pricing_type",
        ]
        if any(field in update_data for field in keyword_fields):
            # Merge existing tool with updates for keyword extraction
            updated_tool = {**existing_tool, **update_data}
            keywords = extract_keywords(updated_tool)
            update_data["keywords"] = keywords

            # Update keywords collection in background after updating the tool
            tool_id_str = str(existing_tool.get("_id", tool_id))

            async def update_keywords_task():
                await update_tool_keywords(
                    tool_id_str, updated_tool.get("name", "Unknown"), keywords
                )

            asyncio.create_task(update_keywords_task())

        # Update the tool
        await tools.update_one({"id": str(tool_id)}, {"$set": update_data})

    # Return the updated tool
    updated_tool = await tools.find_one({"id": str(tool_id)})

    # Update in Algolia
    await algolia_indexer.index_tool(updated_tool)

    # Invalidate caches after updating a tool
    invalidate_cache("tools_list")
    invalidate_cache("tool_by_id")
    invalidate_cache("tool_by_unique_id")

    return await create_tool_response(updated_tool)


async def delete_tool(tool_id: UUID) -> bool:
    """
    Delete a tool.

    Args:
        tool_id: The UUID of the tool to delete

    Returns:
        True if deleted, False otherwise
    """
    # Check if the tool exists
    existing_tool = await tools.find_one({"id": str(tool_id)})
    if not existing_tool:
        return False

    # Delete from Algolia first
    await algolia_indexer.delete_tool(existing_tool.get("_id"))

    # Delete from MongoDB
    result = await tools.delete_one({"id": str(tool_id)})

    # Invalidate caches after deleting a tool
    invalidate_cache("tools_list")
    invalidate_cache("tool_by_id")
    invalidate_cache("tool_by_unique_id")

    return result.deleted_count > 0


# @redis_cache(prefix="search_tools")
async def search_tools(
    search_term: str,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
    additional_filters: Optional[Dict[str, Any]] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    user_id: Optional[str] = None,
) -> Union[Dict[str, Any], int]:
    """
    Search for tools by name or description.

    Args:
        search_term: The search query
        skip: Number of items to skip
        limit: Maximum number of items to return
        count_only: If True, return only the count of items
        additional_filters: Additional MongoDB filters to apply
        sort_by: Field to sort by
        sort_order: Sort order (asc or desc)
        user_id: Optional user ID to check favorite status

    Returns:
        Dictionary with tools list and total count, or just count if count_only is True
    """
    from ..algolia.config import algolia_config
    from ..algolia.search import algolia_search

    # Try using Algolia first if configured
    if algolia_config.is_configured():
        try:
            # Use the direct search function for more flexible name/description search
            search_result = await algolia_search.direct_search_tools(
                query=search_term,
                page=(skip // limit) if limit > 0 else 0,  # Convert skip/limit to page
                per_page=(
                    limit if not count_only else 1
                ),  # Only need one result if just countin
            )

            if count_only:
                return search_result.total

            # Get saved tools if user is provided
            saved_tools_list = []
            if user_id:
                # Check if the user exists and has saved tools
                user = await database.users.find_one({"_id": ObjectId(user_id)})
                if user and "saved_tools" in user:
                    # Convert all items to strings for consistent comparison
                    saved_tools_list = [str(tool_id) for tool_id in user["saved_tools"]]
                else:
                    # If user doesn't have saved_tools field, check favorites collection
                    fav_cursor = favorites.find({"user_id": str(user_id)})
                    async for favorite in fav_cursor:
                        saved_tools_list.append(str(favorite["tool_unique_id"]))

                # For debugging
                logger.info(
                    f"User {user_id} has saved tools (Algolia search): {saved_tools_list}"
                )

            # logger.info(f"Search result: {search_result.tools}")
            # Convert Algolia results to ToolResponse objects
            tools_list = []
            for tool in search_result.tools:
                # logger.info(f"Tool: {tool}")
                # Convert Algolia result to a dictionary format compatible with our helper
                tool_dict = {
                    "id": getattr(tool, "objectID", ""),
                    "price": getattr(tool, "price", ""),
                    "name": getattr(tool, "name", ""),
                    "description": getattr(tool, "description", ""),
                    "link": getattr(tool, "link", ""),
                    "unique_id": getattr(tool, "unique_id", ""),
                    "rating": getattr(tool, "rating", None),
                    "saved_numbers": getattr(tool, "saved_numbers", None),
                    "created_at": getattr(tool, "created_at", None),
                    "updated_at": getattr(tool, "updated_at", None),
                    "features": getattr(tool, "features", None),
                    "is_featured": getattr(tool, "is_featured", False),
                    "keywords": getattr(tool, "keywords", []),
                    "categories": getattr(tool, "categories", None),
                    "logo_url": getattr(tool, "logo_url", ""),
                    "user_reviews": getattr(tool, "user_reviews", None),
                    "feature_list": getattr(tool, "feature_list", []),
                    "referral_allow": getattr(tool, "referral_allow", False),
                    "generated_description": getattr(
                        tool, "generated_description", None
                    ),
                    "industry": getattr(tool, "industry", None),
                    "carriers": getattr(tool, "carriers", []),
                }
                logger.info(f"Tool dict: {tool_dict}")

                # Add categories if available
                if getattr(tool, "categories", None):
                    if (
                        isinstance(getattr(tool, "categories", None), list)
                        and len(getattr(tool, "categories", None)) > 0
                    ):
                        if isinstance(getattr(tool, "categories", None)[0], dict):
                            tool_dict["category"] = getattr(tool, "categories", None)[
                                0
                            ].get("id")
                        elif hasattr(getattr(tool, "categories", None)[0], "id"):
                            tool_dict["category"] = getattr(tool, "categories", None)[
                                0
                            ].id

                tool_response = await create_tool_response(tool_dict)
                if tool_response:
                    # Check if this tool is saved by the user
                    if user_id:
                        # Make sure both are strings for consistent comparison
                        tool_unique_id = str(getattr(tool, "unique_id", "") or "")
                        tool_response.saved_by_user = tool_unique_id in saved_tools_list
                        logger.info(
                            f"Tool {tool_unique_id} saved status (Algolia): {tool_response.saved_by_user}"
                        )
                    tools_list.append(tool_response)

            return {"tools": tools_list, "total": search_result.total}
        except Exception as e:
            # Log the error and fall back to MongoDB
            logger.error(
                f"Error searching with Algolia, falling back to MongoDB: {str(e)}"
            )

    # Fall back to MongoDB text search
    # Create the base query for text search
    query = {"$text": {"$search": search_term}}

    # Add additional filters if provided
    if additional_filters:
        query.update(additional_filters)

    if count_only:
        return await tools.count_documents(query)

    # Determine sort direction
    sort_direction = -1 if sort_order.lower() == "desc" else 1

    # Create cursor with sorting
    if sort_by:
        cursor = tools.find(query).skip(skip).limit(limit).sort(sort_by, sort_direction)
    else:
        cursor = tools.find(query).skip(skip).limit(limit)

    tools_list = []
    saved_tools_list = []

    # If user_id is provided, get the user's saved tools
    if user_id:
        # Check if the user exists and has saved tools
        user = await database.users.find_one({"_id": ObjectId(user_id)})
        if user and "saved_tools" in user:
            # Convert all items to strings for consistent comparison
            saved_tools_list = [str(tool_id) for tool_id in user["saved_tools"]]
        else:
            # If user doesn't have saved_tools field, check favorites collection
            fav_cursor = favorites.find({"user_id": str(user_id)})
            async for favorite in fav_cursor:
                saved_tools_list.append(str(favorite["tool_unique_id"]))

        # For debugging
        logger.info(
            f"User {user_id} has saved tools (MongoDB search): {saved_tools_list}"
        )

    async for tool in cursor:
        tool_response = await create_tool_response(tool)
        if tool_response:
            # Check if this tool is saved by the user
            if user_id:
                unique_id = str(tool.get("unique_id", ""))
                tool_response.saved_by_user = unique_id in saved_tools_list
                logger.info(
                    f"Tool {unique_id} saved status (MongoDB search): {tool_response.saved_by_user}"
                )
            tools_list.append(tool_response)

    # Get total count with the same query
    total = await tools.count_documents(query)

    return {"tools": tools_list, "total": total}


# @redis_cache(prefix="keyword_search")
async def keyword_search_tools(
    keywords: List[str],
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
    filters: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> Union[List[ToolResponse], int]:
    """
    Search for tools by keywords.

    Args:
        keywords: List of keywords to search for
        skip: Number of items to skip
        limit: Maximum number of items to return
        count_only: If True, return only the count of items
        filters: Dictionary of filters to apply
        user_id: Optional user ID to check favorite status

    Returns:
        List of tools or count of tools
    """
    # Initialize empty list for tools
    tools_list = []

    from ..algolia.config import algolia_config
    from ..algolia.search import algolia_search

    try:
        # Try using Algolia first if configured
        if algolia_config.is_configured():
            logger.info(f"Algolia is configured")
            try:
                # Convert skip/limit to page/per_page for Algolia
                page = skip // limit if limit > 0 else 0

                # Use the perform_keyword_search function
                search_result = await algolia_search.perform_keyword_search(
                    keywords=keywords,
                    page=page,
                    per_page=(
                        limit if not count_only else 1000
                    ),  # Get all results if counting
                )

                logger.info(f"Search result type: {type(search_result)}")

                # If only count is needed, return the total hits
                if count_only:
                    # Handle different result formats
                    if hasattr(search_result, "total"):
                        return search_result.total
                    elif hasattr(search_result, "nbHits"):
                        return search_result.nbHits
                    elif isinstance(search_result, dict):
                        return search_result.get("nbHits", 0)
                    else:
                        return 0

                # Get saved tools if user is provided
                saved_tools_list = []
                if user_id:
                    # Check if the user exists and has saved tools
                    user = await database.users.find_one({"_id": ObjectId(user_id)})
                    if user and "saved_tools" in user:
                        # Convert all items to strings for consistent comparison
                        saved_tools_list = [
                            str(tool_id) for tool_id in user["saved_tools"]
                        ]
                    else:
                        # If user doesn't have saved_tools field, check favorites collection
                        fav_cursor = favorites.find({"user_id": str(user_id)})
                        async for favorite in fav_cursor:
                            saved_tools_list.append(str(favorite["tool_unique_id"]))

                    # For debugging
                    logger.info(
                        f"User {user_id} has saved tools (Algolia keyword search): {saved_tools_list}"
                    )

                # Convert Algolia results to ToolResponse objects
                tools_list = []

                # Handle different result formats
                if hasattr(search_result, "tools") and search_result.tools:
                    # Handle SearchResult object
                    tools_to_process = search_result.tools
                    logger.info(
                        f"Processing SearchResult.tools: {len(tools_to_process)} items"
                    )
                elif hasattr(search_result, "hits") and search_result.hits:
                    # Handle Algolia response object
                    tools_to_process = search_result.hits
                    logger.info(
                        f"Processing search_result.hits: {len(tools_to_process)} items"
                    )
                elif isinstance(search_result, dict) and "hits" in search_result:
                    # Handle dictionary response
                    tools_to_process = search_result["hits"]
                    logger.info(
                        f"Processing search_result['hits']: {len(tools_to_process)} items"
                    )
                else:
                    # No results found
                    logger.warning("No search results found in Algolia response")
                    tools_to_process = []

                for tool in tools_to_process:
                    try:
                        logger.info(f"Processing tool: {tool}")

                        # Create a dictionary from the tool object, handling both object and dict formats
                        tool_dict = {}

                        # Helper function to safely get attribute from either object or dict
                        def get_attr(obj, attr, default=None):
                            if isinstance(obj, dict):
                                return obj.get(attr, default)
                            return getattr(obj, attr, default)

                        # Build the tool dictionary
                        tool_dict = {
                            "id": get_attr(tool, "objectID", ""),
                            "price": get_attr(tool, "price", ""),
                            "name": get_attr(tool, "name", ""),
                            "description": get_attr(tool, "description", ""),
                            "link": get_attr(tool, "link", ""),
                            "unique_id": get_attr(tool, "unique_id", ""),
                            "rating": get_attr(tool, "rating", None),
                            "saved_numbers": get_attr(tool, "saved_numbers", None),
                            "created_at": get_attr(tool, "created_at", None),
                            "updated_at": get_attr(tool, "updated_at", None),
                            "features": get_attr(tool, "features", None),
                            "is_featured": get_attr(tool, "is_featured", False),
                            "keywords": get_attr(tool, "keywords", []),
                            "categories": get_attr(tool, "categories", None),
                            "logo_url": get_attr(tool, "logo_url", ""),
                            "user_reviews": get_attr(tool, "user_reviews", None),
                            "feature_list": get_attr(tool, "feature_list", []),
                            "referral_allow": get_attr(tool, "referral_allow", False),
                            "generated_description": get_attr(
                                tool, "generated_description", None
                            ),
                            "industry": get_attr(tool, "industry", None),
                            "carriers": get_attr(tool, "carriers", []),
                        }

                        # Add category if available
                        categories = get_attr(tool, "categories", None)
                        if categories:
                            if isinstance(categories, list) and len(categories) > 0:
                                if isinstance(categories[0], dict):
                                    tool_dict["category"] = categories[0].get("id")
                                elif hasattr(categories[0], "id"):
                                    tool_dict["category"] = categories[0].id

                        # Create tool response
                        tool_response = await create_tool_response(tool_dict)
                        if tool_response:
                            # Check if this tool is saved by the user
                            if user_id:
                                unique_id = str(get_attr(tool, "unique_id", "") or "")
                                tool_response.saved_by_user = (
                                    unique_id in saved_tools_list
                                )

                            tools_list.append(tool_response)
                    except Exception as e:
                        logger.error(f"Error processing tool: {str(e)}")
                        continue

                logger.info(f"Final tools list length: {len(tools_list)}")
                return tools_list

            except Exception as e:
                # Log the error and fall back to MongoDB
                logger.error(
                    f"Error searching with Algolia, falling back to MongoDB: {str(e)}"
                )
                # Continue to MongoDB fallback
        else:
            logger.info(f"Algolia is not configured, falling back to MongoDB")

            # Fall back to MongoDB if Algolia is not configured or search fails
            # Create a query to find tools where any of the provided keywords match
            query = {
                "$or": [
                    {"carriers": {"$in": keywords}},
                    {"name": {"$regex": "|".join(keywords), "$options": "i"}},
                    {"description": {"$regex": "|".join(keywords), "$options": "i"}},
                    {"keywords": {"$in": keywords}},
                    {"category": {"$regex": "|".join(keywords), "$options": "i"}},
                    {
                        "generated_description": {
                            "$regex": "|".join(keywords),
                            "$options": "i",
                        }
                    },
                ]
            }

            # Apply additional filters if provided
            if filters and isinstance(filters, dict):
                for key, value in filters.items():
                    query[key] = value

            # If only count is needed, return the count
            if count_only:
                return await tools.count_documents(query)

            # Find matching tools with pagination
            cursor = tools.find(query).skip(skip).limit(limit)

            # Get saved tools if user is provided
            saved_tools_list = []
            if user_id:
                # Check if the user exists and has saved tools
                user = await database.users.find_one({"_id": ObjectId(user_id)})
                if user and "saved_tools" in user:
                    # Convert all items to strings for consistent comparison
                    saved_tools_list = [str(tool_id) for tool_id in user["saved_tools"]]
                else:
                    # If user doesn't have saved_tools field, check favorites collection
                    fav_cursor = favorites.find({"user_id": str(user_id)})
                    async for favorite in fav_cursor:
                        saved_tools_list.append(str(favorite["tool_unique_id"]))

            # Process results
            async for tool in cursor:
                tool_response = await create_tool_response(tool)
                if tool_response:
                    # Check if this tool is saved by the user
                    if user_id:
                        unique_id = str(tool.get("unique_id", ""))
                        tool_response.saved_by_user = unique_id in saved_tools_list
                    tools_list.append(tool_response)

    except Exception as e:
        # Log any errors but return an empty list instead of failing
        logger.error(f"Error in keyword_search_tools: {str(e)}")

    return tools_list


@redis_cache(prefix="tool_with_favorite")
async def get_tool_with_favorite_status(
    tool_unique_id: str, user_id: str
) -> Optional[ToolResponse]:
    """
    Get a tool with its favorite status for a specific user.

    Args:
        tool_unique_id: The unique_id of the tool
        user_id: The ID of the user

    Returns:
        Tool object with favorite status or None if not found
    """
    tool = await get_tool_by_unique_id(tool_unique_id)

    if not tool:
        return None

    # Check if tool is in user's favorites
    favorite = await favorites.find_one(
        {"user_id": str(user_id), "tool_unique_id": str(tool_unique_id)}
    )

    # Also check saved_tools array in user document
    user = await database.users.find_one({"_id": ObjectId(user_id)})
    saved_in_user = False
    if user and "saved_tools" in user:
        saved_tools = [str(t) for t in user["saved_tools"]]
        saved_in_user = str(tool_unique_id) in saved_tools

    # Log the findings for debugging
    logger.info(
        f"Tool {tool_unique_id} favorite status for user {user_id}: favorite={favorite is not None}, saved_in_user={saved_in_user}"
    )

    # Update the saved_by_user field
    tool.saved_by_user = favorite is not None or saved_in_user

    return tool


# @redis_cache(prefix="keywords")
async def get_keywords(
    skip: int = 0,
    limit: int = 100,
    min_frequency: int = 0,
    sort_by_frequency: bool = True,
) -> List[Dict[str, Any]]:
    """
    Get a list of keywords with their frequency.

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return
        min_frequency: Minimum frequency to include
        sort_by_frequency: Whether to sort by frequency

    Returns:
        List of keywords with their frequency
    """
    query = {}

    # # Apply minimum frequency filter if specified
    # if min_frequency > 0:
    #     query["frequency"] = {"$gte": min_frequency}

    # # Create cursor
    cursor = keywords_collection.find(query).skip(skip).limit(limit)

    # # Apply sorting if requested
    # if sort_by_frequency:
    #     cursor = cursor.sort("frequency", -1)  # Sort by frequency descending

    # Process results
    keywords_list = []
    async for keyword in cursor:
        # Check the field name - could be either 'keyword' or 'word' depending on
        # which function created it. The update_tool_keywords uses 'keyword',
        # while the get_tools function uses 'word'
        keyword_value = keyword.get("keyword") or keyword.get("word")

        keywords_list.append(keyword_value)

    return keywords_list


async def toggle_tool_featured_status(
    tool_id: UUID, is_featured: bool
) -> Optional[ToolResponse]:
    """
    Toggle the featured status of a tool.

    Args:
        tool_id: The UUID of the tool
        is_featured: Whether the tool should be featured

    Returns:
        The updated tool or None if not found
    """
    logger.info(f"Setting tool {tool_id} featured status to {is_featured}")

    # Update the tool in the database
    result = await tools.update_one(
        {"id": str(tool_id)},
        {"$set": {"is_featured": is_featured, "updated_at": datetime.utcnow()}},
    )

    if result.matched_count == 0:
        logger.warning(f"Tool {tool_id} not found for featured status update")
        return None

    # Get the updated tool
    updated_tool = await tools.find_one({"id": str(tool_id)})
    if not updated_tool:
        logger.error(f"Tool {tool_id} was updated but could not be retrieved")
        return None

    # Update the tool in Algolia
    try:
        if algolia_indexer.is_configured():
            # Create a dictionary with the tool data for Algolia
            algolia_data = {
                "objectID": str(updated_tool["id"]),
                "is_featured": is_featured,
            }
            # Update the record in Algolia
            await algolia_indexer.update_record(algolia_data)
            logger.info(f"Updated featured status in Algolia for tool {tool_id}")
    except Exception as e:
        # Log the error but don't fail the request
        logger.error(f"Failed to update Algolia index: {str(e)}")

    # Invalidate caches after toggling featured status
    invalidate_cache("tools_list")
    invalidate_cache("tool_by_id")

    # Return the updated tool as a ToolResponse
    return await create_tool_response(updated_tool)


async def toggle_tool_featured_status_by_unique_id(
    unique_id: str, is_featured: bool
) -> Optional[ToolResponse]:
    """
    Toggle the featured status of a tool by its unique_id.

    Args:
        unique_id: The unique_id of the tool
        is_featured: Whether the tool should be featured

    Returns:
        The updated tool or None if not found
    """
    logger.info(
        f"Setting tool with unique_id={unique_id} featured status to {is_featured}"
    )

    # Update the tool in the database
    result = await tools.update_one(
        {"unique_id": unique_id},
        {"$set": {"is_featured": is_featured, "updated_at": datetime.utcnow()}},
    )

    if result.matched_count == 0:
        logger.warning(
            f"Tool with unique_id={unique_id} not found for featured status update"
        )
        return None

    # Get the updated tool
    updated_tool = await tools.find_one({"unique_id": unique_id})
    if not updated_tool:
        logger.error(
            f"Tool with unique_id={unique_id} was updated but could not be retrieved"
        )
        return None

    # Update the tool in Algolia
    try:
        from ..algolia.config import algolia_config

        if algolia_config.is_configured():
            # Create a dictionary with the tool data for Algolia
            algolia_data = {
                "objectID": str(updated_tool["id"]),
                "is_featured": is_featured,
            }
            # Update the record in Algolia
            await algolia_indexer.update_record(algolia_data)
            logger.info(
                f"Updated featured status in Algolia for tool with unique_id={unique_id}"
            )
    except Exception as e:
        # Log the error but don't fail the request
        logger.error(f"Failed to update Algolia index: {str(e)}")

    # Invalidate caches after toggling featured status
    invalidate_cache("tools_list")
    invalidate_cache("tool_by_unique_id")

    # Return the updated tool as a ToolResponse
    return await create_tool_response(updated_tool)
