# app/algolia/__init__.py
"""
Algolia search integration for TAAFT backend
Provides natural language search capabilities and indexing for the AI tool directory
"""
from .routes import router
from .config import algolia_config
from .indexer import algolia_indexer
from .search import algolia_search

__all__ = ["router", "algolia_config", "algolia_indexer", "algolia_search"]
