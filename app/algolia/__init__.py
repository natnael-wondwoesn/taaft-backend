# app/algolia/__init__.py
"""
Algolia integration module for TAAFT backend
Provides search functionality for AI tools and recommendations
"""
from .routes import router
from .config import algolia_config
from .search import algolia_search

__all__ = ["router", "algolia_config", "algolia_search"]
