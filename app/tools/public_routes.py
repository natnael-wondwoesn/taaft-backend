"""
Public routes for tools, accessible without authentication
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List

from app.models.user import UserResponse

from .models import PaginatedToolsResponse, ToolResponse
from .tools_service import get_tools, keyword_search_tools, search_tools
from ..auth.dependencies import get_current_active_user, get_admin_user
from ..services.redis_cache import redis_cache

public_router = APIRouter(prefix="/public/tools", tags=["public_tools"])


@public_router.get("/", response_model=PaginatedToolsResponse)
@redis_cache(prefix="public_tools_list")
async def list_public_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    category: Optional[str] = Query(None, description="Filter by category"),
    price_type: Optional[str] = Query(None, description="Filter by price type"),
    sort_by: Optional[str] = Query(
        "created_at", description="Field to sort by (name, created_at, updated_at)"
    ),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
):
    """
    List all tools with pagination, filtering and sorting.
    This endpoint is publicly accessible without authentication.
    Default sorting is by created_at in descending order (newest first).
    """
    # Build filters dictionary from query parameters
    filters = {}
    if category:
        filters["category"] = category
    if price_type:
        filters["price"] = price_type

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

    # Ensure we're returning the latest tools first by default
    if not sort_by or sort_by == "created_at":
        # If sort_by is not specified or is created_at, default to descending order (newest first)
        if not sort_order or sort_order.lower() != "asc":
            sort_order = "desc"

    # Get the tools with filtering and sorting
    tools_list = await get_tools(
        skip=skip,
        limit=limit,
        filters=filters if filters else None,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Get total count with the same filters
    total = await get_tools(count_only=True, filters=filters if filters else None)

    return {"tools": tools_list, "total": total, "skip": skip, "limit": limit}


@public_router.get("/featured", response_model=PaginatedToolsResponse)
@redis_cache(prefix="public_featured_tools")
async def get_featured_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search term for filtering tools"),
    category: Optional[str] = Query(None, description="Filter by category"),
    price_type: Optional[str] = Query(None, description="Filter by price type"),
    sort_by: Optional[str] = Query(
        "created_at", description="Field to sort by (name, created_at, updated_at)"
    ),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
):
    """
    Get a list of featured tools. This endpoint is publicly accessible without authentication.
    Default sorting is by created_at in descending order (newest first).

    - **search**: Optional search term to filter tools by name, description, or keywords
    - **category**: Optional category filter
    - **price_type**: Optional price type filter
    - **sort_by**: Field to sort by
    - **sort_order**: Sort order (asc or desc)
    """
    # Apply filter for featured tools only
    filters = {"is_featured": True}

    # Add additional filters if provided
    if category:
        filters["category"] = category
    if price_type:
        filters["price"] = price_type

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

    # If search term is provided, use search_tools
    if search and search.strip():
        # Use search_tools, then filter for featured tools in memory
        search_results = await search_tools(query=search, skip=0, limit=1000)

        # Filter to only include featured tools
        filtered_tools = [tool for tool in search_results if tool.is_featured]

        # Apply other filters
        if category:
            filtered_tools = [
                tool for tool in filtered_tools if tool.category == category
            ]
        if price_type:
            filtered_tools = [
                tool for tool in filtered_tools if tool.price == price_type
            ]

        # Apply pagination
        total = len(filtered_tools)
        tools = filtered_tools[skip : skip + limit]
    else:
        # No search term, use regular get_tools with filters
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

    return {"tools": tools, "total": total, "skip": skip, "limit": limit}


@public_router.get("/sponsored", response_model=PaginatedToolsResponse)
@redis_cache(prefix="public_sponsored_tools")
async def get_sponsored_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search term for filtering tools"),
    category: Optional[str] = Query(None, description="Filter by category"),
    price_type: Optional[str] = Query(None, description="Filter by price type"),
    sort_by: Optional[str] = Query(
        "created_at", description="Field to sort by (name, created_at, updated_at)"
    ),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
):
    """
    Get a list of sponsored tools (identical to featured tools).
    This endpoint is publicly accessible without authentication.
    Default sorting is by created_at in descending order (newest first).

    - **search**: Optional search term to filter tools by name, description, or keywords
    - **category**: Optional category filter
    - **price_type**: Optional price type filter
    - **sort_by**: Field to sort by
    - **sort_order**: Sort order (asc or desc)
    """
    # Apply filter for featured tools only (reusing the same field)
    filters = {"is_featured": True}

    # Add additional filters if provided
    if category:
        filters["category"] = category
    if price_type:
        filters["price"] = price_type

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

    # If search term is provided, use search_tools
    if search and search.strip():
        # Use search_tools, then filter for featured tools in memory
        search_results = await search_tools(query=search, skip=0, limit=1000)

        # Filter to only include featured tools
        filtered_tools = [tool for tool in search_results if tool.is_featured]

        # Apply other filters
        if category:
            filtered_tools = [
                tool for tool in filtered_tools if tool.category == category
            ]
        if price_type:
            filtered_tools = [
                tool for tool in filtered_tools if tool.price == price_type
            ]

        # Apply pagination
        total = len(filtered_tools)
        tools = filtered_tools[skip : skip + limit]
    else:
        # No search term, use regular get_tools with filters
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

    return {"tools": tools, "total": total, "skip": skip, "limit": limit}
