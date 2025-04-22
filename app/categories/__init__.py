"""
Categories module for TAAFT backend
Provides endpoints for fetching and managing tool categories
"""

from .routes import router
from .service import categories_service

__all__ = ["router", "categories_service"]
