from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, Dict, Any, ClassVar, Annotated, List
from pydantic.functional_validators import BeforeValidator
from uuid import UUID, uuid4
import datetime
from bson import ObjectId


def validate_object_id(v: Any) -> ObjectId:
    if isinstance(v, ObjectId):
        return v
    if not ObjectId.is_valid(str(v)):
        raise ValueError("Invalid ObjectId")
    return ObjectId(str(v))


PydanticObjectId = Annotated[ObjectId, BeforeValidator(validate_object_id)]


class ToolBase(BaseModel):
    """Base model for tool schema."""

    id: UUID = Field(default_factory=uuid4)
    price: str
    name: str
    description: str
    link: str
    unique_id: str
    rating: Optional[str] = None
    saved_numbers: Optional[int] = None
    # New fields for UI
    category: Optional[str] = None
    features: Optional[List[str]] = None
    is_featured: bool = False
    saved_by_user: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ToolCreate(ToolBase):
    """Model for creating a new tool."""

    pass


class ToolUpdate(BaseModel):
    """Model for updating an existing tool."""

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

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ToolInDB(ToolBase):
    """Internal tool model with MongoDB-specific fields."""

    id_: Optional[PydanticObjectId] = Field(alias="_id", default=None)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class ToolResponse(ToolBase):
    """Public tool response model."""

    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: lambda oid: str(oid), UUID: lambda uuid: str(uuid)},
    )


class PaginatedToolsResponse(BaseModel):
    """Response model for paginated list of tools."""

    tools: List[ToolResponse]
    total: int
    skip: int
    limit: int

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: lambda oid: str(oid), UUID: lambda uuid: str(uuid)},
    )
