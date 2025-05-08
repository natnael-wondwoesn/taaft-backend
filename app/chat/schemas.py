from pydantic import BaseModel
from typing import List, Optional


class UserProfile(BaseModel):
    industry: Optional[str] = None
    business_size: Optional[str] = None
    challenges: Optional[List[str]] = None


class ChatResponse(BaseModel):
    message: str
    options: List[str]
    keywords: Optional[List[str]] = None
    tool_summary: Optional[List[dict]] = None
