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

from .models import (
    AlgoliaJobImpactRecord,
    AlgoliaToolRecord,
    JobImpactWithTools,
    SearchFacet,
    SearchFacets,
    SearchParams, 
    SearchResult, 
    NaturalLanguageQuery, 
    ProcessedQuery,
    JobImpactSearchResult,
    JobImpactSearchParams,
    JobImpactToolsSearchResult,
    JobImpactToolsSearchParams,
    TaskToolsSearchResult,
    JobToolsRecommendation
)
from .config import algolia_config
from .indexer import algolia_indexer
from ..database import database
from ..logger import logger
from ..auth.dependencies import get_admin_user
from ..models.user import UserInDB

# Create the router before importing middleware that might use it
router = APIRouter(
    prefix="/api/search",
    tags=["Search"],
    responses={404: {"description": "Not found"}},
)

# Now import the search implementation that might depend on the router
from .search import algolia_search

# Import performance stats after router is defined
from .middleware import SEARCH_PERFORMANCE_STATS


# Get MongoDB collections
def get_tools_collection() -> AsyncIOMotorCollection:
    """Get the tools collection"""
    return database.client.get_database("taaft_db").get_collection("tools")


def get_glossary_collection() -> AsyncIOMotorCollection:
    """Get the glossary collection"""
    return database.client.get_database("taaft_db").get_collection("glossary")


def get_job_impacts_collection() -> AsyncIOMotorCollection:
    """Get the job impacts collection"""
    return database.client.get_database("taaft_db").get_collection("tools_job_impacts")


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


@router.post("/index/job-impacts", status_code=status.HTTP_202_ACCEPTED)
async def index_job_impacts(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(100, ge=1, le=1000),
    job_impacts_collection: AsyncIOMotorCollection = Depends(
        get_job_impacts_collection
    ),
):
    """
    Index all job impacts in MongoDB to Algolia (asynchronous operation)

    After indexing, job impacts can be searched using the /direct-search/job-impacts endpoint.

    Args:
        background_tasks: FastAPI background tasks
        batch_size: Number of job impacts to index in each batch
        job_impacts_collection: MongoDB collection containing job impacts

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
        algolia_indexer.index_job_impacts, job_impacts_collection, batch_size
    )

    return {
        "status": "processing",
        "message": "Indexing job impacts to Algolia in the background",
        "search_endpoint": "/api/search/direct-search/job-impacts",
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
        "tools_job_impacts_index_name": algolia_config.tools_job_impacts_index_name,
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


# @router.post("/match-keywords")
# async def match_keywords(
#     keywords: List[str] = Body(..., description="List of keywords to match"),
#     max_matches: int = Query(3, ge=1, le=10, description="Maximum matches per keyword"),
# ):
#     """
#     Match input keywords with semantically similar keywords from our database

#     This endpoint uses an LLM to find the closest matching keywords in our database
#     for each of the input keywords. This is useful for query expansion and
#     finding relevant terms.

#     Args:
#         keywords: List of keywords to match
#         max_matches: Maximum number of matches to return per keyword

#     Returns:
#         Dictionary mapping input keywords to their closest matches
#     """
#     # Validate Algolia configuration
#     if not algolia_config.is_configured():
#         raise HTTPException(
#             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
#             detail="Search service is not configured",
#         )

#     if not keywords:
#         return {}

#     # Limit number of input keywords to prevent abuse
#     if len(keywords) > 20:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Maximum of 20 keywords allowed per request",
#         )

#     # Call the matching function
#     try:
#         matches = await algolia_search.match_keywords_with_database(
#             input_keywords=keywords,
#             max_matches=max_matches,
#         )
#         return matches
#     except Exception as e:
#         logger.error(f"Error matching keywords: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error matching keywords: {str(e)}",
#         )


@router.post("/search-with-matched-keywords")
async def search_with_matched_keywords(
    keywords: List[str] = Body(..., description="List of keywords to match and search"),
    page: int = Query(0, ge=0, description="Page number (0-based)"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
):
    """
    Search using input keywords after matching them with database keywords

    This endpoint first matches the input keywords with semantically similar keywords
    in our database, then uses the expanded keyword set to search the tools index.

    Args:
        keywords: Original keywords to match and search with
        page: Page number (0-based)
        per_page: Number of results per page

    Returns:
        Search results from Algolia with expanded keywords information
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )

    if not keywords:
        return {
            "hits": [],
            "nbHits": 0,
            "page": page,
            "nbPages": 0,
            "processingTimeMS": 0,
            "original_keywords": [],
            "expanded_keywords": [],
            "keyword_matches": {},
        }

    # Limit number of input keywords to prevent abuse
    if len(keywords) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum of 20 keywords allowed per request",
        )

    # Perform the search with matched keywords
    try:
        results = await algolia_search.search_with_matched_keywords(
            input_keywords=keywords,
            page=page,
            per_page=per_page,
        )
        return results
    except Exception as e:
        logger.error(f"Error searching with matched keywords: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching with matched keywords: {str(e)}",
        )


@router.get("/keywords")
async def get_all_keywords():
    """
    Get all known keywords from the database

    This endpoint returns a list of all keywords extracted from the indexed tools.
    This is useful for understanding what keywords are available for matching.

    Returns:
        List of all known keywords from the database
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )

    try:
        # Get all keywords from the database
        keywords = await algolia_search.get_known_keywords_from_database()
        return {"keywords": keywords, "count": len(keywords)}
    except Exception as e:
        logger.error(f"Error getting keywords: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting keywords: {str(e)}",
        )


@router.get("/stats")
async def get_search_stats():
    """
    Get search performance statistics

    Returns:
        Dictionary containing search performance metrics
    """
    # Calculate averages
    avg_response_time = 0
    avg_cached_response_time = 0

    if SEARCH_PERFORMANCE_STATS["total_requests"] > 0:
        avg_response_time = (
            SEARCH_PERFORMANCE_STATS["total_response_time"]
            / SEARCH_PERFORMANCE_STATS["total_requests"]
        )

    if SEARCH_PERFORMANCE_STATS["cached_requests"] > 0:
        avg_cached_response_time = (
            SEARCH_PERFORMANCE_STATS["cached_response_time"]
            / SEARCH_PERFORMANCE_STATS["cached_requests"]
        )

    # Calculate cache hit ratio
    cache_hit_ratio = 0
    if SEARCH_PERFORMANCE_STATS["total_requests"] > 0:
        cache_hit_ratio = (
            SEARCH_PERFORMANCE_STATS["cached_requests"]
            / SEARCH_PERFORMANCE_STATS["total_requests"]
        )

    return {
        "total_requests": SEARCH_PERFORMANCE_STATS["total_requests"],
        "average_response_time": avg_response_time,
        "cached_requests": SEARCH_PERFORMANCE_STATS["cached_requests"],
        "average_cached_response_time": avg_cached_response_time,
        "cache_hit_ratio": cache_hit_ratio,
        "slow_requests": SEARCH_PERFORMANCE_STATS["slow_requests"],
        "error_requests": SEARCH_PERFORMANCE_STATS["error_requests"],
        "stats_since": SEARCH_PERFORMANCE_STATS["last_reset"].isoformat(),
    }


@router.post("/stats/reset")
async def reset_search_stats():
    """
    Reset search performance statistics

    Returns:
        Success message
    """
    # Store previous stats for the response
    previous_stats = dict(SEARCH_PERFORMANCE_STATS)

    # Reset the stats
    SEARCH_PERFORMANCE_STATS.update(
        {
            "total_requests": 0,
            "total_response_time": 0,
            "cached_requests": 0,
            "cached_response_time": 0,
            "slow_requests": 0,
            "error_requests": 0,
            "last_reset": datetime.datetime.utcnow(),
        }
    )

    return {
        "status": "success",
        "message": "Search statistics reset successfully",
        "previous_stats": previous_stats,
    }


@router.get("/job-impacts")
async def search_job_impacts(
    query: str = Query(None, description="Search query"),
    job_title: str = Query(None, description="Filter by job title"),
    job_category: str = Query(None, description="Filter by job category"),
    min_impact_score: float = Query(
        None, ge=0, le=100, description="Minimum impact score"
    ),
    task_name: str = Query(None, description="Filter by task name"),
    tool_name: str = Query(None, description="Filter by tool name"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    sort_by: str = Query(
        "impact_score",
        enum=["impact_score", "relevance", "date"],
        description="Sort order",
    ),
    current_user: UserInDB = Depends(get_admin_user),
):
    """
    Search for job impacts in the Algolia index

    This endpoint allows searching and filtering job impacts data by various criteria.

    Args:
        query: General search query
        job_title: Filter by job title
        job_category: Filter by job category
        min_impact_score: Filter by minimum impact score
        task_name: Filter by task name
        tool_name: Filter by tool name
        page: Page number (1-based)
        per_page: Number of results per page
        sort_by: Sort order
        current_user: Current authenticated user

    Returns:
        Search results with pagination
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )

    # Build filters
    filters = []
    if job_title:
        filters.append(f"job_title:{job_title}")
    if job_category:
        filters.append(f"job_category:{job_category}")
    if min_impact_score is not None:
        filters.append(f"numeric_impact_score >= {min_impact_score}")
    if task_name:
        filters.append(f"task_names:{task_name}")
    if tool_name:
        filters.append(f"tool_names:{tool_name}")

    filter_str = " AND ".join(filters) if filters else ""

    # Determine sort order
    if sort_by == "impact_score":
        ranking = ["desc(numeric_impact_score)"]
    elif sort_by == "date":
        ranking = ["desc(created_at)"]
    else:  # relevance - use default Algolia ranking
        ranking = []

    # Perform the search
    try:
        index_name = algolia_config.tools_job_impacts_index_name
        search_params = {
            "page": page - 1,  # Algolia uses 0-based indexing
            "hitsPerPage": per_page,
            "filters": filter_str,
        }

        if ranking:
            search_params["customRanking"] = ranking

        result = algolia_config.client.search_single_index(
            index_name, query or "", search_params
        )

        # Extract the hits and metadata
        hits = result.get("hits", [])
        nbHits = result.get("nbHits", 0)
        nbPages = result.get("nbPages", 0)
        processingTimeMS = result.get("processingTimeMS", 0)

        return {
            "hits": hits,
            "page": page,
            "per_page": per_page,
            "total_hits": nbHits,
            "total_pages": nbPages,
            "processing_time_ms": processingTimeMS,
            "query": query,
            "filters": filter_str,
        }

    except Exception as e:
        logger.error(f"Error searching job impacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching job impacts: {str(e)}",
        )


@router.get("/direct-search/job-impacts", response_model=JobImpactSearchResult)
async def direct_search_job_impacts(
    query: Optional[str] = Query(None, description="Search query"),
    job_title: Optional[str] = Query(None, description="Filter by job title"),
    job_category: Optional[str] = Query(None, description="Filter by job category"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    min_impact_score: Optional[float] = Query(
        None, ge=0, le=100, description="Minimum impact score"
    ),
    task_name: Optional[str] = Query(None, description="Filter by task name"),
    tool_name: Optional[str] = Query(None, description="Filter by tool name"),
    page: int = Query(0, ge=0, description="Page number (0-based)"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    sort_by: str = Query(
        "impact_score",
        description="Sort order",
    ),
):
    """
    Direct search for job impacts in the Algolia index.
    
    This endpoint allows searching and filtering job impacts data by various criteria,
    similar to the /job-impacts endpoint but using the new direct search implementation.
    
    Args:
        query: General search query
        job_title: Filter by job title
        job_category: Filter by job category
        industry: Filter by industry
        min_impact_score: Filter by minimum impact score
        task_name: Filter by task name
        tool_name: Filter by tool name
        page: Page number (0-based)
        per_page: Number of results per page
        sort_by: Sort order (impact_score, relevance, date)
        
    Returns:
        JobImpactSearchResult with search results and pagination
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )
    
    try:
        # Perform the search using the new direct search method
        search_result = await algolia_search.direct_search_job_impacts(
            query=query,
            job_title=job_title,
            job_category=job_category, 
            industry=industry,
            min_impact_score=min_impact_score,
            task_name=task_name,
            tool_name=tool_name,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
        )
        
        return search_result
    
    except Exception as e:
        logger.error(f"Error searching job impacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching job impacts: {str(e)}",
        )


@router.post("/direct-search/job-impacts", response_model=JobImpactSearchResult)
async def direct_search_job_impacts_post(
    search_params: JobImpactSearchParams,
):
    """
    Direct search for job impacts with POST request.
    
    This endpoint is the POST version of the direct-search/job-impacts endpoint,
    allowing for more complex search parameters to be passed in the request body.
    
    Args:
        search_params: JobImpactSearchParams object containing search parameters
        
    Returns:
        JobImpactSearchResult with search results and pagination
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )
    
    try:
        # Perform the search using the new direct search method
        search_result = await algolia_search.direct_search_job_impacts(
            query=search_params.query,
            job_title=search_params.job_title,
            job_category=search_params.job_category,
            industry=search_params.industry,
            min_impact_score=search_params.min_impact_score,
            task_name=search_params.task_name,
            tool_name=search_params.tool_name,
            page=search_params.page - 1,  # Convert from 1-based to 0-based for Algolia
            per_page=search_params.per_page,
            sort_by=search_params.sort_by,
        )
        
        return search_result
    
    except Exception as e:
        logger.error(f"Error searching job impacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching job impacts: {str(e)}",
        )


@router.get("/job-impact-tools", response_model=JobImpactToolsSearchResult)
async def search_job_impacts_with_tools(
    job_title: str = Query(..., description="Job title to search for"),
    job_category: Optional[str] = Query(None, description="Filter by job category"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    min_impact_score: Optional[float] = Query(
        None, ge=0, le=100, description="Minimum impact score"
    ),
    page: int = Query(0, ge=0, description="Page number (0-based)"),
    per_page: int = Query(10, ge=1, le=20, description="Results per page"),
    sort_by: str = Query(
        "impact_score",
        description="Sort order (impact_score, relevance, date)",
    ),
):
    """
    Search for job impacts by job title and find relevant tools for each task.
    
    This endpoint implements a multi-step search flow:
    1. Find job impacts related to the specified job title
    2. For each job impact, extract the tasks
    3. For each task, find relevant tools from the tools index
    4. Return a combined result with job impacts and tools grouped by task
    
    Args:
        job_title: Job title to search for (e.g., "Software Engineer")
        job_category: Optional filter for job category
        industry: Optional filter for industry
        min_impact_score: Minimum impact score (0-100)
        page: Page number (0-based)
        per_page: Number of job impacts per page
        sort_by: Sort order (impact_score, relevance, date)
        
    Returns:
        JobImpactToolsSearchResult with job impacts and their associated tools
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )
    
    try:
        # Perform the multi-step search
        search_result = await algolia_search.search_job_impacts_with_tools(
            job_title=job_title,
            job_category=job_category,
            industry=industry,
            min_impact_score=min_impact_score,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
        )
        
        return search_result
    
    except Exception as e:
        logger.error(f"Error searching job impacts with tools: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching job impacts with tools: {str(e)}",
        )


@router.post("/job-impact-tools", response_model=JobImpactToolsSearchResult)
async def search_job_impacts_with_tools_post(
    search_params: JobImpactToolsSearchParams,
):
    """
    POST endpoint for searching job impacts with tools.
    
    This endpoint is the POST version of /job-impact-tools, accepting
    the search parameters in the request body instead of as query parameters.
    
    Args:
        search_params: JobImpactToolsSearchParams containing search parameters
        
    Returns:
        JobImpactToolsSearchResult with job impacts and their associated tools
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )
    
    try:
        # Perform the multi-step search
        search_result = await algolia_search.search_job_impacts_with_tools(
            job_title=search_params.job_title,
            job_category=search_params.job_category,
            industry=search_params.industry,
            min_impact_score=search_params.min_impact_score,
            page=search_params.page - 1,  # Convert from 1-based to 0-based
            per_page=search_params.per_page,
            sort_by=search_params.sort_by,
        )
        
        return search_result
    
    except Exception as e:
        logger.error(f"Error searching job impacts with tools: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching job impacts with tools: {str(e)}",
        )


@router.get("/task-tools/{task_name}", response_model=TaskToolsSearchResult)
async def search_tools_by_task(
    task_name: str,
    page: int = Query(0, ge=0, description="Page number (0-based)"),
    per_page: int = Query(10, ge=1, le=50, description="Results per page"),
):
    """
    Search for tools relevant to a specific task name.
    
    This endpoint allows finding tools that are relevant to a specific task,
    which is useful when users want to find tools for specific tasks without
    going through the job impacts.
    
    Args:
        task_name: Name of the task to find tools for
        page: Page number (0-based)
        per_page: Number of tools per page
        
    Returns:
        TaskToolsSearchResult containing the tools related to the task
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )
    
    try:
        # Perform the search
        search_result = await algolia_search.search_tools_by_task(
            task_name=task_name,
            page=page,
            per_page=per_page,
        )
        
        return search_result
    
    except Exception as e:
        logger.error(f"Error searching tools by task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching tools by task: {str(e)}",
        )


@router.get("/recommend-tools/{job_title}", response_model=JobToolsRecommendation)
async def recommend_tools_for_job(
    job_title: str,
    max_tasks: int = Query(5, ge=1, le=10, description="Maximum number of tasks to include"),
    max_tools_per_task: int = Query(3, ge=1, le=10, description="Maximum number of tools per task"),
):
    """
    One-stop endpoint for job-to-tasks-to-tools recommendations.
    
    This streamlined endpoint provides a complete workflow that:
    1. Takes a job title as input
    2. Finds AI impact information for that job
    3. Identifies key tasks affected by AI
    4. Recommends tools for each task
    5. Returns everything in a single, easy-to-use structure
    
    The response includes:
    - Job title, category, and industry
    - AI impact summary
    - Tasks with recommended tools for each
    - Counts of tasks and tools found
    
    Args:
        job_title: Job title to get tool recommendations for (e.g., "Software Engineer")
        max_tasks: Maximum number of tasks to include in the results
        max_tools_per_task: Maximum number of tools to recommend per task
        
    Returns:
        JobToolsRecommendation containing job information and recommended tools by task
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )
    
    try:
        # Get the job tools recommendation
        recommendation = await algolia_search.get_job_tools_recommendation(
            job_title=job_title,
            max_tasks=max_tasks,
            max_tools_per_task=max_tools_per_task,
        )
        
        # If no tasks found, provide a helpful error
        if not recommendation.tasks_with_tools:
            if job_title.strip():
                detail = f"No tasks or tools found for job title '{job_title}'. Try a different job title or check if the job impacts have been indexed."
            else:
                detail = "Job title cannot be empty. Please provide a valid job title."
                
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            )
        
        return recommendation
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        logger.error(f"Error recommending tools for job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error recommending tools for job: {str(e)}",
        )


@router.get("/direct-search/job-impacts/mock-test",response_model=JobImpactSearchResult)
async def mock_direct_search_job_impacts(query: Optional[str] = Query(None, description="Search query"),
    job_title: Optional[str] = Query(None, description="Filter by job title"),
    job_category: Optional[str] = Query(None, description="Filter by job category"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    min_impact_score: Optional[float] = Query(
        None, ge=0, le=100, description="Minimum impact score"
    ),
    task_name: Optional[str] = Query(None, description="Filter by task name"),
    tool_name: Optional[str] = Query(None, description="Filter by tool name"),
    page: int = Query(0, ge=0, description="Page number (0-based)"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    sort_by: str = Query(
        "impact_score",
        description="Sort order",
    ),
):
    """
    Direct search for job impacts in the Algolia index.
    
    This endpoint allows searching and filtering job impacts data by various criteria,
    similar to the /job-impacts endpoint but using the new direct search implementation.
    
    Args:
        query: General search query
        job_title: Filter by job title
        job_category: Filter by job category
        industry: Filter by industry
        min_impact_score: Filter by minimum impact score
        task_name: Filter by task name
        tool_name: Filter by tool name
        page: Page number (0-based)
        per_page: Number of results per page
        sort_by: Sort order (impact_score, relevance, date)
        
    Returns:
        JobImpactSearchResult with search results and pagination
    """
    # Validate Algolia configuration
    if not algolia_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )
    
    try:
        # Perform the search using the new direct search method
        search_result = await algolia_search.direct_search_job_impacts(
            query=query,
            job_title=job_title,
            job_category=job_category, 
            industry=industry,
            min_impact_score=min_impact_score,
            task_name=task_name,
            tool_name=tool_name,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
        )
        
        return search_result
    
    except Exception as e:
        logger.error(f"Error searching job impacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching job impacts: {str(e)}",
        )


@router.get("/job-impact-tools/mock-test", response_model=JobImpactToolsSearchResult)
async def mock_search_job_impacts_with_tools():
    """
    Mock API endpoint for testing job impact tools search.
    No authentication required.

    Returns:
        A sample JobImpactToolsSearchResult with mock data
    """
    # Create a sample job impact record
    sample_job_impact = AlgoliaJobImpactRecord(
        objectID="sample123",
        job_title="Software Engineer",
        job_category="Technology",
        industry="Software Development",
        description="A software engineer designs and develops software applications",
        ai_impact_score="High",
        numeric_impact_score=85.5,
        ai_impact_summary="AI will significantly impact this role through automation of routine coding tasks",
        detailed_analysis="Software engineers will need to adapt to working with AI pair programmers",
        tasks=[
            {"name": "Code writing", "impact": "High"},
            {"name": "Code review", "impact": "Medium"},
            {"name": "Testing", "impact": "Medium"}
        ],
        task_names=["Code writing", "Code review", "Testing"],
        tool_names=["GitHub Copilot", "ChatGPT", "Cursor IDE"],
        keywords=["software", "programming", "coding", "development"],
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        source_date=datetime.datetime.utcnow(),
        detail_page_link="/job-impacts/software-engineer"
    )
    
    # Create sample tools
    sample_tools = [
        AlgoliaToolRecord(
            objectID="tool1",
            name="GitHub Copilot",
            description="AI pair programmer that helps write better code faster",
            category="Development",
            is_featured=True,
            logo_url="https://example.com/copilot-logo.png"
        ),
        AlgoliaToolRecord(
            objectID="tool2",
            name="ChatGPT",
            description="Advanced language model for coding assistance and more",
            category="AI Assistants",
            is_featured=True,
            logo_url="https://example.com/chatgpt-logo.png"
        ),
        AlgoliaToolRecord(
            objectID="tool3",
            name="Cursor IDE",
            description="AI-native code editor built for pair programming",
            category="Development",
            is_featured=False,
            logo_url="https://example.com/cursor-logo.png"
        )
    ]
    
    # Create sample job impact with tools
    sample_impact_with_tools = JobImpactWithTools(
        job_impact=sample_job_impact,
        tools_by_task={
            "Code writing": [sample_tools[0], sample_tools[2]],
            "Code review": [sample_tools[1]],
            "Testing": [sample_tools[2]]
        }
    )
    
    return JobImpactToolsSearchResult(
        results=[sample_impact_with_tools],
        total=1,
        page=1,
        per_page=10,
        job_title="Software Engineer",
        processing_time_ms=25
    )
