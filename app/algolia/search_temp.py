"""
Enhanced search service for Algolia integration
Handles natural language query processing for AI tool search
"""

from typing import Dict, List, Optional, Any, Union
import datetime
import json
import openai
import os
from pydantic import ValidationError
import re

from .config import algolia_config
from .models import (
    SearchParams,
    SearchResult,
    SearchFacets,
    SearchFacet,
    NaturalLanguageQuery,
    ProcessedQuery,
    PricingType,
)
from ..logger import logger


class AlgoliaSearch:
    """Service for NLP-based searching with Algolia"""

    def __init__(self):
        """Initialize the search service with Algolia config"""
        self.config = algolia_config
        # Initialize OpenAI for natural language processing
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if self.openai_api_key:
            openai.api_key = self.openai_api_key

        # Cache of known categories and pricing types
        self.known_categories = {}
        self.keyword_synonyms = {
            "writing": ["content creation", "text generation", "copywriting"],
            "image": ["image generation", "design", "graphic", "visual"],
            "audio": ["sound", "voice", "speech", "music"],
            "video": ["video generation", "animation"],
            "code": ["programming", "development", "coding", "software"],
            "marketing": ["seo", "social media", "advertising"],
            "data": ["analytics", "analysis", "visualization", "statistics"],
            "productivity": ["automation", "workflow", "efficiency"],
            "research": ["academic", "scientific", "study"],
            "chat": ["conversation", "assistant", "chatbot"],
            "e-commerce": ["shopping", "store", "retail", "sales"],
            "analytics": ["data analysis", "metrics", "performance", "tracking"],
        }

        # Price type mapping to standardize variations
        self.price_type_mapping = {
            "free": PricingType.FREE,
            "freemium": PricingType.FREEMIUM,
            "paid": PricingType.PAID,
            "premium": PricingType.PAID,
            "enterprise": PricingType.ENTERPRISE,
            "contact": PricingType.CONTACT,
            "contact for pricing": PricingType.CONTACT,
            "contact sales": PricingType.CONTACT,
        }

    async def perform_keyword_search(
        self,
        keywords: List[str],
        index_name: str = None,
        page: int = 0,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """
        Perform a search using keywords from chat conversation
        """
        # Use the provided index name or fall back to the default tools index
        search_index = index_name or self.config.tools_index_name

        # Join keywords into a space-separated search query
        search_query = ", ".join(keywords) if keywords else ""

        logger.info(
            f"Performing keyword search: '{search_query}' on index '{search_index}'"
        )

        # Check if Algolia is configured
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Returning empty search results.")
            return {
                "hits": [],
                "nbHits": 0,
                "page": page,
                "nbPages": 0,
                "processingTimeMS": 0,
            }

        try:
            # Execute search using Algolia client with explicit attribute retrieval
            results = self.config.client.search_single_index(
                index_name=search_index,
                search_params={
                    "query": f"{search_query}",
                    "attributesToRetrieve": ["*"],  # Request all attributes
                    "page": page,
                    "hitsPerPage": per_page,
                },
            )

            # Extract full object data from Hit objects
            full_hits = []
            if hasattr(results, "hits") and results.hits:
                for hit in results.hits:
                    # Extract all available attributes from the Hit object
                    hit_dict = {}

                    # First, add any direct attributes from the hit object
                    for attr_name in dir(hit):
                        # Skip private/special attributes and methods
                        if attr_name.startswith("_") or callable(
                            getattr(hit, attr_name)
                        ):
                            continue

                        hit_dict[attr_name] = getattr(hit, attr_name)

                    # Some Hit objects may store actual data in _source or _fields
                    if hasattr(hit, "_source"):
                        hit_dict.update(hit._source)

                    # Add the hit to our results
                    full_hits.append(hit_dict)

            # Build the complete response with enhanced hit data
            response = {
                "hits": full_hits if full_hits else results.hits,
                "nbHits": results.nb_hits if hasattr(results, "nb_hits") else 0,
                "page": results.page if hasattr(results, "page") else page,
                "nbPages": results.nb_pages if hasattr(results, "nb_pages") else 0,
                "processingTimeMS": (
                    results.processing_time_ms
                    if hasattr(results, "processing_time_ms")
                    else 0
                ),
                "query": results.query if hasattr(results, "query") else search_query,
                "params": results.params if hasattr(results, "params") else "",
            }

            # For debugging
            logger.info(f"Algolia search returned {response['nbHits']} results")
            if response["hits"] and len(response["hits"]) > 0:
                logger.info(f"First hit keys: {list(response['hits'][0].keys())}")

            return response

        except Exception as e:
            logger.error(f"Error performing keyword search: {str(e)}")
            return {
                "hits": [],
                "nbHits": 0,
                "page": page,
                "nbPages": 0,
                "processingTimeMS": 0,
                "error": str(e),
            }
