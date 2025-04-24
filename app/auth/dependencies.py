from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Optional, Union
from ..models.user import UserInDB, ServiceTier
from .utils import decode_token
from ..database.database import database
from bson import ObjectId
import datetime
from ..logger import logger

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Tier limits configuration
TIER_LIMITS = {
    ServiceTier.FREE: {
        "max_requests_per_day": 100,
        "max_tokens_per_request": 4000,
        "max_storage_mb": 10,
        "features": ["basic_search", "basic_chat"],
    },
    ServiceTier.BASIC: {
        "max_requests_per_day": 1000,
        "max_tokens_per_request": 8000,
        "max_storage_mb": 100,
        "features": ["basic_search", "basic_chat", "advanced_search"],
    },
    ServiceTier.PRO: {
        "max_requests_per_day": 10000,
        "max_tokens_per_request": 16000,
        "max_storage_mb": 1000,
        "features": ["basic_search", "basic_chat", "advanced_search", "custom_models"],
    },
    ServiceTier.ENTERPRISE: {
        "max_requests_per_day": -1,  # Unlimited
        "max_tokens_per_request": 32000,
        "max_storage_mb": 10000,
        "features": [
            "basic_search",
            "basic_chat",
            "advanced_search",
            "custom_models",
            "priority_support",
        ],
    },
}


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """Dependency to get the current authenticated user from token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode and validate the JWT token
    token_data = decode_token(token)
    if token_data is None:
        raise credentials_exception

    # Check if token is expired
    if datetime.datetime.utcnow() > token_data.exp:
        raise credentials_exception

    # Get user from database
    user = await database.users.find_one({"_id": ObjectId(token_data.sub)})
    if user is None:
        raise credentials_exception

    # Convert to UserInDB model
    return UserInDB(**user)


async def get_current_active_user(
    current_user: UserInDB = Depends(get_current_user),
) -> UserInDB:
    """Dependency to get the current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_verified_user(
    current_user: UserInDB = Depends(get_current_active_user),
) -> UserInDB:
    """Dependency to get verified users only."""
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Email verification required")
    return current_user


async def get_admin_user(
    current_user: UserInDB = Depends(get_current_active_user),
) -> UserInDB:
    """Dependency to get admin users only."""
    # Admin is determined by having the ENTERPRISE tier for now
    # This could be enhanced with a specific is_admin flag in the user model
    if current_user.service_tier != ServiceTier.ENTERPRISE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def check_tier_access(required_tier: ServiceTier):
    """Factory for creating tier-based access control dependencies."""

    async def tier_access(
        current_user: UserInDB = Depends(get_current_active_user),
    ) -> UserInDB:
        user_tier = current_user.service_tier
        tier_hierarchy = list(ServiceTier)

        # Check if user's tier is at or above the required tier
        if tier_hierarchy.index(user_tier) < tier_hierarchy.index(required_tier):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires {required_tier} tier or higher",
            )
        return current_user

    return tier_access


def has_feature(feature_name: str):
    """Factory for feature-based access control."""

    async def feature_access(
        current_user: UserInDB = Depends(get_current_active_user),
    ) -> UserInDB:
        user_tier = current_user.service_tier
        tier_features = TIER_LIMITS[user_tier]["features"]

        if feature_name not in tier_features:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature is not available in your current plan",
            )
        return current_user

    return feature_access


class RateLimitMiddleware:
    """Middleware for rate limiting based on user tier."""

    def __init__(self, app):
        """Initialize the middleware with the ASGI application."""
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            # Not an HTTP request, just pass through
            return await self.app(scope, receive, send)

        # Process the request
        request = Request(scope)

        # Skip rate limiting for authentication routes
        if request.url.path.startswith("/auth/"):
            return await self.app(scope, receive, send)

        # Try to get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # No auth token, proceed without rate limiting
            return await self.app(scope, receive, send)

        # Extract token
        token = auth_header.replace("Bearer ", "")
        token_data = decode_token(token)

        if token_data is None:
            # Invalid token, let the route handler deal with it
            return await self.app(scope, receive, send)

        # Get user from database
        user = await database.users.find_one({"_id": ObjectId(token_data.sub)})
        if user is None:
            return await self.app(scope, receive, send)

        # Check rate limits
        today = datetime.datetime.utcnow().date()
        reset_date = (
            user["usage"]["requests_reset_date"].date()
            if "usage" in user and "requests_reset_date" in user["usage"]
            else None
        )

        # Reset daily counter if it's a new day
        if reset_date is None or reset_date < today:
            await database.users.update_one(
                {"_id": ObjectId(token_data.sub)},
                {
                    "$set": {
                        "usage.requests_today": 1,
                        "usage.requests_reset_date": datetime.datetime.utcnow(),
                        "usage.total_requests": user["usage"].get("total_requests", 0)
                        + 1,
                    }
                },
            )
        else:
            # Increment request counters
            requests_today = user["usage"].get("requests_today", 0) + 1

            # Check tier limit
            tier = user.get("service_tier", ServiceTier.FREE)
            max_requests = TIER_LIMITS[tier]["max_requests_per_day"]

            # If max_requests is -1, it means unlimited
            if max_requests != -1 and requests_today > max_requests:
                logger.warning(f"Rate limit exceeded for user {token_data.sub}")
                error_response = HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Your plan allows {max_requests} requests per day.",
                )

                # Return error response
                from starlette.responses import JSONResponse

                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": f"Rate limit exceeded. Your plan allows {max_requests} requests per day."
                    },
                )
                await response(scope, receive, send)
                return

            # Update usage
            await database.users.update_one(
                {"_id": ObjectId(token_data.sub)},
                {
                    "$set": {
                        "usage.requests_today": requests_today,
                        "usage.total_requests": user["usage"].get("total_requests", 0)
                        + 1,
                    }
                },
            )

        # Continue with the request
        return await self.app(scope, receive, send)


class AdminControlMiddleware:
    """Middleware to restrict PUT/POST/DELETE methods to admin users except for specific routes."""

    def __init__(self, app):
        """Initialize the middleware with the ASGI application."""
        self.app = app
        # Paths that are allowed for non-admin users
        self.unrestricted_prefixes = ["/chat", "/algolia"]
        # Auth endpoints should also be accessible
        self.unrestricted_prefixes.append("/auth")
        # Health check should be accessible
        self.unrestricted_prefixes.append("/health")
        # First admin creation endpoint should be accessible without auth
        self.unrestricted_prefixes.append("/admin/init-admin")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            # Not an HTTP request, just pass through
            return await self.app(scope, receive, send)

        # Get request method and path
        request = Request(scope)
        method = request.method
        path = request.url.path

        # Check if method is restricted (POST, PUT, DELETE)
        if method in ["POST", "PUT", "DELETE", "PATCH"]:
            # Check if path is unrestricted
            if not any(
                path.startswith(prefix) for prefix in self.unrestricted_prefixes
            ):
                # Path is restricted, check if user is admin
                auth_header = request.headers.get("Authorization")
                if not auth_header or not auth_header.startswith("Bearer "):
                    # No auth token, return 401
                    from starlette.responses import JSONResponse

                    response = JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={
                            "detail": "Authentication required for this operation"
                        },
                    )
                    await response(scope, receive, send)
                    return

                # Extract token
                token = auth_header.replace("Bearer ", "")
                token_data = decode_token(token)

                if token_data is None:
                    # Invalid token, return 401
                    from starlette.responses import JSONResponse

                    response = JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Invalid authentication token"},
                    )
                    await response(scope, receive, send)
                    return

                # Get user from database
                user = await database.users.find_one({"_id": ObjectId(token_data.sub)})
                if user is None:
                    # User not found, return 401
                    from starlette.responses import JSONResponse

                    response = JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "User not found"},
                    )
                    await response(scope, receive, send)
                    return

                # Check if user is admin (ENTERPRISE tier for now)
                if user.get("service_tier") != ServiceTier.ENTERPRISE:
                    # User is not admin, return 403
                    from starlette.responses import JSONResponse

                    response = JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Admin access required for this operation"},
                    )
                    await response(scope, receive, send)
                    return

        # Continue with the request
        return await self.app(scope, receive, send)
