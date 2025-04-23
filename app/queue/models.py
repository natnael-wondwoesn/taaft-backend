import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Annotated, Any
from pydantic import BaseModel, Field, HttpUrl, BeforeValidator
from bson import ObjectId


# Custom ObjectId field for Pydantic
def validate_object_id(v) -> str:
    if not ObjectId.is_valid(v):
        raise ValueError("Invalid ObjectId")
    return str(v)


PydanticObjectId = Annotated[str, BeforeValidator(validate_object_id)]


# Enums for site management
class SitePriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SiteStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    PENDING = "pending"


# Models for Sites (without tool-specific fields)
class SiteBase(BaseModel):
    name: str
    url: HttpUrl
    priority: SitePriority
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    # We don't include price, rating, etc. here as they're tool-specific


class SiteCreate(SiteBase):
    pass


class Site(SiteBase):
    id: Optional[str] = Field(default=None)
    created_at: Optional[datetime.datetime] = None
    last_updated_at: Optional[datetime.datetime] = None
    status: SiteStatus = SiteStatus.PENDING

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "name": "Example Site",
                "url": "https://example.com",
                "priority": "medium",
                "status": "active",
                "description": "An example site",
                "category": "Technology",
                "tags": ["tech", "news"],
            }
        }


class SiteUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    priority: Optional[SitePriority] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[SiteStatus] = None


class SiteResponse(BaseModel):
    total: int
    sites: List[Site]


# Model for sites in n8n compatible format
class N8nSiteFormat(BaseModel):
    _id: Dict[str, str]  # {"$oid": "..."}
    link: str
    category_id: str = ""
