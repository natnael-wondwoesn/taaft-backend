from fastapi import HTTPException
from uuid import UUID, uuid4, uuid5, NAMESPACE_OID
from datetime import datetime
import asyncio
from typing import List, Optional, Union, Dict, Any

from ..database.database import tools, database
from .models import ToolCreate, ToolUpdate, ToolInDB, ToolResponse
from ..algolia.indexer import algolia_indexer
from ..categories.service import categories_service
from collections import Counter

from ..logger import logger

# Keywords collection
keywords_collection = database.get_collection("keywords")


def objectid_to_uuid(objectid_str: str) -> UUID:
    """
    Converts an ObjectId string to a deterministic UUID.
    Uses UUID v5 with the ObjectId as the name and NAMESPACE_OID as namespace.
    """
    try:
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

        # If 'id' is missing, use a UUID derived from '_id'
        if not tool_id and "_id" in tool:
            objectid_str = str(tool.get("_id"))
            # Convert ObjectId string to a UUID
            derived_uuid = objectid_to_uuid(objectid_str)
            tool_id = str(derived_uuid)
            # Optionally log that we're deriving a UUID from _id
            logger.info(
                f"Derived UUID {tool_id} from ObjectId {objectid_str} for tool '{tool.get('name')}'"
            )

        # If both 'id' and '_id' are missing, generate a new UUID (should ideally not happen)
        elif not tool_id:
            tool_id = str(uuid4())
            logger.error(
                f"Tool missing both 'id' and '_id' fields. Generated new ID: {tool_id}. Tool data: {tool}"
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
        )
    except Exception as e:
        logger.error(f"Error creating tool response: {str(e)}")
        return None


async def get_tools(
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
    filters: Optional[Dict[str, Any]] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc",
) -> Union[List[ToolResponse], int]:
    """
    Retrieve a list of tools with pagination, filtering and sorting.

    Args:
        skip: Number of items to skip for pagination
        limit: Maximum number of items to return
        count_only: If True, returns only the count of tools
        filters: Dictionary of field-value pairs for filtering
        sort_by: Field to sort by
        sort_order: Sort order ('asc' or 'desc')

    Returns:
        Either a list of tools or the total count
    """
    # Build the query
    query = {}

    # Apply filters if provided
    if filters:
        for field, value in filters.items():
            # Handle special filter cases
            if field == "category":
                query["category"] = value
            elif field == "is_featured":
                query["is_featured"] = bool(value)
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

    # Create the cursor
    cursor = tools.find(query).skip(skip).limit(limit)

    # Apply sorting if requested
    if sort_by:
        # Apply ascending sort first
        cursor = cursor.sort(sort_by, 1)

    # Process results
    tools_list = []
    async for tool in cursor:
        # Extract keywords
        keywords = tool.get("keywords", [])
        if keywords:
            for keyword in keywords:
                try:
                    # Use update_one with upsert=True instead of insert_one
                    await keywords_collection.update_one(
                        {"word": keyword},
                        {
                            "$set": {"updated_at": datetime.utcnow()},
                            "$setOnInsert": {"created_at": datetime.utcnow()},
                            "$inc": {"frequency": 1},
                        },
                        upsert=True,
                    )
                except Exception as e:
                    # Just log the error and continue, don't let it break the flow
                    logger.warning(f"Error updating keyword '{keyword}': {str(e)}")

        tool_response = await create_tool_response(tool)

        if tool_response:
            tools_list.append(tool_response)

    # Simply reverse the list for descending order
    if sort_order.lower() == "desc":
        tools_list.reverse()

    return tools_list.reverse()


async def get_tool_by_id(tool_id: UUID) -> Optional[ToolResponse]:
    """
    Retrieve a tool by its UUID.

    First tries to find a document where id=tool_id.
    If that fails, checks if the tool_id might be a UUID derived from an ObjectId,
    and attempts to find the document by its _id.
    """
    # First try: Query by string representation of UUID in 'id' field
    tool = await tools.find_one({"id": str(tool_id)})

    if tool:
        return await create_tool_response(tool)

    # Second try: Check if this could be a UUID derived from an ObjectId
    # We'll try to find all tools and check if any have a derived UUID matching the requested one
    all_tools = await tools.find({}).to_list(length=None)

    for db_tool in all_tools:
        if "_id" in db_tool:
            object_id_str = str(db_tool.get("_id"))
            derived_uuid = objectid_to_uuid(object_id_str)

            # If the derived UUID matches the requested one, we found our tool
            if str(derived_uuid) == str(tool_id):
                logger.info(
                    f"Found tool via derived UUID: {tool_id} from ObjectId: {object_id_str}"
                )
                return await create_tool_response(db_tool)

    # If we get here, the tool wasn't found by either method
    return None


async def get_tool_by_unique_id(unique_id: str) -> Optional[ToolResponse]:
    """
    Retrieve a tool by its unique_id.
    """
    tool = await tools.find_one({"unique_id": unique_id})

    if not tool:
        return None

    return await create_tool_response(tool)


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
        return tool_response
    except Exception as e:
        # Log the error for debugging

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

    # Create and return the response
    return await create_tool_response(updated_tool)


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

                tool_response = await create_tool_response(tool_dict)
                if tool_response:
                    tools_list.append(tool_response)
            return tools_list
        except Exception as e:
            # Log the error and fall back to MongoDB

            logger.error(
                f"Error searching with Algolia, falling back to MongoDB: {str(e)}"
            )

    # Fall back to MongoDB text search
    if count_only:
        return await tools.count_documents({"$text": {"$search": query}})

    cursor = tools.find({"$text": {"$search": query}}).skip(skip).limit(limit)

    tools_list = []
    async for tool in cursor:
        tool_response = await create_tool_response(tool)
        if tool_response:
            tools_list.append(tool_response)

    return tools_list


async def get_keywords(
    skip: int = 0,
    limit: int = 100,
    min_frequency: int = 0,
    sort_by_frequency: bool = True,
) -> List[Dict[str, Any]]:
    """
    Retrieve keywords from the keywords collection.

    Args:
        skip: Number of items to skip for pagination
        limit: Maximum number of items to return
        min_frequency: Minimum frequency threshold for keywords
        sort_by_frequency: Whether to sort by frequency (descending)

    Returns:
        List of keyword documents with their associated tools and frequency
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
        is_featured: Boolean indicating whether the tool should be featured

    Returns:
        Updated tool response or None if tool not found
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

    # Return the updated tool as a ToolResponse
    return await create_tool_response(updated_tool)


async def toggle_tool_featured_status_by_unique_id(
    unique_id: str, is_featured: bool
) -> Optional[ToolResponse]:
    """
    Toggle the featured status of a tool by its unique_id.

    Args:
        unique_id: The unique_id of the tool
        is_featured: Boolean indicating whether the tool should be featured

    Returns:
        Updated tool response or None if tool not found
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

    # Return the updated tool as a ToolResponse
    return await create_tool_response(updated_tool)
