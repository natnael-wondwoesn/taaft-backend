"""
Middleware for allowing public access to featured tools.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import re


class PublicFeaturedToolsMiddleware(BaseHTTPMiddleware):
    """Middleware that allows public access to featured tools endpoints."""

    def __init__(self, app):
        super().__init__(app)
        # Regex patterns for routes that should be accessible without authentication
        self.public_patterns = [
            # Public tools router
            re.compile(r"^/public/tools/.*$"),
            # Public tool logs router
            re.compile(r"^/public/tool-logs/.*$"),
            # Original featured endpoint
            re.compile(r"^/tools/featured/?(\?.*)?$"),
            # New sponsored endpoint
            re.compile(r"^/tools/sponsored/?(\?.*)?$"),
            # Main tools endpoint
            re.compile(r"^/tools/?(\?.*)?$"),
            # Password reset endpoint (POST)
            re.compile(r"^/api/auth/reset-password.*$"),
            # Password reset endpoint (GET)
            re.compile(r"^/reset-password.*$"),
            # Email verification endpoint
            re.compile(r"^/verify-email.*$"),
        ]

    async def dispatch(self, request: Request, call_next):
        # Check if the path matches any of our public patterns
        path = request.url.path
        for pattern in self.public_patterns:
            if pattern.match(path):
                # This is a public endpoint, let it through without authentication
                return await call_next(request)

        # For all other routes, continue normal processing (which includes auth checks)
        return await call_next(request)
