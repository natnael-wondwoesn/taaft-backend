# app/algolia/__init__.py
"""
Algolia integration module for TAAFT backend
Provides search functionality for AI tools and recommendations
"""
# First import config
from .config import algolia_config

# Then import middleware
from .middleware import SearchPerformanceMiddleware

# Import router after middleware to avoid circular dependencies
from .routes import router

# Import search implementation last
from .search import algolia_search

__all__ = ["router", "algolia_config", "SearchPerformanceMiddleware", "algolia_search"]
