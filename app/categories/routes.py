# app/categories/routes.py
"""
API routes for categories management
"""
from fastapi import APIRouter, HTTPException, Query, status, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import re
from pathlib import Path

from .models import CategoryResponse
from .service import categories_service
from ..tools.models import PaginatedToolsResponse

# Remove the direct import to avoid circular dependencies
# from ..tools.tools_service import get_tools, search_tools
from ..logger import logger
from ..services.redis_cache import invalidate_cache, redis_cache
from ..auth.dependencies import get_admin_user, get_current_active_user
from ..models.user import UserResponse, UserInDB
from ..database.database import tools as tools_collection

router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
    responses={404: {"description": "Not found"}},
)

# Public router without authentication
public_router = APIRouter(
    prefix="/public/categories",
    tags=["public_categories"],
    responses={404: {"description": "Not found"}},
)


async def fix_null_category() -> Dict[str, Any]:
    """
    Check if a category called "null" exists and changes it to "Others".
    
    Returns:
        Dictionary with operation results
    """
    result = {
        "success": True,
        "null_category_found": False,
        "null_category_updated": False
    }
    
    try:
        # Get categories collection
        categories_collection = await categories_service._get_categories_collection()
        
        # Look for a category with id or name "null"
        null_category = await categories_collection.find_one({
            "$or": [
                {"id": "null"},
                {"name": "null"}
            ]
        })
        
        if null_category:
            result["null_category_found"] = True
            logger.info("Found 'null' category, updating to 'Others'")
            
            # Update the category name and id to "Others"
            await categories_collection.update_one(
                {"_id": null_category["_id"]},
                {"$set": {
                    "name": "Others",
                    "id": "others",
                    "slug": "others"
                }}
            )
            result["null_category_updated"] = True
            logger.info("Successfully updated 'null' category to 'Others'")
        else:
            logger.info("No 'null' category found in the database")
            
        return result
    
    except Exception as e:
        logger.error(f"Error fixing null category: {str(e)}")
        result["success"] = False
        result["error"] = str(e)
        return result


async def update_category_counts() -> Dict[str, Any]:
    """
    Update the counts for all categories in the database using the accurate counting method.
    
    Returns:
        Dictionary with operation results
    """
    result = {
        "success": True,
        "total_categories": 0,
        "categories_updated": 0,
        "categories_with_errors": 0,
    }
    
    try:
        # Get categories collection
        categories_collection = await categories_service._get_categories_collection()
        
        # Get all categories
        categories = await categories_collection.find({}).to_list(length=None)
        result["total_categories"] = len(categories)
        
        # Update count for each category
        for category in categories:
            category_id = category.get("id")
            category_name = category.get("name")
            
            if not category_id or not category_name:
                logger.warning(f"Skipping category with missing id or name: {category}")
                result["categories_with_errors"] += 1
                continue
            
            # Use aggregation pipeline to get accurate count of unique tools
            pipeline = [
                {
                    "$match": {
                        "$or": [
                            {"categories.id": category_id},  # Array-based categories
                            {"category": category_name}      # String-based category
                        ]
                    }
                },
                # Group by tool ID to ensure uniqueness
                {
                    "$group": {
                        "_id": "$_id"  # Group by MongoDB ObjectID
                    }
                },
                # Count the results
                {
                    "$count": "count"
                }
            ]
            
            # Execute the aggregation
            count_results = await tools_collection.aggregate(pipeline).to_list(length=1)
            accurate_count = count_results[0]["count"] if count_results else 0
            
            # Only update if count has changed
            if category.get("count") != accurate_count:
                old_count = category.get("count", 0)
                logger.info(f"Updating category '{category_name}' count: {old_count} → {accurate_count}")
                
                # Update the count in the database
                await categories_collection.update_one(
                    {"id": category_id},
                    {"$set": {"count": accurate_count}}
                )
                
                result["categories_updated"] += 1
            else:
                logger.info(f"Category '{category_name}' count unchanged: {category.get('count')}")
                
        return result
    
    except Exception as e:
        logger.error(f"Error updating category counts: {str(e)}")
        result["success"] = False
        result["error"] = str(e)
        return result


@public_router.post("/recalculate", response_model=Dict[str, Any])
async def recalculate_category_counts():
    """
    Recalculate the count of tools for each category using optimized method.
    This endpoint resets all category counts to 0 and then rebuilds them by iterating through tools.
    This endpoint is publicly accessible without authentication.

    Returns:
        Dictionary with success status and summary of updated categories
    """
    try:
        # Import the optimized recalculation function
        from ..scripts.recalculate_categories import recalculate_categories_optimized
        
        logger.info("Starting optimized category recalculation...")
        result = await recalculate_categories_optimized()
        
        # Enhance the result with additional info
        enhanced_result = {
            "success": result.get("success", False),
            "timestamp": str(datetime.now()),
            "categories_reset": result.get("categories_reset", 0),
            "tools_processed": result.get("tools_processed", 0),
            "categories_updated": result.get("categories_updated", 0),
            "categories_created": result.get("categories_created", 0),
            "errors": result.get("errors", 0),
            "duration_seconds": result.get("duration_seconds", 0),
            "message": "Category counts recalculated successfully" if result.get("success") else "Recalculation failed"
        }
        
        if not result.get("success"):
            enhanced_result["error"] = result.get("error", "Unknown error")

        # Invalidate any category-related caches
        invalidate_cache("category_tools")

        return enhanced_result
    
    except Exception as e:
        logger.error(f"Error recalculating category counts: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to recalculate category counts: {str(e)}"
        )


@router.get("/", response_model=List[CategoryResponse])
async def get_categories():
    """
    Get all available categories for tools

    Returns:
        List of category objects with id, name, slug, and count
    """
    categories = await categories_service.get_all_categories()
    return categories


@router.get("/mock-test",response_model=List[CategoryResponse])
async def mock_categories_test():
    """
    Get all available categories for tools

    Returns:
        List of category objects with id, name, slug, and count
    """
    categories = await categories_service.get_all_categories()
    return categories

@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category_by_id(category_id: str):
    """
    Get a category by its ID

    Args:
        category_id: ID of the category to fetch

    Returns:
        Category object with id, name, slug, and count
    """
    category = await categories_service.get_category_by_id(category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID {category_id} not found",
        )
    return category


@router.get("/slug/{slug}", response_model=CategoryResponse)
async def get_category_by_slug(slug: str):
    """
    Get a category by its slug

    Args:
        slug: Slug of the category to fetch

    Returns:
        Category object with id, name, slug, and count
    """
    category = await categories_service.get_category_by_slug(slug)
    if not category:
        # Try by name if not found by slug
        category = await categories_service.get_category_by_name(slug)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with slug or name '{slug}' not found",
        )
    return category


@router.get("/slug/{slug}/tools", response_model=PaginatedToolsResponse)
async def get_tools_by_category_slug(
    slug: str,
    search: Optional[str] = Query(None, description="Search term for filtering tools"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(
        20, ge=1, le=2000, description="Maximum number of items to return"
    ),
    sort_by: Optional[str] = Query(
        "created_at",
        description="Field to sort by (name, created_at, updated_at, price)",
    ),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    price_type: Optional[str] = Query(None, description="Filter by price type"),
    is_featured: Optional[bool] = Query(None, description="Filter featured tools"),
    current_user: Optional[UserResponse] = Depends(get_current_active_user),
):
    """
    Get tools by category slug with search and pagination

    Args:
        slug: Slug of the category to fetch tools for
        search: Optional search term to filter tools
        skip: Number of items to skip for pagination
        limit: Maximum number of items to return
        sort_by: Field to sort by
        sort_order: Sort order (asc or desc)
        price_type: Filter by price type
        is_featured: Filter featured tools
        current_user: Optional authenticated user

    Returns:
        Paginated list of tools in the specified category
    """
    from ..tools.tools_service import get_tools, search_tools

    # First, get the category to verify it exists
    category = await categories_service.get_category_by_slug(slug)
    if not category:
        # Try by name if not found by slug
        category = await categories_service.get_category_by_name(slug)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with slug or name '{slug}' not found",
        )

    # Validate sort_by field if provided
    valid_sort_fields = ["name", "created_at", "updated_at", "price"]
    if sort_by and sort_by not in valid_sort_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by field. Must be one of: {', '.join(valid_sort_fields)}",
        )

    # Validate sort_order
    if sort_order.lower() not in ["asc", "desc"]:
        raise HTTPException(
            status_code=400, detail="Invalid sort_order. Must be 'asc' or 'desc'"
        )

    # Get user ID if authenticated
    user_id = str(current_user.id) if current_user else None

    # Build filters dictionary
    # Priority-based filtering: prefer string category field over categories array
    # First try to find tools with the category in the string field
    # Only use categories array for tools without a string category
    filters = {
        "$or": [
            # Tools with the category in string field (regardless of categories array)
            {"category": category.name},
            # Tools without string category but with the category in array
            {
                "$and": [
                    {"$or": [{"category": {"$exists": False}}, {"category": ""}, {"category": None}]},
                    {"categories.id": category.id}
                ]
            }
        ]
    }

    if price_type:
        filters["price"] = price_type

    if is_featured is not None:
        filters["is_featured"] = is_featured

    # If search term is provided, use search_tools function
    if search and search.strip():
        # Use search_tools with proper category filters for improved relevance
        # Pass the exact search term as entered by the user, including any nonsensical terms
        sanitized_search = search.strip()
        logger.info(f"Searching in category {category.name} with query: '{sanitized_search}'")
        
        result = await search_tools(
            search_term=sanitized_search,
            skip=skip,
            limit=limit,
            additional_filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            user_id=user_id,
        )

        tools = result.get("tools", [])
        total = result.get("total", 0)
    else:
        # For non-search, use aggregation to get distinct tools
        from ..tools.tools_service import create_tool_response
        
        # First get the total count using aggregation
        count_pipeline = [
            {
                "$match": filters
            },
            # Group by tool ID to ensure uniqueness
            {
                "$group": {
                    "_id": "$_id"
                }
            },
            # Count the results
            {
                "$count": "total"
            }
        ]
        
        count_result = await tools_collection.aggregate(count_pipeline).to_list(length=1)
        total = count_result[0]["total"] if count_result else 0
        
        # Now get the paginated tools with sort
        sort_direction = -1 if sort_order.lower() == "desc" else 1
        
        pipeline = [
            {
                "$match": filters
            },
            # Group by tool ID to ensure uniqueness
            {
                "$group": {
                    "_id": "$_id",
                    "doc": {"$first": "$$ROOT"}  # Keep the first document for each ID
                }
            },
            # Sort after deduplication
            {
                "$sort": {f"doc.{sort_by}": sort_direction}
            },
            # Apply pagination
            {
                "$skip": skip
            },
            {
                "$limit": limit
            },
            # Return the full document
            {
                "$replaceRoot": {"newRoot": "$doc"}
            }
        ]
        
        cursor = tools_collection.aggregate(pipeline)
        
        # Get user's favorite tools if authenticated
        favorites_set = set()
        if user_id:
            from ..database.database import favorites
            user_favorites = favorites.find({"user_id": user_id})
            async for fav in user_favorites:
                favorites_set.add(fav["tool_unique_id"])
        
        # Process the tools using the existing create_tool_response function
        tools = []
        async for tool in cursor:
            tool_response = await create_tool_response(tool)
            if tool_response:
                # Set saved_by_user flag if authenticated
                if user_id and hasattr(tool_response, "unique_id"):
                    tool_response.saved_by_user = str(tool_response.unique_id) in favorites_set
                
                tools.append(tool_response)

    # Ensure tools is always a list, even if None is returned
    if tools is None:
        tools = []

    # Extract unique carriers from all tools
    all_carriers = set()
    if tools:
        for tool in tools:
            if isinstance(tool, dict):
                if tool.get("carriers"):
                    all_carriers.update(tool.get("carriers"))
            else:
                if tool.carriers:
                    all_carriers.update(tool.carriers)

    # Convert to sorted list
    unique_carriers = sorted(list(all_carriers))
    
    # Calculate pagination metadata
    current_page = skip // limit + 1 if limit > 0 else 1
    total_pages = (total + limit - 1) // limit if limit > 0 else 1

    return {
        "tools": tools,
        "total": total,
        "skip": skip,
        "limit": limit,
        "carriers": unique_carriers,
        "search_term": search,
        "current_page": current_page,
        "total_pages": total_pages,
    }


@public_router.get("/", response_model=List[CategoryResponse])
async def get_public_categories():
    """
    Get all available categories for tools.
    This endpoint is publicly accessible without authentication.

    Returns:
        List of category objects with id, name, slug, and count
    """
    categories = await categories_service.get_all_categories()
    return categories


@public_router.get("/mock-test", response_model=Dict[str, str])
async def public_mock_categories_test():
    """
    Public mock API endpoint for testing categories.
    No authentication required.

    Returns:
        A simple Hello World message
    """
    return {
        "message": "Hello World",
        "status": "success"
    }


@public_router.get("/slug/{slug}", response_model=CategoryResponse)
async def get_public_category_by_slug(slug: str):
    """
    Get a category by its slug.
    This endpoint is publicly accessible without authentication.

    Args:
        slug: Slug of the category to fetch

    Returns:
        Category object with id, name, slug, and count
    """
    category = await categories_service.get_category_by_slug(slug)
    if not category:
        # Try by name if not found by slug
        category = await categories_service.get_category_by_name(slug)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with slug or name '{slug}' not found",
        )
    return category


@public_router.get("/slug/{slug}/tools", response_model=PaginatedToolsResponse)
async def get_public_tools_by_category_slug(
    slug: str,
    search: Optional[str] = Query(None, description="Search term for filtering tools"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of items to return"
    ),
    sort_by: Optional[str] = Query(
        "created_at",
        description="Field to sort by (name, created_at, updated_at, price)",
    ),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    price_type: Optional[str] = Query(None, description="Filter by price type"),
    is_featured: Optional[bool] = Query(None, description="Filter featured tools"),
):
    """
    Get tools by category slug with search and pagination.
    This endpoint is publicly accessible without authentication.

    Args:
        slug: Slug of the category to fetch tools for
        search: Optional search term to filter tools
        skip: Number of items to skip for pagination
        limit: Maximum number of items to return
        sort_by: Field to sort by
        sort_order: Sort order (asc or desc)
        price_type: Filter by price type
        is_featured: Filter featured tools

    Returns:
        Paginated list of tools in the specified category
    """
    # Simply reuse the authenticated endpoint logic but pass None for current_user
    try:
        return await get_tools_by_category_slug(
            slug=slug,
            search=search,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            price_type=price_type,
            is_featured=is_featured,
            current_user=None,
        )
    except HTTPException as e:
        # Re-raise the exception to maintain same error handling
        raise e
