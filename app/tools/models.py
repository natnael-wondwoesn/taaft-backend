from pydantic import (
    BaseModel,
    Field,
    validator,
    ConfigDict,
    field_validator,
    root_validator,
    model_validator,
)
from typing import Optional, Dict, Any, ClassVar, Annotated, List, Union
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
    # Keyword support
    keywords: Optional[List[str]] = None
    categories: Optional[List[Dict[str, Any]]] = None

    # New Fields
    logo_url: Optional[str] = ""
    user_reviews: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None
    feature_list: Optional[List[str]] = []
    referral_allow: Optional[bool] = False
    generated_description: Optional[str] = None
    industry: Optional[str] = None
    image_url: Optional[str] = None
    carriers: Optional[List[str]] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("user_reviews")
    @classmethod
    def validate_user_reviews(cls, v):
        """Convert list of reviews to a dictionary if needed."""
        if isinstance(v, list):
            # Convert list to a dictionary with indices as keys
            return {str(i): review for i, review in enumerate(v)}
        return v


class ToolCreate(ToolBase):
    """Model for creating a new tool."""

    @model_validator(mode="before")
    @classmethod
    def handle_field_mappings(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map fields with spaces to their proper names.
        """
        if isinstance(data, dict):
            # Handle "saved numbers" vs "saved_numbers"
            if "saved numbers" in data:
                data["saved_numbers"] = data.pop("saved numbers")

            # Handle category_id vs category
            if "category_id" in data and "category" not in data:
                data["category"] = data.pop("category_id")

            # Ensure ID is a valid UUID
            if "id" not in data:
                data["id"] = str(uuid4())

        return data


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
    keywords: Optional[List[str]] = None
    categories: Optional[List[Dict[str, Any]]] = None
    logo_url: Optional[str] = None
    user_reviews: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None
    feature_list: Optional[List[str]] = None
    referral_allow: Optional[bool] = None
    generated_description: Optional[str] = None
    industry: Optional[str] = None
    carriers: Optional[List[str]] = None

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
    carriers: Optional[List[str]] = []

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: lambda oid: str(oid), UUID: lambda uuid: str(uuid)},
    )
