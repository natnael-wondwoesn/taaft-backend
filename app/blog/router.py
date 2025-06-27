from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import List, Optional
from .database import BlogDB, get_blog_db
from .models import (
    BlogArticleResponse,
    BlogArticleWithGlossaryTerms,
    RelatedBlogArticle,
)
from ..glossary.database import GlossaryDB, get_glossary_db
from bson import ObjectId
from pymongo import DESCENDING

router = APIRouter(
    prefix="/blog",
    tags=["blog"],
    responses={404: {"description": "Not found"}},
)


@router.get("/articles", response_model=List[BlogArticleResponse])
async def list_blog_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("_id", description="Field to sort by"),
    sort_desc: bool = Query(True, description="Sort in descending order"),
    blog_db: BlogDB = Depends(get_blog_db),
):
    """
    List blog articles with pagination and sorting.
    No authentication required (free tier access).
    """
    sort_order = DESCENDING if sort_desc else 1

    articles = await blog_db.list_articles(
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Convert the _id to string
    for article in articles:
        article["id"] = str(article.pop("_id"))

    return articles


@router.get("/articles/{article_id}", response_model=BlogArticleWithGlossaryTerms)
async def get_blog_article(
    article_id: str = Path(..., description="ID of the blog article"),
    blog_db: BlogDB = Depends(get_blog_db),
    glossary_db: GlossaryDB = Depends(get_glossary_db),
):
    """
    Get a specific blog article by ID with related glossary terms.
    No authentication required (free tier access).
    """
    article = await blog_db.get_article_by_id(article_id)

    if not article:
        raise HTTPException(status_code=404, detail="Blog article not found")

    # Convert the _id to string
    article["id"] = str(article.pop("_id"))

    # Get related glossary terms if any
    related_terms = []
    if "related_glossary_terms" in article and article["related_glossary_terms"]:
        for term_id in article["related_glossary_terms"]:
            term = await glossary_db.get_term_by_id(term_id)
            if term:
                # Convert _id to string
                term["id"] = str(term.pop("_id"))
                # Add only essential fields
                related_terms.append(
                    {
                        "id": term["id"],
                        "name": term["name"],
                        "slug": term.get("slug", ""),
                        "short_definition": term.get("short_definition", ""),
                    }
                )

    article["related_glossary_term_details"] = related_terms

    return article


@router.get("/by-term/{term_id}", response_model=List[RelatedBlogArticle])
async def get_blog_articles_by_glossary_term(
    term_id: str = Path(..., description="ID of the glossary term"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    blog_db: BlogDB = Depends(get_blog_db),
    glossary_db: GlossaryDB = Depends(get_glossary_db),
):
    """
    Get blog articles related to a specific glossary term.
    No authentication required (free tier access).
    """
    # Check if the glossary term exists
    term = await glossary_db.get_term_by_id(term_id)
    if not term:
        raise HTTPException(status_code=404, detail="Glossary term not found")

    articles = await blog_db.get_articles_by_glossary_term(
        term_id=term_id,
        skip=skip,
        limit=limit,
    )

    # Format the response
    formatted_articles = []
    for article in articles:
        # Create a preview of the body text
        body_preview = (
            article.get("body", "")[:150] + "..." if article.get("body") else None
        )

        formatted_articles.append(
            {
                "id": str(article["_id"]),
                "title": article["title"],
                "url": article.get("url", ""),
                "body_preview": body_preview,
                "images": article.get("images", []),
            }
        )

    return formatted_articles


@router.get("/glossary-terms", response_model=List[dict])
async def get_glossary_terms_list(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None, description="Search text in name"),
    glossary_db: GlossaryDB = Depends(get_glossary_db),
):
    """
    Get a list of glossary terms with slug and short definition.
    Optimized for frontend consumption.
    No authentication required (free tier access).
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

    # Format the response for frontend consumption
    formatted_terms = []
    for term in terms:
        formatted_terms.append(
            {
                "id": str(term["_id"]),
                "name": term["name"],
                "slug": term.get("slug", ""),
                "short_definition": term.get("short_definition", ""),
            }
        )

    return formatted_terms


@router.post("/articles/{article_id}/glossary-terms", response_model=dict)
async def update_article_glossary_terms(
    article_id: str = Path(..., description="ID of the blog article"),
    term_ids: List[str] = Query(..., description="IDs of glossary terms to link"),
    blog_db: BlogDB = Depends(get_blog_db),
):
    """
    Update the glossary terms linked to a specific blog article.
    This enables bidirectional linking between blog articles and glossary terms.
    """
    # Verify the article exists
    article = await blog_db.get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Blog article not found")

    # Update the article's related_glossary_terms field
    success = await blog_db.update_article_glossary_terms(article_id, term_ids)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to update related glossary terms for this article",
        )

    return {
        "status": "success",
        "message": "Successfully updated related glossary terms",
        "article_id": article_id,
        "term_ids": term_ids,
    }
