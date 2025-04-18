# app/algolia/models.py
"""
Data models for Algolia search integration
Defines schemas for tool indexing and search
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, HttpUrl
import datetime
from bson import ObjectId


# Custom ObjectId field for Pydantic
class PydanticObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


# Models for Algolia indexing
class PricingType(str, Enum):
    FREE = "Free"
    FREEMIUM = "Freemium"
    PAID = "Paid"
    ENTERPRISE = "Enterprise"
    CONTACT = "Contact"


class ToolCategory(BaseModel):
    id: str
    name: str
    slug: str


class ToolPricingPlan(BaseModel):
    name: str
    price: str
    billing_cycle: Optional[str] = None
    features: Optional[List[str]] = None


class ToolPricing(BaseModel):
    type: PricingType
    starting_at: Optional[str] = None
    plans: Optional[List[ToolPricingPlan]] = None


class ToolRatings(BaseModel):
    average: float = 0.0
    count: int = 0


class AlgoliaToolRecord(BaseModel):
    """Model for a tool record to be indexed in Algolia"""

    objectID: str  # Required by Algolia, will be the MongoDB _id
    name: str
    description: str
    slug: str
    long_description: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    categories: Optional[List[ToolCategory]] = None
    features: Optional[List[str]] = None
    use_cases: Optional[List[str]] = None
    pricing: Optional[ToolPricing] = None
    ratings: Optional[ToolRatings] = None
    trending_score: Optional[float] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    is_featured: bool = False
    is_sponsored: bool = False

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {datetime.datetime: lambda dt: dt.isoformat(), ObjectId: str}


# Models for search
class SearchParams(BaseModel):
    """Parameters for search operations"""

    query: str
    categories: Optional[List[str]] = None
    pricing_types: Optional[List[PricingType]] = None
    min_rating: Optional[float] = None
    page: int = 1
    per_page: int = 20
    sort_by: Optional[str] = None  # relevance, newest, trending
    filters: Optional[str] = None  # Algolia filter query string


class SearchFacet(BaseModel):
    """Facet result from Algolia"""

    name: str
    count: int


class SearchFacets(BaseModel):
    """Facets for filtering search results"""

    categories: List[SearchFacet] = []
    pricing_types: List[SearchFacet] = []


class SearchResult(BaseModel):
    """Result model for search operations"""

    tools: List[AlgoliaToolRecord]
    total: int
    page: int
    per_page: int
    pages: int
    facets: Optional[SearchFacets] = None
    processing_time_ms: Optional[int] = None


# Models for natural language processing
class NaturalLanguageQuery(BaseModel):
    """Natural language query input"""

    question: str
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ProcessedQuery(BaseModel):
    """Processed natural language query"""

    original_question: str
    search_query: str
    filters: Optional[str] = None
    categories: Optional[List[str]] = None
    pricing_types: Optional[List[PricingType]] = None
    interpreted_intent: Optional[str] = None
