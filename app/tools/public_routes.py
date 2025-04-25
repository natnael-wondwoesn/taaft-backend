"""
Public routes for tools, accessible without authentication
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from .models import PaginatedToolsResponse
from .tools_service import get_tools

public_router = APIRouter(prefix="/public/tools", tags=["public_tools"])


@public_router.get("/featured", response_model=PaginatedToolsResponse)
async def get_featured_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sort_by: Optional[str] = Query(
        None, description="Field to sort by (name, created_at, updated_at)"
    ),
    sort_order: str = Query("asc", description="Sort order (asc or desc)"),
):
    """
    Get a list of featured tools. This endpoint is publicly accessible without authentication.
    """
    # Apply filter for featured tools only
    filters = {"is_featured": True}

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

    # Get the featured tools with sorting
    tools = await get_tools(
        skip=skip,
        limit=limit,
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Get total count of featured tools
    total = await get_tools(count_only=True, filters=filters)

    # Ensure tools is always a list, even if None is returned
    if tools is None:
        tools = []

    return {"tools": tools, "total": total, "skip": skip, "limit": limit}


@public_router.get("/sponsored", response_model=PaginatedToolsResponse)
async def get_sponsored_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sort_by: Optional[str] = Query(
        None, description="Field to sort by (name, created_at, updated_at)"
    ),
    sort_order: str = Query("asc", description="Sort order (asc or desc)"),
):
    """
    Get a list of sponsored tools (identical to featured tools).
    This endpoint is publicly accessible without authentication.
    """
    # Apply filter for featured tools only (reusing the same field)
    filters = {"is_featured": True}

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

    # Get the featured tools with sorting
    tools = await get_tools(
        skip=skip,
        limit=limit,
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Get total count of featured tools
    total = await get_tools(count_only=True, filters=filters)

    # Ensure tools is always a list, even if None is returned
    if tools is None:
        tools = []

    return {"tools": tools, "total": total, "skip": skip, "limit": limit}
