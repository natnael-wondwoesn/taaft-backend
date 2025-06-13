"""
Public routes for tools, accessible without authentication
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from typing import Optional, List
from uuid import UUID

from app.models.user import UserResponse

from .models import PaginatedToolsResponse, ToolResponse
from .tools_service import (
    create_tool_response,
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
from ..categories.service import categories_service

public_router = APIRouter(prefix="/public/tools", tags=["public_tools"])


@public_router.get("/", response_model=PaginatedToolsResponse)
async def list_public_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search term for filtering tools"),
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
        # Use $or to match either categories.id OR the category string field
        filters["$or"] = [
            {"categories.id": category},  # Array-based categories
            {"category": category}        # String-based category
        ]
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
            filters=filters if filters else None,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Get total count with the same filters
        total = await get_tools(count_only=True, filters=filters if filters else None)

    # Extract unique carriers from all tools
    all_carriers = set()
    if tools:
        for tool in tools:
            if type(tool) == dict:
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


@public_router.get("/search", response_model=PaginatedToolsResponse)
async def search_public_tools(
    q: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Search for tools by name or description using MongoDB directly.
    This endpoint is publicly accessible without authentication.
    """
    from ..database.database import tools

    # Create a MongoDB text search query
    query = {"$text": {"$search": q}}

    # Get tools with pagination
    cursor = tools.find(query).skip(skip).limit(limit)

    # Convert MongoDB documents to ToolResponse objects
    tools_list = []
    async for tool in cursor:
        tool_response = await create_tool_response(tool)
        if tool_response:
            tools_list.append(tool_response)

    # Get total count with the same query
    total = await tools.count_documents(query)

    return {
        "tools": tools_list,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@public_router.get("/featured", response_model=PaginatedToolsResponse)
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

    # If search term is provided, use direct MongoDB search
    if search and search.strip():
        from ..database.database import tools

        # Create a query that combines search term with featured filter
        query = {"$text": {"$search": search}, "is_featured": True}

        # Add additional filters if provided
        if category:
            query["category"] = category
        if price_type:
            query["price"] = price_type

        # Get tools with pagination
        cursor = tools.find(query).skip(skip).limit(limit)

        # Convert MongoDB documents to ToolResponse objects
        tools_list = []
        async for tool in cursor:
            tool_response = await create_tool_response(tool)
            if tool_response:
                tools_list.append(tool_response)

        # Get total count with the same query
        total = await tools.count_documents(query)

        tools = tools_list
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
    if tools:
        for tool in tools:
            if type(tool) == dict:
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


@public_router.get("/featured/search", response_model=PaginatedToolsResponse)
async def search_public_featured_tools(
    q: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Search for featured tools by name or description using MongoDB directly.
    This endpoint is publicly accessible without authentication.
    """
    from ..database.database import tools

    # Create a MongoDB text search query that also filters for featured tools
    query = {"$text": {"$search": q}, "is_featured": True}

    # Get tools with pagination
    cursor = tools.find(query).skip(skip).limit(limit)

    # Convert MongoDB documents to ToolResponse objects
    tools_list = []
    async for tool in cursor:
        tool_response = await create_tool_response(tool)
        if tool_response:
            tools_list.append(tool_response)

    # Get total count with the same query
    total = await tools.count_documents(query)

    return {
        "tools": tools_list,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@public_router.get("/sponsored", response_model=PaginatedToolsResponse)
async def get_public_sponsored_tools(
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
    Get a list of publicly sponsored tools with pagination, filtering, and sorting.
    This endpoint is publicly accessible without authentication.
    Default sorting is by created_at in descending order (newest first).

    - **search**: Optional search term to filter tools by name, description, or keywords
    - **category**: Optional category filter
    - **price_type**: Optional price type filter
    - **sort_by**: Field to sort by
    - **sort_order**: Sort order (asc or desc)
    """
    # Apply filter for sponsored tools only
    filters = {"is_sponsored_public": True}

    # Add additional filters if provided
    if category:
        # Get the category to verify it exists
        cat_obj = await categories_service.get_category_by_id(category)
        if cat_obj:
            # Use $or to match either categories.id OR the category string field
            filters["$or"] = [
                {"categories.id": cat_obj.id},  # Array-based categories
                {"category": cat_obj.name}      # String-based category
            ]

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

    # Extract unique carriers from all tools
    all_carriers = set()
    if tools:
        for tool in tools:
            if type(tool) == dict:
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


@public_router.get("/unique/{unique_id}", response_model=ToolResponse)
async def get_public_tool_by_unique_identifier(
    unique_id: str,
    response: Response,
):
    """
    Get a specific tool by its unique_id without requiring authentication.
    """
    tool = await get_tool_by_unique_id(unique_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    # Add header flag indicating data source (always from database now that we don't track cache status)
    response.headers["X-Data-Source"] = "database"
    
    return tool


@public_router.post("/keyword-search", response_model=PaginatedToolsResponse)
async def public_keyword_search_endpoint(
    keywords: List[str],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Search for tools by exact keywords match using MongoDB directly.
    This endpoint is publicly accessible without authentication.
    """
    from ..database.database import tools

    # Create a query to find tools where any of the provided keywords match
    query = {
        "$or": [
            {"carriers": {"$in": keywords}},
            {"name": {"$regex": "|".join(keywords), "$options": "i"}},
            {"description": {"$regex": "|".join(keywords), "$options": "i"}},
            {"keywords": {"$in": keywords}},
            {"category": {"$regex": "|".join(keywords), "$options": "i"}},
            {"generated_description": {"$regex": "|".join(keywords), "$options": "i"}},
        ]
    }

    # Find matching tools with pagination
    cursor = tools.find(query).skip(skip).limit(limit)

    # Convert MongoDB documents to ToolResponse objects
    tools_list = []
    async for tool in cursor:
        tool_response = await create_tool_response(tool)
        if tool_response:
            tools_list.append(tool_response)

    # Get total count with the same query
    total = await tools.count_documents(query)

    return {
        "tools": tools_list,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@public_router.get("/keywords", response_model=List[str])
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


@public_router.get("/category/{category_slug}", response_model=PaginatedToolsResponse)
async def get_public_tools_by_category(
    category_slug: str,
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
        category_slug: Slug of the category to fetch tools for
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
    # Import categories_service to get the category ID from the slug
    from ..categories.service import categories_service

    # Get the category by slug
    category = await categories_service.get_category_by_slug(category_slug)
    if not category:
        raise HTTPException(
            status_code=404,
            detail=f"Category with slug '{category_slug}' not found",
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
    # Use $or to match either categories.id OR the category string field
    filters = {
        "$or": [
            {"categories.id": category.id},  # Array-based categories
            {"category": category.name}      # String-based category
        ]
    }

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


@public_router.get("/category/{category_id}", response_model=PaginatedToolsResponse)
async def get_public_tools_by_category_id(
    category_id: str,
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
    Get tools by category ID with search and pagination.
    This endpoint is publicly accessible without authentication.

    Args:
        category_id: ID of the category to fetch tools for
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
    # First, get the category to verify it exists
    category = await categories_service.get_category_by_id(category_id)
    if not category:
        raise HTTPException(
            status_code=404,
            detail=f"Category with ID '{category_id}' not found",
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
    # Use $or to match either categories.id OR the category string field
    filters = {
        "$or": [
            {"categories.id": category.id},  # Array-based categories
            {"category": category.name}      # String-based category
        ]
    }

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


@public_router.get("/browse/search", response_model=PaginatedToolsResponse)
async def browse_public_tools_search(
    q: Optional[str] = Query(None, description="Search term for filtering tools"),
    category: Optional[str] = Query(None, description="Filter by category ID"),
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
    Advanced search for tools on the browse page with filtering, sorting, and pagination.
    This endpoint is publicly accessible without authentication.

    Args:
        q: Optional search term to filter tools
        category: Optional category ID to filter by
        skip: Number of items to skip for pagination
        limit: Maximum number of items to return
        sort_by: Field to sort by
        sort_order: Sort order (asc or desc)
        price_type: Filter by price type
        is_featured: Filter featured tools

    Returns:
        Paginated list of tools matching the search criteria
    """
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
    filters = {}
    
    if category:
        # Get the category to verify it exists
        cat_obj = await categories_service.get_category_by_id(category)
        if cat_obj:
            # Use $or to match either categories.id OR the category string field
            filters["$or"] = [
                {"categories.id": cat_obj.id},  # Array-based categories
                {"category": cat_obj.name}      # String-based category
            ]

    if price_type:
        filters["price"] = price_type

    if is_featured is not None:
        filters["is_featured"] = is_featured

    # If search term is provided, use search_tools function
    if q and q.strip():
        result = await search_tools(
            search_term=q,
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
            filters=filters if filters else None,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        total = await get_tools(count_only=True, filters=filters if filters else None)

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
        "search_term": q,
        "current_page": current_page,
        "total_pages": total_pages,
    }
