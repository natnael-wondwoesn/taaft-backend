# app/chat/models.py
"""
Data models for the chat feature
Defines schemas for chat sessions, messages, and LLM interactions
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


# Enums for chat system
class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatModelType(str, Enum):
    GPT_4 = "gpt4"
    CLAUDE = "claude"
    LLAMA = "llama"
    DEFAULT = "default"


# Message models
class MessageBase(BaseModel):
    role: MessageRole
    content: str
    timestamp: Optional[datetime.datetime] = None


class MessageCreate(MessageBase):
    pass


class Message(MessageBase):
    id: Optional[PydanticObjectId] = Field(alias="_id", default=None)
    chat_id: PydanticObjectId
    metadata: Optional[Dict[str, Any]] = None

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "chat_id": "507f1f77bcf86cd799439012",
                "role": "user",
                "content": "Hello!",
                "timestamp": "2023-04-01T12:00:00Z",
                "metadata": {"client": "web"},
            }
        },
    }

    def model_dump(self, **kwargs):
        kwargs.pop("exclude_none", None)
        dump = super().model_dump(**kwargs)
        if "_id" in dump and dump["_id"] is not None:
            dump["_id"] = str(dump["_id"])
        if "chat_id" in dump and dump["chat_id"] is not None:
            dump["chat_id"] = str(dump["chat_id"])
        return dump


# Chat session models
class ChatSessionBase(BaseModel):
    title: Optional[str] = "New Chat"
    user_id: Optional[str] = None
    model: ChatModelType = ChatModelType.DEFAULT
    system_prompt: Optional[str] = None


class ChatSessionCreate(ChatSessionBase):
    pass


class ChatSession(ChatSessionBase):
    id: Optional[PydanticObjectId] = Field(alias="_id", default=None)
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    message_count: int = 0
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "title": "Discussion about AI",
                "user_id": "user123",
                "model": "gpt4",
                "created_at": "2023-04-01T12:00:00Z",
                "updated_at": "2023-04-01T12:30:00Z",
                "message_count": 10,
                "is_active": True,
            }
        },
    }

    def model_dump(self, **kwargs):
        kwargs.pop("exclude_none", None)
        dump = super().model_dump(**kwargs)
        if "_id" in dump and dump["_id"] is not None:
            dump["_id"] = str(dump["_id"])
        return dump


# Models for API interactions
class ChatMessageRequest(BaseModel):
    """Request for sending a chat message"""

    message: str
    model: Optional[ChatModelType] = None
    system_prompt: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatMessageResponse(BaseModel):
    """Response for a chat message"""

    message: str
    chat_id: str
    message_id: str
    timestamp: datetime.datetime
    model: ChatModelType
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {
            datetime.datetime: lambda dt: dt.isoformat(),
            ObjectId: lambda oid: str(oid),
        }
