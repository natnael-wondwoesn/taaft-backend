from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from enum import Enum
import datetime
from bson import ObjectId


class PydanticObjectId(str):
    """Custom ObjectId field for Pydantic models."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(str(v)):
            raise ValueError("Invalid ObjectId")
        return ObjectId(str(v))


class ServiceTier(str, Enum):
    """Enum representing different service tiers."""

    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class TierLimits(BaseModel):
    """Model for defining tier-specific limits."""

    max_requests_per_day: int
    max_tokens_per_request: int
    max_storage_mb: int
    features: List[str]


class UserCreate(BaseModel):
    """Model for user creation."""

    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @validator("password")
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        # Add more validations as needed
        return v


class UserUpdate(BaseModel):
    """Model for user updates."""

    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    service_tier: Optional[ServiceTier] = None


class UserInDB(BaseModel):
    """Internal user model with hashed password."""

    id: Optional[PydanticObjectId] = Field(alias="_id", default=None)
    email: EmailStr
    hashed_password: str
    full_name: Optional[str] = None
    service_tier: ServiceTier = ServiceTier.FREE
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    last_login: Optional[datetime.datetime] = None
    usage: dict = Field(
        default_factory=lambda: {
            "requests_today": 0,
            "requests_reset_date": datetime.datetime.utcnow(),
            "total_requests": 0,
            "storage_used_bytes": 0,
        }
    )


class UserResponse(BaseModel):
    """Public user response model (without sensitive data)."""

    id: str
    email: EmailStr
    full_name: Optional[str] = None
    service_tier: ServiceTier
    is_active: bool
    is_verified: bool
    created_at: datetime.datetime
    usage: dict

    class Config:
        json_encoders = {ObjectId: lambda oid: str(oid)}


class TokenData(BaseModel):
    """Model for JWT token data."""

    sub: str  # User ID
    exp: datetime.datetime
    service_tier: ServiceTier
    is_verified: bool
