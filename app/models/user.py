from pydantic import BaseModel, EmailStr, Field, validator, BeforeValidator
from typing import Optional, List, Dict, Any, ClassVar, Annotated
from enum import Enum
import datetime
from bson import ObjectId
from pydantic.json_schema import JsonSchemaMode
from pydantic.functional_validators import BeforeValidator


def validate_object_id(v) -> str:
    """Validate and convert string to ObjectId."""
    if isinstance(v, str):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return v
    if isinstance(v, ObjectId):
        return str(v)
    raise ValueError("Invalid ObjectId")


PydanticObjectId = Annotated[str, BeforeValidator(validate_object_id)]


class ServiceTier(str, Enum):
    """User service tier levels."""

    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class TierLimits(BaseModel):
    """Model for defining tier-specific limits."""

    max_requests_per_day: int
    max_tokens_per_request: int
    max_storage_mb: int
    features: List[str]


class UserCreate(BaseModel):
    """User registration model."""

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


class UserLogin(BaseModel):
    """User login model."""

    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token model."""

    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    expires_in: int = 3600  # seconds
    user: Dict[str, Any] = {}


class TokenData(BaseModel):
    """JWT token payload data."""

    email: Optional[EmailStr] = None
    user_id: Optional[str] = None
    exp: Optional[datetime.datetime] = None
    iat: Optional[datetime.datetime] = None
    sub: Optional[str] = None
    iss: Optional[str] = None
    aud: Optional[str] = None
    jti: Optional[str] = None


class UserUpdate(BaseModel):
    """User update model."""

    full_name: Optional[str] = None
    username: Optional[str] = None
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    password: Optional[str] = None
    service_tier: Optional[ServiceTier] = None
    is_active: Optional[bool] = None
    subscribeToNewsletter: Optional[bool] = None


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""

    GOOGLE = "google"
    GITHUB = "github"


class UserInDB(BaseModel):
    """Internal user model with hashed password."""

    id: Optional[PydanticObjectId] = Field(alias="_id", default=None)
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

    model_config = {
        "arbitrary_types_allowed": True, 
        "json_schema_extra": {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "full_name": "John Doe",
                "service_tier": "free"
            }
        }
    }


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

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "full_name": "John Doe",
                "service_tier": "free",
                "is_active": True,
                "is_verified": True,
                "created_at": "2023-01-01T00:00:00"
            }
        }
    }
