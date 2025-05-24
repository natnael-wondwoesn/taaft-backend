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
    price: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    link: Optional[str] = None
    unique_id: Optional[str] = None
    rating: Optional[str] = None
    saved_numbers: Optional[int] = None
    category: Optional[str] = None
    features: Optional[List[str]] = None
    is_featured: Optional[bool] = None
    keywords: Optional[List[str]] = None
    categories: Optional[List[Dict[str, Any]]] = None
    logo_url: Optional[str] = None
    user_reviews: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None
    feature_list: Optional[List[str]] = None
    referral_allow: Optional[bool] = None
    generated_description: Optional[str] = None
    industry: Optional[str] = None
    carriers: Optional[List[str]] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

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


class AlgoliaJobImpactRecord(BaseModel):
    """Model for a job impact record to be indexed in Algolia"""

    objectID: str  # Required by Algolia, will be the MongoDB _id
    job_title: Optional[str] = None
    job_category: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    ai_impact_score: Optional[str] = None
    numeric_impact_score: Optional[float] = None
    ai_impact_summary: Optional[str] = None
    detailed_analysis: Optional[str] = None
    tasks: Optional[List[Dict[str, Any]]] = None
    task_names: Optional[List[str]] = None
    tool_names: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    source_date: Optional[datetime.datetime] = None
    detail_page_link: Optional[str] = None

    model_config = {
        "allow_population_by_field_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {datetime.datetime: lambda dt: dt.isoformat(), ObjectId: str},
    }


class JobImpactSearchResult(BaseModel):
    """Search result model for job impacts"""

    job_impacts: List[AlgoliaJobImpactRecord]
    total: int
    page: int
    per_page: int
    pages: int
    processing_time_ms: int
    facets: Optional[SearchFacets] = None
    response_time: Optional[float] = None

    model_config = {"arbitrary_types_allowed": True}


class JobImpactSearchParams(BaseModel):
    """Parameters for job impact search operations"""

    query: Optional[str] = None
    job_title: Optional[str] = None
    job_category: Optional[str] = None
    industry: Optional[str] = None
    min_impact_score: Optional[float] = None
    task_name: Optional[str] = None
    tool_name: Optional[str] = None
    page: int = 1
    per_page: int = 20
    sort_by: str = "impact_score"  # impact_score, relevance, date


class JobImpactWithTools(BaseModel):
    """Model representing a job impact with associated tools"""
    
    job_impact: AlgoliaJobImpactRecord
    tools_by_task: Dict[str, List[AlgoliaToolRecord]] = Field(default_factory=dict)


class JobImpactToolsSearchResult(BaseModel):
    """Search result model for job impacts with tools for each task"""
    
    results: List[JobImpactWithTools]
    total: int
    page: int
    per_page: int
    job_title: Optional[str] = None
    processing_time_ms: int
    
    model_config = {"arbitrary_types_allowed": True}


class JobImpactToolsSearchParams(BaseModel):
    """Parameters for job impact and tools search operation"""
    
    job_title: str
    job_category: Optional[str] = None
    industry: Optional[str] = None
    min_impact_score: Optional[float] = None
    page: int = 1
    per_page: int = 10
    sort_by: str = "impact_score"  # impact_score, relevance, date


class TaskToolsSearchResult(BaseModel):
    """Search result model for tools by task name"""
    
    task_name: str
    tools: List[AlgoliaToolRecord]
    total: int
    page: int
    per_page: int
    processing_time_ms: int
    
    model_config = {"arbitrary_types_allowed": True}


class TaskWithTools(BaseModel):
    """Task with recommended tools"""
    task_name: str
    tools: List[AlgoliaToolRecord]
    tool_count: int = 0


class JobToolsRecommendation(BaseModel):
    """Simplified job-to-tools recommendation model"""
    job_title: str
    job_category: Optional[str] = None
    industry: Optional[str] = None
    ai_impact_score: Optional[str] = None
    ai_impact_summary: Optional[str] = None
    tasks_with_tools: List[TaskWithTools] = Field(default_factory=list)
    task_count: int = 0
    total_tool_count: int = 0
    processing_time_ms: int = 0
    
    model_config = {"arbitrary_types_allowed": True}
