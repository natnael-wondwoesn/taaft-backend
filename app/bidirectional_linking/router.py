from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import List, Optional, Dict, Any
from ..blog.database import BlogDB, get_blog_db
from ..glossary.database import GlossaryDB, get_glossary_db
from .database import LinkingDB, get_linking_db
from ..models.bidirectional_linking import (
    GlossaryTermSummary,
    BlogArticleSummary,
    BlogArticlesForTermResponse,
    GlossaryTermsListResponse,
    GlossaryTermWithArticlesCount,
)
from bson import ObjectId


router = APIRouter(
    prefix="/linking",
    tags=["bidirectional_linking"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/terms/{term_id}/articles",
    response_model=BlogArticlesForTermResponse,
    summary="Get blog articles related to a glossary term",
)
async def get_articles_for_term(
    term_id: str = Path(..., description="ID of the glossary term"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of items to return"),
    blog_db: BlogDB = Depends(get_blog_db),
    glossary_db: GlossaryDB = Depends(get_glossary_db),
):
    """
    Get blog articles related to a specific glossary term.
    Returns the term details and a list of related articles.
    Optimized for frontend consumption with appropriate data structure.
    """
    # Check if the glossary term exists
    term = await glossary_db.get_term_by_id(term_id)
    if not term:
        raise HTTPException(status_code=404, detail="Glossary term not found")

    # Get related articles
    articles = await blog_db.get_articles_by_glossary_term(
        term_id=term_id, skip=skip, limit=limit
    )

    # Get total count for pagination
    total_count = await blog_db.count_articles(
        filter_query={"related_glossary_terms": str(term_id)}
    )

    # Format term summary
    term_summary = GlossaryTermSummary(
        id=str(term["_id"]),
        name=term["name"],
        slug=term.get("slug", ""),
        short_definition=term.get("short_definition", ""),
    )

    # Format article summaries
    article_summaries = []
    for article in articles:
        # Create a preview of the body text
        body_preview = (
            article.get("body", "")[:150] + "..." if article.get("body") else None
        )

        article_summaries.append(
            BlogArticleSummary(
                id=str(article["_id"]),
                title=article["title"],
                url=article.get("url"),
                body_preview=body_preview,
                images=article.get("images", []),
            )
        )

    return BlogArticlesForTermResponse(
        term=term_summary,
        articles=article_summaries,
        total_count=total_count,
    )


@router.get(
    "/terms",
    response_model=GlossaryTermsListResponse,
    summary="Get a list of glossary terms with slugs and short definitions",
)
async def get_glossary_terms_list(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of items to return"),
    search: Optional[str] = Query(None, description="Search text in name"),
    include_article_counts: bool = Query(
        False, description="Include count of related articles for each term"
    ),
    glossary_db: GlossaryDB = Depends(get_glossary_db),
    blog_db: BlogDB = Depends(get_blog_db),
):
    """
    Get a list of glossary terms with their slug and short definition.
    Optimized for frontend consumption with a simplified structure.
    Supports optional search functionality and can include article counts.
    """
    from ..models.glossary import GlossaryTermFilter

    # Build filter
    filter_params = None
    if search:
        filter_params = GlossaryTermFilter(search=search)

    # Get terms
    terms = await glossary_db.list_terms(
        filter_params=filter_params,
        skip=skip,
        limit=limit,
        sort_by="name",
    )

    # Get total count for pagination
    total_count = await glossary_db.count_terms(filter_params=filter_params)

    # Format the response
    result = []
    for term in terms:
        term_summary = None

        if include_article_counts:
            # Count related articles
            article_count = await blog_db.count_articles(
                filter_query={"related_glossary_terms": str(term["_id"])}
            )

            term_summary = GlossaryTermWithArticlesCount(
                id=str(term["_id"]),
                name=term["name"],
                slug=term.get("slug", ""),
                short_definition=term.get("short_definition", ""),
                article_count=article_count,
            )
        else:
            term_summary = GlossaryTermSummary(
                id=str(term["_id"]),
                name=term["name"],
                slug=term.get("slug", ""),
                short_definition=term.get("short_definition", ""),
            )

        result.append(term_summary)

    return GlossaryTermsListResponse(
        terms=result,
        total_count=total_count,
    )


@router.get(
    "/static-mapping",
    response_model=Dict[str, Any],
    summary="Get a static mapping of terms to articles and vice versa",
)
async def get_static_mapping(
    linking_db: LinkingDB = Depends(get_linking_db),
):
    """
    Generate a static mapping of terms to articles and articles to terms.
    This can be used for frontend caching or static site generation.

    The response includes two mappings:
    - terms_to_articles: Maps term IDs to their details and related article IDs
    - articles_to_terms: Maps article IDs to their details and related term IDs

    This endpoint is optimized for bulk data retrieval and can be cached
    on the client side for improved performance.
    """
    mapping = await linking_db.generate_static_mapping()
    return mapping


@router.post(
    "/cache/enable", status_code=200, summary="Enable caching for bidirectional linking"
)
async def enable_cache():
    """Enable the caching for bidirectional linking to improve performance."""
    LinkingDB.enable_cache()
    return {"status": "success", "message": "Cache enabled"}


@router.post(
    "/cache/disable",
    status_code=200,
    summary="Disable caching for bidirectional linking",
)
async def disable_cache():
    """Disable the caching for bidirectional linking."""
    LinkingDB.disable_cache()
    return {"status": "success", "message": "Cache disabled and cleared"}


@router.post(
    "/cache/clear", status_code=200, summary="Clear the bidirectional linking cache"
)
async def clear_cache():
    """Clear the bidirectional linking cache."""
    LinkingDB.clear_cache()
    return {"status": "success", "message": "Cache cleared"}
