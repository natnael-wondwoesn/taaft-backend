"""
Data models for categories management
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from bson import ObjectId


class PydanticObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(str(v)):
            raise ValueError("Invalid ObjectId")
        return str(v)  # Return string representation instead of ObjectId


class Category(BaseModel):
    """Base category model"""

    id: str
    name: str
    slug: str
    svg: Optional[str] = Field(
        None,
        description="Path to the category's SVG icon file. If None, no icon is available.",
    )


class CategoryResponse(Category):
    """Category model with count information"""

    count: int = Field(
        0,
        description="Number of tools in this category",
    )
