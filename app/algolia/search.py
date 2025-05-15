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

        print(f"keywords: {keywords}")

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
            # Construct the search request
            # print(f"{search_query}")
            # Convert the search query to the specified format with a placeholder popularity value
            # Using a fixed popularity value of 2.5658 as specified in the instructions
            # search_query = list(search_query.join())
            print(f"search_index: {search_query}")
            params = {
                "params": {
                    "index_name": search_index,
                    "query": search_query,
                    "page": page,
                    "hitsPerPage": per_page,
                    "attributesToRetrieve": ["*"],
                }
            }

            # Execute search using Algolia client
            results = self.config.client.search_single_index(
                index_name=search_index,
                search_params={
                    "query": f"{search_query}",
                    "attributesToRetrieve": ["*"],
                    "advancedSyntax": True,
                    "typoTolerance": True,
                    "removeWordsIfNoResults": "allOptional",
                    "hitsPerPage": 1000,  # Increase to get all available hits
                },
            )

            print(f"results: {results.nb_hits}")

            # Process the response based on its actual structure
            # The response contains direct search results without a "results" field
            if results:
                # Extract the relevant search result fields
                return {
                    "hits": results.hits,
                    "nbHits": results.nb_hits,
                    "page": results.page,
                    "nbPages": results.nb_pages,
                    "processingTimeMS": results.processing_time_ms,
                    "query": results.query,
                    "params": results.params,
                }
            else:
                logger.warning("No results found or invalid response format.")
                return {
                    "hits": [],
                    "nbHits": 0,
                    "page": page,
                    "nbPages": 0,
                    "processingTimeMS": 0,
                }

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
            # Set up search parameters to focus on name and description fields
            search_params = {
                "query": query,
                "restrictSearchableAttributes": ["name", "description"],
                "page": page,
                "hitsPerPage": per_page,
                "typoTolerance": False,  # Allow for typos in search
                "advancedSyntax": True,
                "removeWordsIfNoResults": "allOptional",  # Makes search more flexible
            }

            # Execute search using Algolia client
            index_name = self.config.tools_index_name
            search_response = self.config.client.search_single_index(
                index_name=index_name, search_params=search_params
            )

            # Convert results to tool records
            tools = []
            for hit in search_response.hits:
                # print(f"hit: {hit}")
                try:
                    # Create AlgoliaToolRecord from each hit
                    tool_record = AlgoliaToolRecord(
                        objectID=getattr(hit, "objectID", ""),
                        price=getattr(hit, "price", None),
                        name=getattr(hit, "name", None),
                        description=getattr(hit, "description", None),
                        link=getattr(hit, "link", None),
                        unique_id=getattr(hit, "unique_id", None),
                        rating=getattr(hit, "rating", None),
                        saved_numbers=getattr(hit, "saved_numbers", None),
                        category=getattr(hit, "category", None),
                        features=getattr(hit, "features", None),
                        is_featured=getattr(hit, "is_featured", False),
                        keywords=getattr(hit, "keywords", None),
                        categories=getattr(hit, "categories", None),
                        logo_url=getattr(hit, "logo_url", None),
                        user_reviews=getattr(hit, "user_reviews", None),
                        feature_list=getattr(hit, "feature_list", None),
                        referral_allow=getattr(hit, "referral_allow", False),
                        generated_description=getattr(
                            hit, "generated_description", None
                        ),
                        industry=getattr(hit, "industry", None),
                        created_at=getattr(hit, "created_at", None),
                        updated_at=getattr(hit, "updated_at", None),
                    )
                    # print(f"tool_record: {tool_record}")
                    tools.append(tool_record)
                    print(f"tools: {tools}")
                except Exception as e:
                    logger.error(f"Error converting hit to AlgoliaToolRecord: {str(e)}")
                    continue
            print(f"tools: {tools}")
            # Create and return SearchResult
            return SearchResult(
                tools=tools,
                total=search_response.nb_hits,
                page=search_response.page,
                per_page=per_page,
                pages=search_response.nb_pages,
                processing_time_ms=search_response.processing_time_ms,
            )

        except Exception as e:
            logger.error(f"Error performing direct search: {str(e)}")
            # Return empty results on error
            return SearchResult(
                tools=[],
                total=0,
                page=page,
                per_page=per_page,
                pages=0,
                processing_time_ms=0,
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
