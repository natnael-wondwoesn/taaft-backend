from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from uuid import UUID

from ..auth.dependencies import get_current_active_user
from .models import ToolCreate, ToolUpdate, ToolResponse, PaginatedToolsResponse
from ..models.user import UserResponse
from .tools_service import (
    get_tools,
    get_tool_by_id,
    get_tool_by_unique_id,
    create_tool,
    update_tool,
    delete_tool,
    search_tools,
)

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/", response_model=PaginatedToolsResponse)
async def list_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_featured: Optional[bool] = Query(None, description="Filter featured tools"),
    price_type: Optional[str] = Query(None, description="Filter by price type"),
    sort_by: Optional[str] = Query(
        None, description="Field to sort by (name, created_at, updated_at)"
    ),
    sort_order: str = Query("asc", description="Sort order (asc or desc)"),
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    List all tools with pagination, filtering and sorting.
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

    return {"tools": tools, "total": total, "skip": skip, "limit": limit}


@router.get("/search", response_model=PaginatedToolsResponse)
async def search_tools_endpoint(
    q: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    Search for tools by name or description.
    """
    tools = await search_tools(query=q, skip=skip, limit=limit)
    total = await search_tools(query=q, count_only=True)
    return {"tools": tools, "total": total, "skip": skip, "limit": limit}


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: UUID,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    Get a specific tool by its UUID.
    """
    tool = await get_tool_by_id(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.get("/unique/{unique_id}", response_model=ToolResponse)
async def get_tool_by_unique_identifier(
    unique_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """
    Get a specific tool by its unique_id.
    """
    tool = await get_tool_by_unique_id(unique_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


# @router.post("/", response_model=ToolResponse, status_code=201)
# async def create_new_tool(
#     tool_data: ToolCreate,
#     current_user: UserResponse = Depends(get_current_active_user),
# ):
#     """
#     Create a new tool.
#     """
#     try:
#         return await create_tool(tool_data)
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         # Log the error for debugging
#         from ..logger import logger

#         logger.error(f"Tool creation error in route: {str(e)}")

#         # Provide a more helpful error message
#         if "validation error" in str(e).lower():
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Validation error: Please check that all required fields are provided correctly. Error: {str(e)}",
#             )
#         else:
#             raise HTTPException(
#                 status_code=500, detail=f"Failed to create tool: {str(e)}"
#             )


# @router.put("/{tool_id}", response_model=ToolResponse)
# async def update_existing_tool(
#     tool_id: UUID,
#     tool_update: ToolUpdate,
#     current_user: UserResponse = Depends(get_current_active_user),
# ):
#     """
#     Update an existing tool.
#     """
#     updated_tool = await update_tool(tool_id, tool_update)
#     if not updated_tool:
#         raise HTTPException(status_code=404, detail="Tool not found")
#     return updated_tool


# @router.delete("/{tool_id}", status_code=204)
# async def delete_existing_tool(
#     tool_id: UUID,
#     current_user: UserResponse = Depends(get_current_active_user),
# ):
#     """
#     Delete a tool.
#     """
#     success = await delete_tool(tool_id)
#     if not success:
#         raise HTTPException(status_code=404, detail="Tool not found")
#     return None
