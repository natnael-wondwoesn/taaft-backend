from pydantic import BaseModel, Field, ConfigDict, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from uuid import UUID, uuid4
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated


def validate_object_id(v) -> str:
    """
    Validate and convert various ID types to string.
    For ObjectId, converts to string.
    For UUID, converts to string.
    For string, returns as is if not a valid ObjectId.
    For string that is a valid ObjectId, returns as is.
    """
    if v is None:
        return v
    if isinstance(v, str):
        return v  # Return any string, valid ObjectId or not
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, UUID):
        return str(v)
    return str(v)  # Try to convert other types to string


PydanticObjectId = Annotated[ObjectId, BeforeValidator(validate_object_id)]


class ToolClickLogBase(BaseModel):
    """Base model for tool click logs."""
    tool_unique_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ToolClickLogCreate(ToolClickLogBase):
    """Model for creating a new tool click log."""
    pass


class ToolClickLog(ToolClickLogBase):
    """Tool click log with MongoDB-specific fields."""
    id_: Optional[str] = Field(alias="_id", default=None)
    user_id: Optional[str] = None

    @validator("id_", pre=True)
    def validate_id(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True, 
        populate_by_name=True,
        json_encoders={ObjectId: str}
    )


class ToolClickSummary(BaseModel):
    """Summary of tool clicks for a specific date."""
    date: str
    total_clicks: int
    clicks_by_tool: Dict[str, int]
    
    model_config = ConfigDict(arbitrary_types_allowed=True)