from fastapi import HTTPException
from uuid import UUID, uuid4, uuid5, NAMESPACE_OID
from datetime import datetime
import asyncio
from typing import List, Optional, Union, Dict, Any, Tuple
from bson import ObjectId
import re

from app.algolia.models import AlgoliaToolRecord

from ..database.database import tools, database, favorites, users
from .models import ToolCreate, ToolUpdate, ToolInDB, ToolResponse
from ..algolia.indexer import algolia_indexer
from ..categories.service import categories_service
from collections import Counter
from ..services.redis_cache import redis_cache, invalidate_cache, redis_client, REDIS_CACHE_ENABLED
from ..models.user import UserResponse
# from ..scraper.utils import format_price, get_palo_alto_data

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
            is_sponsored_public=tool.get("is_sponsored_public", False),
            is_sponsored_private=tool.get("is_sponsored_private", False),
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
    if filters:
        # To handle both string and list of strings for category
        if "category" in filters and isinstance(filters["category"], list):
            query["category"] = {"$in": filters["category"]}
            del filters["category"]
        query.update(filters)

    if count_only:
        return await tools.count_documents(query)

    # Determine sort direction
    sort_direction = -1 if sort_order.lower() == "desc" else 1

    # Create cursor with sorting
    cursor = tools.find(query).skip(skip).limit(limit).sort(sort_by, sort_direction)

    tools_list = []
    
    saved_tools_list = []

    # If user_id is provided, get the user's saved tools
    if user_id and not count_only:
        # Check if the user exists and has saved tools
        user = await users.find_one({"_id": ObjectId(user_id)})
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
        user = await users.find_one({"_id": ObjectId(user_id)})
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


async def get_tool_by_unique_id(
    unique_id: str, user_id: Optional[str] = None
) -> Optional[ToolResponse]:
    """
    Get a tool by its unique_id.

    Args:
        unique_id: The unique_id of the tool
        user_id: Optional user ID to check favorite status

    Returns:
        The tool response or None if not found
    """
    # Check for cached response first
    if REDIS_CACHE_ENABLED and redis_client:
        try:
            cache_key = f"tool_by_unique_id:{unique_id}"
            if user_id:
                cache_key += f":{user_id}"
            
            # The redis_client.get method is synchronous, don't use await
            cached_result = redis_client.get(cache_key)
            if cached_result:
                import json
                result_data = json.loads(cached_result)
                
                # Convert to ToolResponse
                tool_response = ToolResponse(**result_data)
                return tool_response
        except Exception as e:
            logger.error(f"Error retrieving cached tool by unique_id: {str(e)}")
    
    # If not cached, fetch from database
    tool = await tools.find_one({"unique_id": unique_id})
    if not tool:
        return None

    tool_response = await create_tool_response(tool)

    # If user_id is provided, check if the tool is saved by the user
    if user_id and tool_response:
        # Check if user has saved_tools array
        user = await users.find_one({"_id": ObjectId(user_id)})
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

    # Cache the result for future requests
    if REDIS_CACHE_ENABLED and redis_client and tool_response:
        try:
            import json
            cache_key = f"tool_by_unique_id:{unique_id}"
            if user_id:
                cache_key += f":{user_id}"
            
            # Cache for 1 hour (3600 seconds)
            # The redis_client.setex method is synchronous, don't use await
            redis_client.setex(
                cache_key, 
                3600, 
                json.dumps(tool_response.model_dump(), default=str)
            )
        except Exception as e:
            logger.error(f"Error caching tool by unique_id: {str(e)}")
    
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
    Search for tools by name or description using MongoDB only.

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
    from ..database.database import tools, users, favorites
    from bson import ObjectId
    from ..logger import logger
    
    # Split the search term into individual words
    search_terms = search_term.strip().split()
    if not search_terms:
        return {"tools": [], "total": 0} if not count_only else 0
    
    # Create a MongoDB $and query with multiple parts to improve relevance
    search_parts = []
    
    # For multi-word queries, ensure ALL words must appear in the document (AND logic)
    # This prevents irrelevant results when nonsensical terms are mixed with real terms
    if len(search_terms) > 1:
        # Create text match conditions for each term
        text_match_conditions = []
        for term in search_terms:
            escaped_term = re.escape(term.lower())
            # Each term must appear in either name, description, or keywords
            term_condition = {
                "$or": [
                    {"name": {"$regex": escaped_term, "$options": "i"}},
                    {"description": {"$regex": escaped_term, "$options": "i"}},
                    {"keywords": {"$in": [term.lower()]}}
                ]
            }
            text_match_conditions.append(term_condition)
        
        # All terms must match (AND logic)
        search_parts.append({"$and": text_match_conditions})
    else:
        # Single word query
        single_term = search_terms[0]
        
        # For very short terms (1-2 characters), use only regex matching
        # since MongoDB text search ignores short words
        if len(single_term) <= 2:
            escape_regex = re.escape(single_term)
            name_regex = {"name": {"$regex": escape_regex, "$options": "i"}}
            desc_regex = {"description": {"$regex": escape_regex, "$options": "i"}}
            keyword_match = {"keywords": {"$in": [single_term.lower()]}}
            
            # For short terms, use regex matching only
            search_parts.append({
                "$or": [
                    name_regex,
                    desc_regex,
                    keyword_match
                ]
            })
        else:
            # For longer terms, use text index for better performance
            search_parts.append({"$text": {"$search": single_term}})
            
            # Add regex matches for name and description fields for better matching
            escape_regex = re.escape(single_term)
            name_regex = {"name": {"$regex": escape_regex, "$options": "i"}}
            desc_regex = {"description": {"$regex": escape_regex, "$options": "i"}}
            keyword_match = {"keywords": {"$in": [single_term.lower()]}}
            
            # Add regex conditions as a boost but not a requirement
            search_parts.append({
                "$or": [
                    name_regex,
                    desc_regex,
                    keyword_match
                ]
            })
    
    # Add additional filters if provided
    if additional_filters:
        if "$or" in additional_filters:
            # Add category filter directly to the search parts
            search_parts.append({"$or": additional_filters["$or"]})
            
            # Add any other filters
            for k, v in additional_filters.items():
                if k != "$or":
                    search_parts.append({k: v})
        else:
            # Add all additional filters
            for k, v in additional_filters.items():
                search_parts.append({k: v})
    
    # Construct the final query
    query = {"$and": search_parts}
    
    # Add a score field to rank results by relevance
    # This gives higher weight to exact name matches
    score_query = {
        "$addFields": {
            "search_score": {
                "$sum": [
                    # Highest score for exact name match
                    {"$cond": [{"$eq": [{"$toLower": "$name"}, search_term.lower()]}, 100, 0]},
                    # High score for name containing all search terms
                    {"$cond": [
                        {"$regexMatch": {"input": {"$toLower": "$name"}, "regex": re.escape(search_term.lower()), "options": "i"}}, 
                        50, 
                        0
                    ]},
                    # Medium score for description containing all search terms
                    {"$cond": [
                        {"$regexMatch": {"input": {"$toLower": "$description"}, "regex": re.escape(search_term.lower()), "options": "i"}}, 
                        25, 
                        0
                    ]},
                    # Score based on how many terms match in keywords
                    {"$multiply": [
                        {"$size": {
                            "$setIntersection": [
                                {"$ifNull": [{"$map": {"input": "$keywords", "in": {"$toLower": "$$this"}}}, []]},
                                search_terms
                            ]
                        }},
                        5  # 5 points per matched keyword
                    ]}
                ]
            }
        }
    }

    if count_only:
        return await tools.count_documents(query)

    # Determine sort direction
    sort_direction = -1 if sort_order.lower() == "desc" else 1

    # Use aggregation pipeline for better search results
    pipeline = [
        {"$match": query},
        score_query,
        {"$sort": {"search_score": -1, sort_by: sort_direction}},
        {"$skip": skip},
        {"$limit": limit}
    ]
    
    cursor = tools.aggregate(pipeline)
    
    tools_list = []
    saved_tools_list = []

    # If user_id is provided, get the user's saved tools
    if user_id:
        user = await users.find_one({"_id": ObjectId(user_id)})
        if user and "saved_tools" in user:
            saved_tools_list = [str(tool_id) for tool_id in user["saved_tools"]]
        else:
            fav_cursor = favorites.find({"user_id": str(user_id)})
            async for favorite in fav_cursor:
                saved_tools_list.append(str(favorite["tool_unique_id"]))

        # For debugging
        logger.info(
            f"User {user_id} has saved tools (MongoDB search): {saved_tools_list}"
        )

    # For multi-term queries, check if all terms are in the document before including
    multi_term_query = len(search_terms) > 1
    
    async for tool in cursor:
        # For multi-term queries with nonsense terms, double-check that all terms are present
        if multi_term_query:
            # Convert name, description, and keywords to lowercase for case-insensitive matching
            tool_text = (tool.get("name", "").lower() + " " + 
                        tool.get("description", "").lower())
            
            # Add keywords if they exist
            if tool.get("keywords"):
                for kw in tool.get("keywords", []):
                    if isinstance(kw, str):
                        tool_text += " " + kw.lower()
            
            # Check if all search terms are in the document
            all_terms_present = all(term.lower() in tool_text for term in search_terms)
            
            # Skip this result if not all terms are present
            if not all_terms_present:
                continue
        
        tool_response = await create_tool_response(tool)
        if tool_response:
            if user_id:
                unique_id = str(tool.get("unique_id", ""))
                tool_response.saved_by_user = unique_id in saved_tools_list
            tools_list.append(tool_response)

    # For count, we need to recount based on our additional filtering
    if multi_term_query:
        total = len(tools_list)
    else:
        # For single-term queries, use the MongoDB count
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
                    user = await users.find_one({"_id": ObjectId(user_id)})
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
                user = await users.find_one({"_id": ObjectId(user_id)})
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


async def get_tool_with_favorite_status(
    tool_unique_id: str, user_id: str
) -> Tuple[Optional[ToolResponse], bool]:
    """
    Get a tool by its unique_id with favorite status for a specific user.

    Args:
        tool_unique_id: The unique_id of the tool
        user_id: User ID to check favorite status

    Returns:
        Tuple of (tool_response, is_favorite)
    """
    # Get the tool
    tool = await get_tool_by_unique_id(tool_unique_id)
    if not tool:
        return None, False

    # Check if it's a favorite
    favorite = await favorites.find_one(
        {"user_id": str(user_id), "tool_unique_id": str(tool_unique_id)}
    )
    is_favorite = favorite is not None

    return tool, is_favorite


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
    try:
        if not unique_id:
            logger.error("Cannot toggle featured status: unique_id is empty or None")
            return None
            
        logger.info(f"Setting tool with unique_id '{unique_id}' featured status to {is_featured}")
        
        # Try to find the tool using multiple approaches
        tool = None
        
        # 1. First try exact match on unique_id
        logger.info(f"Searching for tool with exact unique_id: '{unique_id}'")
        tool = await tools.find_one({"unique_id": unique_id})
        
        # 2. If not found, try case-insensitive match
        if not tool:
            logger.info(f"Tool not found with exact unique_id, trying case-insensitive search")
            try:
                tool = await tools.find_one({"unique_id": {"$regex": f"^{unique_id}$", "$options": "i"}})
            except Exception as e:
                logger.warning(f"Case-insensitive search failed: {e}")
        
        # 3. If still not found, try by partial match
        if not tool:
            logger.info(f"Tool not found with case-insensitive search, trying partial match")
            try:
                tool = await tools.find_one({"unique_id": {"$regex": f".*{unique_id}.*", "$options": "i"}})
            except Exception as e:
                logger.warning(f"Partial match search failed: {e}")
                
        # 4. Try to find by name if it looks like a tool name rather than an ID
        if not tool and len(unique_id) > 10 and " " in unique_id:
            logger.info(f"Trying to find tool by name: '{unique_id}'")
            try:
                tool = await tools.find_one({"name": {"$regex": f".*{unique_id}.*", "$options": "i"}})
            except Exception as e:
                logger.warning(f"Name search failed: {e}")
        
        # Final check - if tool is still not found
        if not tool:
            logger.warning(f"Tool with unique_id '{unique_id}' not found using any search method")
            # Dump some database statistics to help diagnose the issue
            try:
                count = await tools.count_documents({})
                logger.info(f"Total tools in database: {count}")
                
                # Sample a few tools to check if database connection is working
                sample = await tools.find().limit(3).to_list(length=3)
                if sample:
                    logger.info(f"Sample tool names: {[t.get('name', 'unnamed') for t in sample]}")
                    logger.info(f"Sample tool unique_ids: {[t.get('unique_id', 'no-id') for t in sample]}")
                else:
                    logger.warning("No tools found in database sample")
            except Exception as e:
                logger.error(f"Error accessing database: {e}")
                
            return None
            
        # Log the found tool details
        logger.info(f"Found tool: '{tool.get('name')}' (ID: {tool.get('_id')}, unique_id: {tool.get('unique_id')})")

        # Verify the tool has an _id field
        if not tool.get("_id"):
            logger.error(f"Tool found but has no _id field: {tool}")
            return None

        # Update the is_featured field
        try:
            update_result = await tools.update_one(
                {"_id": tool["_id"]},
                {"$set": {"is_featured": is_featured, "updated_at": datetime.utcnow()}},
            )
            
            logger.info(f"Update result: matched={update_result.matched_count}, modified={update_result.modified_count}")
            
            if update_result.matched_count == 0:
                logger.error(f"Failed to update tool with _id {tool['_id']}, no document matched")
                return None
        except Exception as e:
            logger.error(f"Database update error: {e}")
            return None

        # Get the updated tool
        try:
            updated_tool = await tools.find_one({"_id": tool["_id"]})
            if not updated_tool:
                logger.error(f"Tool with _id {tool['_id']} was updated but could not be retrieved")
                return None
                
            logger.info(f"Successfully retrieved updated tool: {updated_tool.get('name')}")
        except Exception as e:
            logger.error(f"Error retrieving updated tool: {e}")
            return None

        # Invalidate cache
        try:
            invalidate_cache_tasks = [
                invalidate_cache(f"tool_by_unique_id:{unique_id}"),
                invalidate_cache("tools_list")
            ]
            
            # Run all invalidation tasks
            for task in invalidate_cache_tasks:
                await task
                
            logger.info("Cache invalidation completed")
        except Exception as e:
            logger.warning(f"Cache invalidation error (non-critical): {e}")

        # Convert to response model
        try:
            tool_response = await create_tool_response(updated_tool)
            if not tool_response:
                logger.error("Failed to create tool response from updated tool")
                return None
                
            logger.info(f"Successfully updated tool '{updated_tool.get('name')}' featured status to {is_featured}")
            return tool_response
        except Exception as e:
            logger.error(f"Error creating tool response: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error toggling tool featured status by unique_id: {e}")
        # Include traceback for easier debugging
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


async def toggle_tool_sponsored_private_status(
    unique_id: str, is_sponsored_private: bool
) -> Optional[ToolResponse]:
    """
    Toggle the private sponsored status of a tool by its unique_id.

    Args:
        unique_id: The unique_id of the tool
        is_sponsored_private: Whether the tool should be privately sponsored

    Returns:
        Updated tool or None if not found
    """
    try:
        if not unique_id:
            logger.error("Cannot toggle sponsored status: unique_id is empty or None")
            return None
            
        logger.info(f"Setting tool with unique_id '{unique_id}' private sponsored status to {is_sponsored_private}")
        
        # Try to find the tool using multiple approaches
        tool = None
        
        # 1. First try exact match on unique_id
        logger.info(f"Searching for tool with exact unique_id: '{unique_id}'")
        tool = await tools.find_one({"unique_id": unique_id})
        
        # 2. If not found, try case-insensitive match
        if not tool:
            logger.info(f"Tool not found with exact unique_id, trying case-insensitive search")
            try:
                tool = await tools.find_one({"unique_id": {"$regex": f"^{unique_id}$", "$options": "i"}})
            except Exception as e:
                logger.warning(f"Case-insensitive search failed: {e}")
        
        # 3. If still not found, try by partial match
        if not tool:
            logger.info(f"Tool not found with case-insensitive search, trying partial match")
            try:
                tool = await tools.find_one({"unique_id": {"$regex": f".*{unique_id}.*", "$options": "i"}})
            except Exception as e:
                logger.warning(f"Partial match search failed: {e}")
                
        # 4. Try to find by name if it looks like a tool name rather than an ID
        if not tool and len(unique_id) > 10 and " " in unique_id:
            logger.info(f"Trying to find tool by name: '{unique_id}'")
            try:
                tool = await tools.find_one({"name": {"$regex": f".*{unique_id}.*", "$options": "i"}})
            except Exception as e:
                logger.warning(f"Name search failed: {e}")
        
        # Final check - if tool is still not found
        if not tool:
            logger.warning(f"Tool with unique_id '{unique_id}' not found using any search method")
            # Dump some database statistics to help diagnose the issue
            try:
                count = await tools.count_documents({})
                logger.info(f"Total tools in database: {count}")
                
                # Sample a few tools to check if database connection is working
                sample = await tools.find().limit(3).to_list(length=3)
                if sample:
                    logger.info(f"Sample tool names: {[t.get('name', 'unnamed') for t in sample]}")
                    logger.info(f"Sample tool unique_ids: {[t.get('unique_id', 'no-id') for t in sample]}")
                else:
                    logger.warning("No tools found in database sample")
            except Exception as e:
                logger.error(f"Error accessing database: {e}")
                
            return None
            
        # Log the found tool details
        logger.info(f"Found tool: '{tool.get('name')}' (ID: {tool.get('_id')}, unique_id: {tool.get('unique_id')})")

        # Verify the tool has an _id field
        if not tool.get("_id"):
            logger.error(f"Tool found but has no _id field: {tool}")
            return None

        # Update the is_sponsored_private field
        try:
            update_result = await tools.update_one(
                {"_id": tool["_id"]},
                {"$set": {"is_sponsored_private": is_sponsored_private, "updated_at": datetime.utcnow()}},
            )
            
            logger.info(f"Update result: matched={update_result.matched_count}, modified={update_result.modified_count}")
            
            if update_result.matched_count == 0:
                logger.error(f"Failed to update tool with _id {tool['_id']}, no document matched")
                return None
        except Exception as e:
            logger.error(f"Database update error: {e}")
            return None

        # Get the updated tool
        try:
            updated_tool = await tools.find_one({"_id": tool["_id"]})
            if not updated_tool:
                logger.error(f"Tool with _id {tool['_id']} was updated but could not be retrieved")
                return None
                
            logger.info(f"Successfully retrieved updated tool: {updated_tool.get('name')}")
        except Exception as e:
            logger.error(f"Error retrieving updated tool: {e}")
            return None

        # Invalidate cache
        try:
            invalidate_cache_tasks = [
                invalidate_cache(f"tool_by_unique_id:{unique_id}"),
                invalidate_cache("tools_list")
            ]
            
            # Run all invalidation tasks
            for task in invalidate_cache_tasks:
                await task
                
            logger.info("Cache invalidation completed")
        except Exception as e:
            logger.warning(f"Cache invalidation error (non-critical): {e}")

        # Convert to response model
        try:
            tool_response = await create_tool_response(updated_tool)
            if not tool_response:
                logger.error("Failed to create tool response from updated tool")
                return None
                
            logger.info(f"Successfully updated tool '{updated_tool.get('name')}' sponsored private status to {is_sponsored_private}")
            return tool_response
        except Exception as e:
            logger.error(f"Error creating tool response: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error toggling tool private sponsored status by unique_id: {e}")
        # Include traceback for easier debugging
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


async def ensure_search_indexes():
    """
    Ensure all necessary search indexes exist in the tools collection.
    This should be called during application startup.
    """
    try:
        from ..database.database import tools
        from ..logger import logger
        
        # Create text index on name, description, and keywords fields with weights
        await tools.create_index(
            [
                ("name", "text"),
                ("description", "text"),
                ("keywords", "text")
            ],
            weights={
                "name": 10,  # Name matches are most important
                "keywords": 5,  # Keyword matches are next
                "description": 3,  # Description matches less important
            },
            name="tools_text_search_index",
            default_language="english",
            background=True
        )
        
        # Create regular indexes for commonly searched/filtered fields
        await tools.create_index("name", background=True)
        await tools.create_index("keywords", background=True)
        await tools.create_index("description", background=True)
        await tools.create_index("categories.id", background=True)
        await tools.create_index("category", background=True)
        await tools.create_index("price", background=True)
        await tools.create_index("is_featured", background=True)
        await tools.create_index("created_at", background=True)
        await tools.create_index("updated_at", background=True)
        
        logger.info("Search indexes created or updated successfully")
    except Exception as e:
        logger.error(f"Error creating search indexes: {str(e)}")
