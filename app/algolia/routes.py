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
        algolia_indexer.index_glossary, glossary_collection, batch_size
    )

    return {
        "status": "processing",
        "message": "Indexing glossary to Algolia in the background",
    }


@router.post("/index/tool/{tool_id}")
async def index_single_tool(
    tool_id: str,
    tools_collection: AsyncIOMotorCollection = Depends(get_tools_collection),
):
    """
    Index a single tool in MongoDB to Algolia

    Args:
        tool_id: ID of the tool to index
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

    tool = await tools_collection.find_one({"_id": ObjectId(tool_id)})
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found"
        )

    # Index the tool
    await algolia_indexer.index_single_tool(tool)

    return {
        "status": "success",
        "message": f"Indexed tool {tool_id}",
    }


@router.delete("/index/tool/{tool_id}")
async def delete_tool_from_index(
    tool_id: str,
):
    """
    Delete a tool from Algolia index

    Args:
        tool_id: ID of the tool to delete

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
    await algolia_indexer.delete_tool(tool_id)

    return {
        "status": "success",
        "message": f"Deleted tool {tool_id} from index",
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


@router.post("/nlp-search", response_model=SearchResult)
async def nlp_search(
    nlq: NaturalLanguageQuery,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    Perform a natural language search

    This endpoint handles NLP query processing and search execution in a
    single API call. It's the only way to search for AI tools using
    natural language questions.

    Examples:
        - "I need a free tool for writing blog posts"
        - "What AI can help my marketing team with social media?"
        - "Looking for an enterprise-grade coding assistant"
        - "Show me the most popular image generation tools"

    Args:
        nlq: Natural language query object with question and optional context
        page: Page number (1-based)
        per_page: Number of results per page

    Returns:
        SearchResult object with tools and metadata, including the processed query
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )

    # Execute the NLP search
    result = await algolia_search.execute_nlp_search(nlq, page, per_page)

    # Return the search result along with the processed query
    return result
