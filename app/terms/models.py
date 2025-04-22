# app/terms/models.py
"""
Data models for the terms feature
Defines schemas for term definitions and LLM interactions
"""
from enum import Enum
from typing import Dict, List, Optional, Union, Any, Annotated
from pydantic import BaseModel, Field, BeforeValidator
import datetime
from bson import ObjectId


# Custom ObjectId field for Pydantic v2
def validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    if ObjectId.is_valid(v):
        return str(v)
    raise ValueError("Invalid ObjectId")


PydanticObjectId = Annotated[str, BeforeValidator(validate_object_id)]


# Enums for term system
class TermModelType(str, Enum):
    GPT_4 = "gpt4"
    CLAUDE = "claude"
    LLAMA = "llama"
    DEFAULT = "default"


# Term definition models
class TermDefinitionRequest(BaseModel):
    term: str
    user_id: Optional[str] = None
    model: Optional[TermModelType] = TermModelType.DEFAULT


class TermDefinitionResponse(BaseModel):
    term: str
    description: str
    examples: List[str]
    id: str
    timestamp: datetime.datetime
    model: TermModelType


class TermDefinition(BaseModel):
    id: Optional[PydanticObjectId] = Field(alias="_id", default=None)
    term: str
    description: str
    examples: List[str]
    user_id: Optional[str] = None
    timestamp: Optional[datetime.datetime] = None
    model: TermModelType = TermModelType.DEFAULT
    metadata: Optional[Dict[str, Any]] = None

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "term": "Machine Learning",
                "description": "A field of AI that enables systems to learn from data without explicit programming.",
                "examples": [
                    "Image recognition",
                    "Recommendation systems",
                    "Fraud detection",
                ],
                "user_id": "user123",
                "timestamp": "2023-04-01T12:00:00Z",
                "model": "gpt4",
            }
        },
    }

    def model_dump(self, **kwargs):
        kwargs.pop("exclude_none", None)
        dump = super().model_dump(**kwargs)
        if "_id" in dump and dump["_id"] is not None:
            dump["_id"] = str(dump["_id"])
        return dump


class PopularTerm(BaseModel):
    term: str
    count: int
    last_requested: datetime.datetime
