from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from uuid import UUID, uuid4
import datetime
from bson import ObjectId
from .user import PydanticObjectId


class ShareCreate(BaseModel):
    """Model for creating a share."""

    tool_unique_id: str


class ShareBase(BaseModel):
    """Base model for shares."""

    user_id: str
    tool_unique_id: str
    share_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ShareInDB(ShareBase):
    """Internal model for shares stored in DB."""

    id_: Optional[PydanticObjectId] = Field(alias="_id", default=None)


class ShareResponse(ShareBase):
    """Public response model for shares."""

    id: str
    share_link: str

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: lambda oid: str(oid), UUID: lambda uuid: str(uuid)},
    )


class SharesListResponse(BaseModel):
    """Response model for paginated list of shares."""

    shares: List[ShareResponse]
    total: int
    skip: int
    limit: int

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: lambda oid: str(oid), UUID: lambda uuid: str(uuid)},
    )
