# app/algolia/models.py
"""
Data models for Algolia search integration
Defines schemas for tool indexing and search
"""
from enum import Enum
from typing import Dict, List, Optional, Any, Union
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
        if not ObjectId.is_valid(str(v)):
            raise ValueError("Invalid ObjectId")
        return str(v)  # Return string representation instead of ObjectId


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
    image_url: Optional[str] = None
    website: Optional[str] = None
    link: Optional[str] = None
    unique_id: Optional[str] = None
    categories: Optional[List[ToolCategory]] = None
    category_id: Optional[str] = None
    features: Optional[List[str]] = None
    use_cases: Optional[List[str]] = None
    keywords: Optional[List[str]] = None  # Keywords for searching
    pricing: Optional[ToolPricing] = None
    price: Optional[str] = None  # String representation of price
    pricing_url: Optional[str] = None
    ratings: Optional[ToolRatings] = None
    rating: Optional[float] = None  # Direct rating value
    saved_numbers: Optional[int] = None  # Number of times saved
    trending_score: Optional[float] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    is_featured: bool = False
    is_sponsored: bool = False

    model_config = {
        "allow_population_by_field_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {datetime.datetime: lambda dt: dt.isoformat(), ObjectId: str},
    }


# Define ToolRecord for backwards compatibility
ToolRecord = AlgoliaToolRecord


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
    """Search result model"""

    tools: List[Union[ToolRecord, AlgoliaToolRecord]]
    total: int
    page: int
    per_page: int
    pages: int
    processing_time_ms: int
    facets: Optional[SearchFacets] = None
    response_time: Optional[float] = None
    processed_query: Optional["ProcessedQuery"] = None

    model_config = {"arbitrary_types_allowed": True}


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

    # New fields based on updated prompt
    price_filter: Optional[str] = None
    rating_filter: Optional[float] = None
    min_rating: Optional[float] = (
        None  # Alias for rating_filter for backward compatibility
    )
