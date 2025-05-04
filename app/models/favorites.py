from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from uuid import UUID, uuid4
import datetime
from bson import ObjectId
from .user import PydanticObjectId


class FavoriteCreate(BaseModel):
    """Model for creating a favorite."""

    tool_unique_id: str


class FavoriteBase(BaseModel):
    """Base model for favorites."""

    user_id: str
    tool_unique_id: str
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class FavoriteInDB(FavoriteBase):
    """Internal model for favorites stored in DB."""

    id_: Optional[PydanticObjectId] = Field(alias="_id", default=None)


class FavoriteResponse(FavoriteBase):
    """Public response model for favorites."""

    id: str

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: lambda oid: str(oid), UUID: lambda uuid: str(uuid)},
    )


class FavoritesListResponse(BaseModel):
    """Response model for paginated list of favorites."""

    favorites: List[FavoriteResponse]
    total: int
    skip: int
    limit: int

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: lambda oid: str(oid), UUID: lambda uuid: str(uuid)},
    )
