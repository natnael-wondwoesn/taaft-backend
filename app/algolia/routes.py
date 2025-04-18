# app/algolia/routes.py
"""
API routes for Algolia search integration
Provides endpoints for search, indexing, and configuration
"""
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Body,
    status,
    BackgroundTasks,
)
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorCollection
import datetime

from .models import SearchParams, SearchResult, NaturalLanguageQuery, ProcessedQuery
from .config import algolia_config
from .search import algolia_search
from .indexer import algolia_indexer
from ..database import database
from ..logger import logger

router = APIRouter(
    prefix="/api/search",
    tags=["Search"],
    responses={404: {"description": "Not found"}},
)


# Get MongoDB collections
def get_tools_collection() -> AsyncIOMotorCollection:
    """Get the tools collection"""
    return database.client.get_database("taaft_db").get_collection("tools")


def get_glossary_collection() -> AsyncIOMotorCollection:
    """Get the glossary collection"""
    return database.client.get_database("taaft_db").get_collection("glossary")


@router.get("/tools", response_model=SearchResult)
async def search_tools(
    query: str = "",
    categories: Optional[List[str]] = Query(None),
    pricing_types: Optional[List[str]] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: Optional[str] = Query(None, regex="^(relevance|newest|trending)$"),
    filters: Optional[str] = Query(None),
):
    """
    Search for tools using Algolia

    Args:
        query: Search query
        categories: List of category IDs to filter by
        pricing_types: List of pricing types to filter by
        min_rating: Minimum rating to filter by
        page: Page number (1-based)
        per_page: Number of results per page
        sort_by: Sort order (relevance, newest, trending)
        filters: Custom Algolia filter query

    Returns:
        SearchResult object with tools and metadata
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )

    # Create search parameters
    params = SearchParams(
        query=query,
        categories=categories,
        pricing_types=pricing_types,
        min_rating=min_rating,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        filters=filters,
    )

    # Execute search
    result = await algolia_search.search_tools(params)
    return result


@router.get("/glossary")
async def search_glossary(
    query: str = "",
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    Search glossary terms using Algolia

    Args:
        query: Search query
        page: Page number (1-based)
        per_page: Number of results per page

    Returns:
        Dictionary with search results
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )

    # Execute search
    result = await algolia_search.search_glossary(query, page, per_page)
    return result


@router.post("/nlp", response_model=ProcessedQuery)
async def process_nlp_query(
    nlq: NaturalLanguageQuery,
):
    """
    Process a natural language query into structured search parameters

    Args:
        nlq: Natural language query object

    Returns:
        ProcessedQuery object with structured search parameters
    """
    # Process the query
    processed_query = await algolia_search.process_natural_language_query(nlq)
    return processed_query


@router.post("/nlp-search", response_model=SearchResult)
async def nlp_search(
    nlq: NaturalLanguageQuery,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    Perform a natural language search in one step

    Args:
        nlq: Natural language query object
        page: Page number (1-based)
        per_page: Number of results per page

    Returns:
        SearchResult object with tools and metadata
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )

    # Process the query
    processed_query = await algolia_search.process_natural_language_query(nlq)

    # Create search parameters
    params = SearchParams(
        query=processed_query.search_query,
        categories=processed_query.categories,
        pricing_types=processed_query.pricing_types,
        page=page,
        per_page=per_page,
        filters=processed_query.filters,
    )

    # Execute search
    result = await algolia_search.search_tools(params)

    # Add the interpreted query to the result
    result_dict = result.dict()
    result_dict["processed_query"] = processed_query

    return result_dict


@router.post("/index/tools", status_code=status.HTTP_202_ACCEPTED)
async def index_tools(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(100, ge=1, le=1000),
    tools_collection: AsyncIOMotorCollection = Depends(get_tools_collection),
):
    """
    Index all tools in MongoDB to Algolia (asynchronous operation)

    Args:
        background_tasks: FastAPI background tasks
        batch_size: Number of tools to index in each batch
        tools_collection: MongoDB collection containing tools

    Returns:
        Status message
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )

    # Schedule the indexing task in the background
    background_tasks.add_task(algolia_indexer.index_tools, tools_collection, batch_size)

    return {
        "status": "processing",
        "message": "Indexing tools to Algolia in the background",
    }


@router.post("/index/glossary", status_code=status.HTTP_202_ACCEPTED)
async def index_glossary(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(100, ge=1, le=1000),
    glossary_collection: AsyncIOMotorCollection = Depends(get_glossary_collection),
):
    """
    Index all glossary terms in MongoDB to Algolia (asynchronous operation)

    Args:
        background_tasks: FastAPI background tasks
        batch_size: Number of terms to index in each batch
        glossary_collection: MongoDB collection containing glossary terms

    Returns:
        Status message
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )

    # Schedule the indexing task in the background
    background_tasks.add_task(
        algolia_indexer.index_glossary_terms, glossary_collection, batch_size
    )

    return {
        "status": "processing",
        "message": "Indexing glossary terms to Algolia in the background",
    }


@router.post("/index/tool/{tool_id}")
async def index_single_tool(
    tool_id: str,
    tools_collection: AsyncIOMotorCollection = Depends(get_tools_collection),
):
    """
    Index a single tool in Algolia

    Args:
        tool_id: MongoDB _id of the tool
        tools_collection: MongoDB collection containing tools

    Returns:
        Status message
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )

    # Get the tool from MongoDB
    from bson import ObjectId

    try:
        tool = await tools_collection.find_one({"_id": ObjectId(tool_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tool ID format"
        )

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found",
        )

    # Index the tool
    success = await algolia_indexer.index_tool(tool)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to index tool",
        )

    return {"status": "success", "message": f"Tool {tool_id} indexed successfully"}


@router.delete("/index/tool/{tool_id}")
async def delete_tool_from_index(
    tool_id: str,
):
    """
    Delete a tool from Algolia index

    Args:
        tool_id: MongoDB _id of the tool

    Returns:
        Status message
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )

    # Delete the tool from Algolia
    success = await algolia_indexer.delete_tool(tool_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tool from index",
        )

    return {
        "status": "success",
        "message": f"Tool {tool_id} deleted from index successfully",
    }


@router.get("/config")
async def get_search_config():
    """
    Get Algolia search configuration for frontend use

    Returns:
        Configuration object with app ID and search-only API key
    """
    return {
        "app_id": algolia_config.app_id,
        "search_api_key": algolia_config.search_only_api_key,
        "tools_index_name": algolia_config.tools_index_name,
        "glossary_index_name": algolia_config.glossary_index_name,
        "is_configured": algolia_config.is_configured(),
    }
