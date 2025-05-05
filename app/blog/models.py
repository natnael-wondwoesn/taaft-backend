from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId


class BlogArticleBase(BaseModel):
    """Base model for blog articles."""

    title: str
    url: Optional[str] = None
    body: str
    images: List[str] = []
    related_glossary_terms: List[str] = []  # List of glossary term IDs


class BlogArticleCreate(BlogArticleBase):
    """Model for creating a blog article."""

    pass


class BlogArticleUpdate(BaseModel):
    """Model for updating a blog article."""

    title: Optional[str] = None
    url: Optional[str] = None
    body: Optional[str] = None
    images: Optional[List[str]] = None
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
    url: Optional[str] = None
    body_preview: Optional[str] = None  # A truncated version of the body for previews
    images: List[str] = []
