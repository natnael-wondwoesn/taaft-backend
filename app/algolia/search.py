# # app/algolia/search.py
# """
# Enhanced search service for Algolia integration
# Handles natural language query processing for AI tool search
# """


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
import time

from .config import algolia_config
from .models import (
    SearchParams,
    SearchResult,
    SearchFacets,
    SearchFacet,
    NaturalLanguageQuery,
    ProcessedQuery,
    PricingType,
    AlgoliaToolRecord,
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

        Args:
            keywords: List of keywords extracted from the conversation
            index_name: Optional index name to override the default tools index
            page: Page number (0-based for Algolia)
            per_page: Number of results per page

        Returns:
            Dictionary containing search results from Algolia
        """
        # Use the provided index name or fall back to the default tools index
        search_index = index_name or self.config.tools_index_name

        # Performance optimization: Start tracking execution time
        start_time = time.time()

        # Join keywords into a space-separated search query
        search_query = " ".join(keywords) if keywords else ""

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
            # Optimization: Use more efficient search parameters
            search_params = {
                "query": search_query,
                "page": page,
                "hitsPerPage": per_page,
                "attributesToRetrieve": ["*"],
                "advancedSyntax": True,
                "typoTolerance": True,
                "removeWordsIfNoResults": "allOptional",
                "analytics": False,  # Disable analytics for faster response
                "enablePersonalization": False,  # Disable personalization for speed
                "distinct": True,
            }

            # Use optimized client if available
            if (
                hasattr(self.config, "optimized_client")
                and self.config.optimized_client
            ):
                logger.debug("Using optimized Algolia client for search")
                results = await self.config.optimized_client.search_single_index(
                    index_name=search_index, search_params=search_params
                )
            else:
                # Fall back to standard client
                logger.debug("Using standard Algolia client for search")
                results = self.config.client.search_single_index(
                    index_name=search_index,
                    search_params=search_params,
                )

            # Performance logging
            elapsed = time.time() - start_time
            logger.debug(f"Algolia search completed in {elapsed:.4f}s")

            # Return standardized results
            if results:
                return {
                    "hits": (
                        results.hits
                        if hasattr(results, "hits")
                        else results.get("hits", [])
                    ),
                    "nbHits": (
                        results.nb_hits
                        if hasattr(results, "nb_hits")
                        else results.get("nbHits", 0)
                    ),
                    "page": (
                        results.page
                        if hasattr(results, "page")
                        else results.get("page", page)
                    ),
                    "nbPages": (
                        results.nb_pages
                        if hasattr(results, "nb_pages")
                        else results.get("nbPages", 0)
                    ),
                    "processingTimeMS": (
                        results.processing_time_ms
                        if hasattr(results, "processing_time_ms")
                        else results.get("processingTimeMS", 0)
                    ),
                    "query": (
                        results.query
                        if hasattr(results, "query")
                        else results.get("query", search_query)
                    ),
                    "params": (
                        results.params
                        if hasattr(results, "params")
                        else results.get("params", search_params)
                    ),
                    "responseTime": elapsed,
                }
            else:
                logger.warning("No results found or invalid response format.")
                return {
                    "hits": [],
                    "nbHits": 0,
                    "page": page,
                    "nbPages": 0,
                    "processingTimeMS": 0,
                    "responseTime": elapsed,
                }

        except Exception as e:
            # Log and return error
            elapsed = time.time() - start_time
            logger.error(f"Error performing keyword search ({elapsed:.4f}s): {str(e)}")
            return {
                "hits": [],
                "nbHits": 0,
                "page": page,
                "nbPages": 0,
                "processingTimeMS": 0,
                "error": str(e),
                "responseTime": elapsed,
            }

    def extract_keywords_from_chat(self, messages: List[Dict[str, Any]]) -> List[str]:
        """
        Extract keywords from chat messages for search

        Args:
            messages: List of chat messages with 'role' and 'content' fields

        Returns:
            List of relevant keywords for search
        """
        # Common stopwords to filter out
        stopwords = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "if",
            "then",
            "else",
            "when",
            "at",
            "from",
            "by",
            "for",
            "with",
            "about",
            "against",
            "between",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "to",
            "of",
            "in",
            "on",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "where",
            "why",
            "how",
            "all",
            "any",
            "both",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "can",
            "will",
            "just",
            "should",
            "now",
            "tool",
            "tools",
            "ai",
            "intelligence",
            "artificial",
            "model",
            "models",
            "system",
        }

        # Extract only user messages as these contain the intent
        user_messages = [
            msg["content"] for msg in messages if msg.get("role") == "user"
        ]

        if not user_messages:
            return []

        # Focus on the last 3 messages, with more weight on the most recent
        recent_messages = user_messages[-3:]

        # Combine messages with more weight to more recent ones
        weights = [0.5, 0.75, 1.0]
        weighted_text = ""

        for i, msg in enumerate(recent_messages):
            if i < len(weights):
                # Repeat more recent messages to give them more weight
                repeats = int(weights[i] * 10)
                weighted_text += " " + " ".join([msg] * repeats)
            else:
                weighted_text += " " + msg

        # Extract words, normalize
        words = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", weighted_text.lower())

        # Remove stopwords and duplicates while preserving order
        filtered_words = []
        seen = set()

        for word in words:
            if word not in stopwords and word not in seen:
                filtered_words.append(word)
                seen.add(word)

        # Check for synonyms and add them
        extended_keywords = []
        for word in filtered_words:
            extended_keywords.append(word)
            # Check for synonyms
            for key, synonyms in self.keyword_synonyms.items():
                if word == key or word in synonyms:
                    # Add both the key and other synonyms
                    extended_keywords.append(key)
                    extended_keywords.extend([s for s in synonyms if s != word])

        # Remove duplicates from extended list while preserving order
        final_keywords = []
        seen = set()
        for word in extended_keywords:
            if word not in seen:
                final_keywords.append(word)
                seen.add(word)

        # Return top keywords (limit to reasonable number)
        return final_keywords[:15]

    async def search_from_chat(
        self,
        messages: List[Dict[str, Any]],
        index_name: str = None,
        page: int = 0,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """
        Search for tools based on chat conversation

        Args:
            messages: List of chat messages with 'role' and 'content' fields
            index_name: Optional index name to override the default
            page: Page number (0-based for Algolia)
            per_page: Number of results per page

        Returns:
            Dictionary containing search results from Algolia
        """
        # Extract keywords from chat messages
        keywords = self.extract_keywords_from_chat(messages)

        if not keywords:
            logger.warning("No keywords extracted from chat messages")
            return {
                "hits": [],
                "nbHits": 0,
                "page": page,
                "nbPages": 0,
                "processingTimeMS": 0,
                "keywords": [],
            }

        logger.info(f"Extracted keywords from chat: {keywords}")

        # Perform search using the extracted keywords
        results = await self.perform_keyword_search(
            keywords=keywords, index_name=index_name, page=page, per_page=per_page
        )

        # Add the keywords used to the results
        results["keywords"] = keywords

        return results

    def extract_keywords_from_text(self, text: str) -> List[str]:
        """
        Extract keywords from a single text string

        Args:
            text: The text to extract keywords from

        Returns:
            List of relevant keywords for search
        """
        if not text:
            return []

        # Create a fake message to use the existing extraction logic
        fake_messages = [{"role": "user", "content": text}]
        return self.extract_keywords_from_chat(fake_messages)

    async def get_known_keywords_from_database(self) -> List[str]:
        """
        Fetch all keywords from the database keywords collection.

        Returns:
            List of all keywords stored in the database
        """
        from ..database.database import keywords

        # Fetch all keywords from the database
        cursor = keywords.find({})

        # Process results
        keywords_list = []
        async for keyword_doc in cursor:
            # Check the field name - could be either 'keyword' or 'word' depending on
            # which function created it. The update_tool_keywords uses 'keyword',
            # while the get_tools function uses 'word'
            keyword_value = keyword_doc.get("keyword") or keyword_doc.get("word")

            if keyword_value and keyword_value not in keywords_list:
                keywords_list.append(keyword_value)

        return keywords_list

    async def direct_search_tools(
        self,
        query: str,
        page: int = 0,
        per_page: int = 20,
    ) -> SearchResult:
        """
        Search for tools directly by name or description using Algolia.
        This search is more flexible and doesn't require exact matches.

        Args:
            query: The search query text
            page: Page number (0-based for Algolia)
            per_page: Number of results per page

        Returns:
            SearchResult object containing the search results
        """
        # Start tracking execution time
        start_time = time.time()

        # Check if Algolia is configured
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Returning empty search results.")
            return SearchResult(
                tools=[],
                total=0,
                page=page,
                per_page=per_page,
                pages=0,
                processing_time_ms=0,
            )

        try:
            # Set up optimized search parameters
            search_params = {
                "query": query,
                "restrictSearchableAttributes": ["name", "description"],
                "page": page,
                "hitsPerPage": per_page,
                "typoTolerance": True,
                "advancedSyntax": True,
                "removeWordsIfNoResults": "allOptional",
                "analytics": False,  # Disable analytics for speed
                "enablePersonalization": False,  # Disable personalization
                "distinct": True,
            }

            # Execute search using Algolia client
            index_name = self.config.tools_index_name

            # Use optimized client if available
            if (
                hasattr(self.config, "optimized_client")
                and self.config.optimized_client
            ):
                logger.debug("Using optimized Algolia client for direct search")
                search_response = (
                    await self.config.optimized_client.search_single_index(
                        index_name=index_name, search_params=search_params
                    )
                )
            else:
                # Fall back to standard client
                logger.debug("Using standard Algolia client for direct search")
                search_response = self.config.client.search_single_index(
                    index_name=index_name, search_params=search_params
                )

            # Convert results to tool records efficiently
            tools = []

            # Handle both object and dict response formats
            hits = []
            if hasattr(search_response, "hits"):
                hits = search_response.hits
            elif isinstance(search_response, dict):
                hits = search_response.get("hits", [])

            for hit in hits:
                try:
                    # Create AlgoliaToolRecord from each hit
                    tool_record = AlgoliaToolRecord(
                        objectID=(
                            getattr(hit, "objectID", "")
                            if not isinstance(hit, dict)
                            else hit.get("objectID", "")
                        ),
                        name=(
                            getattr(hit, "name", "")
                            if not isinstance(hit, dict)
                            else hit.get("name", "")
                        ),
                        description=(
                            getattr(hit, "description", "")
                            if not isinstance(hit, dict)
                            else hit.get("description", "")
                        ),
                        slug=(
                            getattr(hit, "slug", None)
                            if not isinstance(hit, dict)
                            else hit.get("slug") or hit.get("unique_id")
                        ),
                        website=(
                            getattr(hit, "website", None)
                            if not isinstance(hit, dict)
                            else hit.get("website") or hit.get("link")
                        ),
                        features=(
                            getattr(hit, "features", [])
                            if not isinstance(hit, dict)
                            else hit.get("features", [])
                        ),
                        categories=(
                            getattr(hit, "categories", [])
                            if not isinstance(hit, dict)
                            else hit.get("categories", [])
                        ),
                        pricing=(
                            getattr(hit, "pricing", None)
                            if not isinstance(hit, dict)
                            else hit.get("pricing")
                        ),
                        price=(
                            getattr(hit, "price", "")
                            if not isinstance(hit, dict)
                            else hit.get("price", "")
                        ),
                        is_featured=(
                            getattr(hit, "is_featured", False)
                            if not isinstance(hit, dict)
                            else hit.get("is_featured", False)
                        ),
                        created_at=(
                            getattr(hit, "created_at", None)
                            if not isinstance(hit, dict)
                            else hit.get("created_at")
                        ),
                        updated_at=(
                            getattr(hit, "updated_at", None)
                            if not isinstance(hit, dict)
                            else hit.get("updated_at")
                        ),
                    )
                    tools.append(tool_record)
                except Exception as e:
                    logger.error(f"Error converting hit to AlgoliaToolRecord: {str(e)}")
                    continue

            # Calculate response time
            elapsed = time.time() - start_time
            logger.debug(f"Direct search completed in {elapsed:.4f}s")

            # Get result metadata from either object or dict response
            if hasattr(search_response, "nb_hits"):
                total = search_response.nb_hits
                result_page = search_response.page
                pages = search_response.nb_pages
                processing_time_ms = search_response.processing_time_ms
            else:
                total = search_response.get("nbHits", 0)
                result_page = search_response.get("page", page)
                pages = search_response.get("nbPages", 0)
                processing_time_ms = search_response.get("processingTimeMS", 0)

            # Create and return SearchResult
            return SearchResult(
                tools=tools,
                total=total,
                page=result_page,
                per_page=per_page,
                pages=pages,
                processing_time_ms=processing_time_ms,
                response_time=elapsed,
            )

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Error performing direct search ({elapsed:.4f}s): {str(e)}")

            # Return empty results on error
            return SearchResult(
                tools=[],
                total=0,
                page=page,
                per_page=per_page,
                pages=0,
                processing_time_ms=0,
                response_time=elapsed,
            )


# Create a singleton instance of AlgoliaSearch
algolia_search = AlgoliaSearch()


async def format_search_results_summary(search_results: Dict[str, Any]) -> str:
    """
    Format the results from perform_keyword_search into a structured summary.

    Args:
        search_results: Dictionary or object containing search results from Algolia

    Returns:
        A formatted string with a summary of the search results
    """
    # Extract key information from search results - handle both dict and object formats
    if hasattr(search_results, "nb_hits"):
        num_hits = search_results.nb_hits
        hits = search_results.hits
    else:
        num_hits = search_results.get("nbHits", 0)
        hits = search_results.get("hits", [])

    print(f"hits: {hits}")
    # Create the initial greeting message
    summary = f"Hey! Great News! I have found Plenty of tools to help you from our directory.\n\n"

    # If no results were found, provide a message
    if num_hits == 0:
        summary += "Unfortunately, I couldn't find any matching tools. Try broadening your search terms."
        return summary

    # Add a structured list of the top tools found
    summary += "Here are the top tools I found for you:\n\n"

    # Process each hit/tool into a structured format
    for i, hit in enumerate(hits, 1):
        if i > 10:  # Limit to top 10 for readability
            break

        # Get properties with fallbacks for missing data - handle both dict and object formats
        if isinstance(hit, dict):
            name = hit.get("name", "Unnamed Tool")
            description = hit.get("description", "No description available.")
            pricing = hit.get("pricing_type", "")
            categories = hit.get("categories", [])
            url = hit.get("url", "")
        else:
            name = getattr(hit, "name", "Unnamed Tool")
            description = getattr(hit, "description", "No description available.")
            pricing = getattr(hit, "pricing_type", "")
            categories = getattr(hit, "categories", [])
            url = getattr(hit, "url", "")

        if pricing:
            pricing = pricing.capitalize()

        # Format each tool entry
        summary += f"📌 {name}\n"
        summary += f"   {description}\n"
        if pricing:
            summary += f"   💰 {pricing}\n"
        if categories and isinstance(categories, list):
            cat_text = ", ".join(categories)
            summary += f"   🏷️ {cat_text}\n"
        if url:
            summary += f"   🔗 {url}\n"
        summary += "\n"

    # Add a footer if there are more results than shown
    if num_hits > 10:
        remaining = num_hits - 10
        summary += (
            f"...and {remaining} more tool{'s' if remaining > 1 else ''} available."
        )

    return summary
