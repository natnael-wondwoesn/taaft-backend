from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from enum import Enum
import datetime
from bson import ObjectId


class GlossaryTerm(BaseModel):
    """Model for glossary terms."""

    id: Optional[ObjectId] = Field(alias="_id", default=None)
    name: str = Field(..., description="The name/title of the glossary term")
    definition: str = Field(..., description="Detailed definition of the term")
    related_terms: List[str] = Field(
        default_factory=list, description="List of related term names"
    )
    tool_references: List[str] = Field(
        default_factory=list,
        description="List of tool IDs that are related to this term",
    )
    categories: List[str] = Field(
        default_factory=list, description="Categories this term belongs to"
    )
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    @validator("name")
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @validator("definition")
    def definition_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Definition cannot be empty")
        return v.strip()

    model_config = {"arbitrary_types_allowed": True, "json_encoders": {ObjectId: str}}


class GlossaryTermResponse(BaseModel):
    """Public glossary term response model."""

    id: str
    name: str
    definition: str
    related_terms: List[str] = []
    tool_references: List[str] = []
    categories: List[str] = []
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"json_encoders": {ObjectId: lambda oid: str(oid)}}


class GlossaryTermCreate(BaseModel):
    """Model for creating a new glossary term."""

    name: str
    definition: str
    related_terms: List[str] = []
    tool_references: List[str] = []
    categories: List[str] = []


class GlossaryTermUpdate(BaseModel):
    """Model for updating a glossary term."""

    name: Optional[str] = None
    definition: Optional[str] = None
    related_terms: Optional[List[str]] = None
    tool_references: Optional[List[str]] = None
    categories: Optional[List[str]] = None


class GlossaryTermFilter(BaseModel):
    """Model for filtering glossary terms."""

    category: Optional[str] = None
    search: Optional[str] = None
