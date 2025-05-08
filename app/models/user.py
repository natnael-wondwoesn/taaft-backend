from pydantic import BaseModel, EmailStr, Field, validator, BeforeValidator
from typing import Optional, List, Dict, Any, ClassVar, Annotated
from enum import Enum
import datetime
from bson import ObjectId
from pydantic.json_schema import JsonSchemaMode
from bson.objectid import ObjectId


class PydanticObjectId(str):
    """Custom ObjectId field for Pydantic models."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(str(v)):
            raise ValueError("Invalid ObjectId")
        return str(v)  # Return string representation instead of ObjectId


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
    username: Optional[str] = None
    subscribeToNewsletter: bool = False

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
    username: Optional[str] = None
    service_tier: Optional[ServiceTier] = None
    subscribeToNewsletter: Optional[bool] = None
    bio: Optional[str] = None
    profile_image: Optional[str] = None


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""

    GOOGLE = "google"
    GITHUB = "github"


class UserInDB(BaseModel):
    """Internal user model with hashed password."""

    id: Optional[ObjectId] = Field(alias="_id", default=None)
    email: EmailStr
    hashed_password: str
    full_name: Optional[str] = None
    username: Optional[str] = None
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    service_tier: ServiceTier = ServiceTier.FREE
    is_active: bool = True
    is_verified: bool = False
    subscribeToNewsletter: bool = False
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    last_login: Optional[datetime.datetime] = None
    oauth_providers: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    usage: dict = Field(
        default_factory=lambda: {
            "requests_today": 0,
            "requests_reset_date": datetime.datetime.utcnow(),
            "total_requests": 0,
            "storage_used_bytes": 0,
        }
    )

    model_config = {"arbitrary_types_allowed": True, "json_encoders": {ObjectId: str}}


class UserResponse(BaseModel):
    """Public user response model (without sensitive data)."""

    id: str
    email: EmailStr
    full_name: Optional[str] = None
    username: Optional[str] = None
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    service_tier: ServiceTier
    is_active: bool
    is_verified: bool
    subscribeToNewsletter: bool = False
    created_at: datetime.datetime
    oauth_providers: Dict[str, Dict[str, Any]] = {}
    usage: dict

    model_config = {"json_encoders": {ObjectId: lambda oid: str(oid)}}


class TokenData(BaseModel):
    """Model for JWT token data."""

    sub: str  # User ID
    exp: datetime.datetime
    service_tier: ServiceTier
    is_verified: bool
    saved_tools: List[str] = []  # List of saved tool IDs
