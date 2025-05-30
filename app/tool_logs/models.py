from pydantic import BaseModel, Field, ConfigDict, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from uuid import UUID, uuid4
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated


def validate_object_id(v) -> str:
    if v is None:
        return v
    if isinstance(v, str):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return v
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, UUID):
        return str(v)
    raise ValueError("Invalid ObjectId")


PydanticObjectId = Annotated[ObjectId, BeforeValidator(validate_object_id)]


class ToolClickLogBase(BaseModel):
    """Base model for tool click logs."""
    tool_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ToolClickLogCreate(ToolClickLogBase):
    """Model for creating a new tool click log."""
    pass


class ToolClickLog(ToolClickLogBase):
    """Tool click log with MongoDB-specific fields."""
    id_: Optional[str] = Field(alias="_id", default=None)
    user_id: Optional[str] = None

    _validate_id = validator("id_", allow_reuse=True)(validate_object_id)
    
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)


class ToolClickSummary(BaseModel):
    """Summary of tool clicks for a specific date."""
    date: str
    total_clicks: int
    clicks_by_tool: Dict[str, int]
    
    model_config = ConfigDict(arbitrary_types_allowed=True)