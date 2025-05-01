from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId


class BlogArticleBase(BaseModel):
    """Base model for blog articles."""

    title: str
    slug: str
    content: str
    summary: str
    author: str
    published_date: datetime
    last_updated: Optional[datetime] = None
    tags: List[str] = []
    related_glossary_terms: List[str] = []  # List of glossary term IDs


class BlogArticleCreate(BlogArticleBase):
    """Model for creating a blog article."""

    pass


class BlogArticleUpdate(BaseModel):
    """Model for updating a blog article."""

    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    last_updated: Optional[datetime] = None
    tags: Optional[List[str]] = None
    related_glossary_terms: Optional[List[str]] = None


class BlogArticleResponse(BlogArticleBase):
    """Model for returning a blog article."""

    id: str

    class Config:
        from_attributes = True


class BlogArticleWithGlossaryTerms(BlogArticleResponse):
    """Model for returning a blog article with related glossary terms."""

    related_glossary_term_details: List[dict] = []


class RelatedBlogArticle(BaseModel):
    """Model for returning a simplified blog article for relation purposes."""

    id: str
    title: str
    slug: str
    summary: str
    published_date: datetime
