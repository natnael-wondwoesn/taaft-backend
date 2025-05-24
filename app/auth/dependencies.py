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

# List of user IDs that are exempted from rate limits
RATE_LIMIT_EXEMPT_USERS = [
    "6807647e1afd3348178550426",  # User from the logs
]

# Tier limits configuration
TIER_LIMITS = {
    ServiceTier.FREE: {
        "max_requests_per_day": 1000,
        "max_tokens_per_request": 4000,
        "max_storage_mb": 10,
        "features": ["basic_search", "basic_chat"],
    },
    ServiceTier.BASIC: {
        "max_requests_per_day": 5000,
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

        # Skip rate limiting for authentication routes and public routes
        if (
            request.url.path.startswith("/auth/")
            or request.url.path.startswith("/public/")
            or request.url.path.startswith("/tools/featured")
            or request.url.path.startswith("/tools/sponsored")
            or request.url.path.startswith("/favorites/")
            or request.url.path.startswith("/share/")
            or request.url.path == "/api/auth/reset-password"
            or request.url.path == "/tools"  # Allow direct access to /tools endpoint
            or request.url.path
            == "/api/categories/recalculate"  # Allow recalculating category counts
        ):
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

        # Get user ID from token
        user_id = token_data.sub

        # Check if user is exempt from rate limits
        if is_exempt_from_rate_limits(user_id):
            logger.info(f"User {user_id} is exempt from rate limits")
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

            # Special handling for chat-related endpoints
            # More lenient rate limiting for streaming/chat endpoints
            is_chat_endpoint = (
                request.url.path.startswith("/api/chat")
                or "/chat/" in request.url.path
                or request.url.path.startswith("/api/categories")
            )

            if is_chat_endpoint:
                # For chat endpoints, we'll be more lenient
                # Only check every 10 requests instead of every single one
                if requests_today % 10 != 0:
                    await database.users.update_one(
                        {"_id": ObjectId(token_data.sub)},
                        {
                            "$set": {
                                "usage.requests_today": requests_today,
                                "usage.total_requests": user["usage"].get(
                                    "total_requests", 0
                                )
                                + 1,
                            }
                        },
                    )
                    # Skip rate limit check
                    return await self.app(scope, receive, send)

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
    """Middleware for controlling access to admin endpoints."""

    def __init__(self, app):
        """Initialize the middleware with the ASGI application."""
        self.app = app
        # Paths that are allowed for non-admin users
        self.unrestricted_prefixes = ["/chat", "/algolia", "/api/chat", "/tools"]
        # Auth endpoints should also be accessible
        self.unrestricted_prefixes.append("/auth")
        # Health check should be accessible
        self.unrestricted_prefixes.append("/health")
        # First admin creation endpoint should be accessible without auth
        self.unrestricted_prefixes.append("/admin/init-admin")
        # Glossary endpoints should be accessible to all users for GET/POST/PUT operations
        # DELETE operations are restricted at the route handler level with the get_admin_user dependency
        self.unrestricted_prefixes.append("/api/glossary")
        # Keyword search endpoint should be accessible to all authenticated users
        self.unrestricted_prefixes.append("/tools/keyword-search")
        # Favorites endpoint should be accessible to all authenticated users
        self.unrestricted_prefixes.append("/favorites")
        # Share endpoint should be accessible to all authenticated users
        self.unrestricted_prefixes.append("/share")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            # Not an HTTP request, just pass through
            return await self.app(scope, receive, send)

        # Process the request
        request = Request(scope)

        # List of endpoints that should be accessible without authentication
        public_endpoints = [
            "/docs",
            "/redoc",
            "/openapi.json",
            # Auth endpoints
            "/api/auth/login",
            "/api/auth/token",
            "/api/auth/register",
            "/api/auth/refresh-token",
            "/api/auth/request-login-code",
            "/api/auth/verify-login-code",
            "/api/auth/verify-email",
            "/api/auth/resend-verification",
            "/api/auth/request-password-reset",
            "/api/auth/reset-password",  # Password reset endpoint
            # Also include the non-prefixed paths for direct access
            "/auth/login",
            "/auth/token",
            "/auth/register",
            "/auth/refresh-token",
            "/auth/request-login-code",
            "/auth/verify-login-code",
            "/auth/verify-email",
            "/auth/resend-verification",
            "/auth/request-password-reset",
            "/auth/reset-password",
            # Public routes for email verification and password reset
            "/verify-email",
            "/reset-password",
            # OAuth endpoints
            "/api/sso/login/google",
            "/api/sso/login/github",
            "/api/sso/callback/google",
            "/api/sso/callback/github",
            "/api/sso/providers",
            # Category endpoints
            "/api/categories/recalculate",  # Public endpoint for recalculating category counts
        ]

        # If it's a public endpoint, skip auth checks
        path = request.url.path
        if any(path.startswith(endpoint) for endpoint in public_endpoints):
            return await self.app(scope, receive, send)

        # Get request method
        method = request.method

        # Allow POST requests to /tools/keyword-search without admin check
        if (
            path == "/tools/keyword-search" or path == "/api/tools/keyword-search"
        ) and method == "POST":
            return await self.app(scope, receive, send)

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


def is_exempt_from_rate_limits(user_id: str) -> bool:
    """Check if a user is exempt from rate limits."""
    return user_id in RATE_LIMIT_EXEMPT_USERS
