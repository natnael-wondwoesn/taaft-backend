from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class GlossaryTermSummary(BaseModel):
    """Model for a simplified glossary term to be used in listings."""

    id: str
    name: str
    slug: str
    short_definition: str = ""


class BlogArticleSummary(BaseModel):
    """Model for a simplified blog article to be used in listings."""

    id: str
    title: str
    url: Optional[str] = None
    body_preview: Optional[str] = None  # First 100-150 characters of the body
    images: List[str] = []


class BlogArticlesForTermResponse(BaseModel):
    """Model for returning blog articles related to a glossary term."""

    term: GlossaryTermSummary
    articles: List[BlogArticleSummary]
    total_count: int


class GlossaryTermsListResponse(BaseModel):
    """Model for returning a list of glossary terms with their slugs and definitions."""

    terms: List[GlossaryTermSummary]
    total_count: int


class GlossaryTermWithArticlesCount(GlossaryTermSummary):
    """Glossary term with count of related articles."""

    article_count: int = 0
