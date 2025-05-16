"""
Public routes for tools, accessible without authentication
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from uuid import UUID

from app.models.user import UserResponse

from .models import PaginatedToolsResponse, ToolResponse
from .tools_service import (
    get_tools,
    get_tool_by_id,
    get_tool_by_unique_id,
    keyword_search_tools,
    search_tools,
    get_keywords,
)
from ..auth.dependencies import get_current_active_user, get_admin_user
from ..services.redis_cache import redis_cache
from ..logger import logger

public_router = APIRouter(prefix="/public/tools", tags=["public_tools"])


@public_router.get("/", response_model=PaginatedToolsResponse)
@redis_cache(prefix="public_tools_list")
async def list_public_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_featured: Optional[bool] = Query(None, description="Filter featured tools"),
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
    if is_featured is not None:
        filters["is_featured"] = is_featured
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

    # Get the tools with filtering and sorting
    tools = await get_tools(
        skip=skip,
        limit=limit,
        filters=filters if filters else None,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Get total count with the same filters
    total = await get_tools(count_only=True, filters=filters if filters else None)

    # Extract unique carriers from all tools
    all_carriers = set()
    for tool in tools:
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


@public_router.get("/search", response_model=PaginatedToolsResponse)
async def search_public_tools(
    q: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Search for tools by name or description.
    This endpoint is publicly accessible without authentication.
    """
    tools = await search_tools(query=q, skip=skip, limit=limit)
    total = await search_tools(query=q, count_only=True)

    # Extract unique carriers from all tools
    all_carriers = set()
    for tool in tools:
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

    # Extract unique carriers from all tools
    all_carriers = set()
    for tool in tools:
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


@public_router.get("/featured/search", response_model=PaginatedToolsResponse)
async def search_public_featured_tools(
    q: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Search for featured tools by name or description.
    This endpoint is publicly accessible without authentication.
    """
    # First search for tools matching the query
    tools = await search_tools(query=q, skip=0, limit=1000)

    # Filter the results to include only featured tools
    featured_tools = [tool for tool in tools if tool.get("is_featured", False)]

    # Apply pagination
    start_idx = min(skip, len(featured_tools))
    end_idx = min(skip + limit, len(featured_tools))
    paginated_tools = featured_tools[start_idx:end_idx]

    # Extract unique carriers from all featured tools
    all_carriers = set()
    for tool in featured_tools:
        if tool.carriers:
            all_carriers.update(tool.carriers)

    # Convert to sorted list
    unique_carriers = sorted(list(all_carriers))

    return {
        "tools": paginated_tools,
        "total": len(featured_tools),
        "skip": skip,
        "limit": limit,
        "carriers": unique_carriers,
    }


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


@public_router.get("/unique/{unique_id:path}", response_model=ToolResponse)
async def get_public_tool_by_unique_identifier(
    unique_id: str,
):
    """
    Get a specific tool by its unique_id.
    This endpoint is publicly accessible without authentication.
    """
    tool = await get_tool_by_unique_id(unique_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@public_router.post("/keyword-search", response_model=PaginatedToolsResponse)
async def public_keyword_search_endpoint(
    keywords: List[str],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Search for tools by exact keywords match.
    This endpoint is publicly accessible without authentication.
    """
    # Get tools that match any of the provided keywords
    tools = await keyword_search_tools(keywords=keywords, skip=skip, limit=limit)

    # Get total count with the same keywords
    total = await keyword_search_tools(keywords=keywords, count_only=True)

    # Extract unique carriers from all tools
    all_carriers = set()
    if tools:
        for tool in tools:
            if hasattr(tool, "carriers") and tool.carriers:
                all_carriers.update(tool.carriers)

    # Convert to sorted list
    unique_carriers = sorted(list(all_carriers))

    return {
        "tools": tools or [],  # Ensure we always return a list
        "total": total if isinstance(total, int) else 0,  # Ensure total is an integer
        "skip": skip,
        "limit": limit,
        "carriers": unique_carriers,
    }


@public_router.get("/keywords", response_model=List[str])
@redis_cache(prefix="public_keywords")
async def get_public_keywords(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    min_frequency: int = Query(0, ge=0),
    sort_by_frequency: bool = Query(True),
):
    """
    Get a list of all keywords in the database.
    This endpoint is publicly accessible without authentication.

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return
        min_frequency: Minimum frequency to include
        sort_by_frequency: Whether to sort by frequency

    Returns:
        List of unique keywords
    """
    keywords = await get_keywords(
        skip=skip,
        limit=limit,
        min_frequency=min_frequency,
        sort_by_frequency=sort_by_frequency,
    )

    return keywords
