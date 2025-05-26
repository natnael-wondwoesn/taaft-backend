# app/categories/routes.py
"""
API routes for categories management
"""
from fastapi import APIRouter, HTTPException, Query, status, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime

from .models import CategoryResponse
from .service import categories_service
from ..tools.models import PaginatedToolsResponse

# Remove the direct import to avoid circular dependencies
# from ..tools.tools_service import get_tools, search_tools
from ..logger import logger
from ..services.redis_cache import invalidate_cache
from ..auth.dependencies import get_admin_user
from ..models.user import UserResponse

router = APIRouter(
    prefix="/api/categories",
    tags=["Categories"],
    responses={404: {"description": "Not found"}},
)

# Public router without authentication
public_router = APIRouter(
    prefix="/public/categories",
    tags=["public_categories"],
    responses={404: {"description": "Not found"}},
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with slug '{slug}' not found",
        )
    return category


@router.get("/slug/{slug}/tools", response_model=PaginatedToolsResponse)
async def get_tools_by_category_slug(
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

    Returns:
        Paginated list of tools in the specified category
    """
    # Import tools_service functions here to avoid circular imports
    from ..tools.tools_service import get_tools, search_tools

    # First, get the category to verify it exists
    category = await categories_service.get_category_by_slug(slug)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with slug '{slug}' not found",
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

    # Build filters dictionary
    filters = {"categories.id": category.id}

    if price_type:
        filters["price"] = price_type

    if is_featured is not None:
        filters["is_featured"] = is_featured

    # If search term is provided, use search_tools function
    if search and search.strip():
        result = await search_tools(
            search_term=search,
            skip=skip,
            limit=limit,
            additional_filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        tools = result.get("tools", [])
        total = result.get("total", 0)
    else:
        # Otherwise, use get_tools with filters
        tools = await get_tools(
            skip=skip,
            limit=limit,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        total = await get_tools(count_only=True, filters=filters)

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

    return {
        "tools": tools,
        "total": total,
        "skip": skip,
        "limit": limit,
        "carriers": unique_carriers,
    }


@router.post("/recalculate", response_model=Dict[str, Any])
async def recalculate_category_counts():
    """
    Recalculate the count of tools for each category.
    This endpoint is publicly accessible with no authentication required.

    Returns:
        Dictionary with success status and summary of updated categories
    """
    # Import the update_category_counts function from the script
    from ..scripts.update_category_counts import update_category_counts

    try:
        # Run the update function and get the result
        result = await update_category_counts()

        # Invalidate any category-related caches
        invalidate_cache("category_tools")

        # Add additional information to the result
        result["timestamp"] = str(datetime.now())

        # If the update was successful, add a friendly message
        if result["success"]:
            result["message"] = (
                f"Category counts recalculated successfully. Updated {result['categories_updated']} out of {result['categories_total']} categories."
            )

        return result
    except Exception as e:
        logger.error(f"Error recalculating category counts: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to recalculate category counts: {str(e)}"
        )


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with slug '{slug}' not found",
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
    # Import tools_service functions here to avoid circular imports
    from ..tools.tools_service import get_tools, search_tools

    # First, get the category to verify it exists
    category = await categories_service.get_category_by_slug(slug)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with slug '{slug}' not found",
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

    # Build filters dictionary
    filters = {"categories.id": category.id}

    if price_type:
        filters["price"] = price_type

    if is_featured is not None:
        filters["is_featured"] = is_featured

    # If search term is provided, use search_tools function
    if search and search.strip():
        result = await search_tools(
            search_term=search,
            skip=skip,
            limit=limit,
            additional_filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        tools = result.get("tools", [])
        total = result.get("total", 0)
    else:
        # Otherwise, use get_tools with filters
        tools = await get_tools(
            skip=skip,
            limit=limit,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        total = await get_tools(count_only=True, filters=filters)

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
