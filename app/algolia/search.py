# app/algolia/search.py
"""
Enhanced search service for Algolia integration
Handles tool search and natural language query processing
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
    """Service for searching with Algolia"""

    def __init__(self):
        """Initialize the search service with Algolia config"""
        self.config = algolia_config
        # Initialize OpenAI for natural language processing
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if self.openai_api_key:
            openai.api_key = self.openai_api_key

        # Cache of known categories and pricing types
        self.known_categories = {}
        self.category_synonyms = {
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

    async def search_tools(self, params: SearchParams) -> SearchResult:
        """
        Search for tools using Algolia

        Args:
            params: Search parameters

        Returns:
            SearchResult object with tools and metadata
        """
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Returning empty search results.")
            return SearchResult(
                tools=[], total=0, page=params.page, per_page=params.per_page, pages=0
            )

        try:
            # Build search parameters
            search_args = {
                "query": params.query,
                "page": params.page - 1,  # Algolia uses 0-based pagination
                "hitsPerPage": params.per_page,
            }

            # Add facet filters if provided
            facet_filters = []

            if params.categories:
                category_filters = [
                    f"categories.id:{cat_id}" for cat_id in params.categories
                ]
                facet_filters.append(category_filters)

            if params.pricing_types:
                pricing_filters = [
                    f"pricing.type:{pricing}" for pricing in params.pricing_types
                ]
                facet_filters.append(pricing_filters)

            if params.min_rating:
                # For numeric filters like ratings
                search_args["numericFilters"] = [
                    f"ratings.average>={params.min_rating}"
                ]

            # Add custom filters if provided
            if params.filters:
                search_args["filters"] = params.filters

            # Add facet filters to search args if any
            if facet_filters:
                search_args["facetFilters"] = facet_filters

            # Add sort if provided
            if params.sort_by:
                if params.sort_by == "newest":
                    search_args["sortBy"] = "created_at:desc"
                elif params.sort_by == "trending":
                    search_args["sortBy"] = "trending_score:desc"
                # Default is relevance, which doesn't need a sort parameter

            # Request facets for filtering options
            search_args["facets"] = ["categories.name", "pricing.type", "features"]

            # Execute search using v4 client syntax
            result = self.config.client.search_single_index(
                self.config.tools_index_name, search_args
            )

            # Log the search parameters and result summary
            logger.info(f"Algolia search with params: {search_args}")

            # Extract data from the search response - try different access patterns
            try:
                # Try accessing as object attributes first
                hits = result.hits if hasattr(result, "hits") else []
                nb_hits = result.nbHits if hasattr(result, "nbHits") else 0
                processing_time_ms = (
                    result.processingTimeMS
                    if hasattr(result, "processingTimeMS")
                    else 0
                )
                facets = result.facets if hasattr(result, "facets") else {}

                logger.info(f"Search found {nb_hits} results")

                # Cache category information from facets
                categories_dict = {}
                if hasattr(facets, "categories_name"):
                    categories_dict = facets.categories_name
                elif isinstance(facets, dict) and "categories.name" in facets:
                    categories_dict = facets["categories.name"]

                # Extract pricing types
                pricing_dict = {}
                if hasattr(facets, "pricing_type"):
                    pricing_dict = facets.pricing_type
                elif isinstance(facets, dict) and "pricing.type" in facets:
                    pricing_dict = facets["pricing.type"]

                # Update known categories
                for category_name, count in categories_dict.items():
                    self.known_categories[category_name.lower()] = {
                        "name": category_name,
                        "count": count,
                    }

                # Create facets objects
                facets_obj = SearchFacets(
                    categories=[
                        SearchFacet(name=name, count=count)
                        for name, count in categories_dict.items()
                    ],
                    pricing_types=[
                        SearchFacet(name=name, count=count)
                        for name, count in pricing_dict.items()
                    ],
                )

                # Calculate total pages
                total_pages = (
                    (nb_hits + params.per_page - 1) // params.per_page
                    if params.per_page > 0
                    else 0
                )

                # Prepare the search result
                search_result = SearchResult(
                    tools=hits,
                    total=nb_hits,
                    page=params.page,
                    per_page=params.per_page,
                    pages=total_pages,
                    facets=facets_obj,
                    processing_time_ms=processing_time_ms,
                )

                return search_result

            except Exception as e:
                logger.warning(
                    f"Error accessing response properties as attributes: {str(e)}. Falling back to dictionary access."
                )

                # Fall back to dictionary access
                hits = result.get("hits", []) if hasattr(result, "get") else []
                if not hits and isinstance(result, dict):
                    hits = result.get("hits", [])

                nb_hits = 0
                if hasattr(result, "get"):
                    nb_hits = result.get("nbHits", 0)
                elif isinstance(result, dict):
                    nb_hits = result.get("nbHits", 0)

                processing_time_ms = 0
                if hasattr(result, "get"):
                    processing_time_ms = result.get("processingTimeMS", 0)
                elif isinstance(result, dict):
                    processing_time_ms = result.get("processingTimeMS", 0)

                # Extract facets from result
                facets_dict = {}
                if hasattr(result, "get"):
                    facets_dict = result.get("facets", {})
                elif isinstance(result, dict):
                    facets_dict = result.get("facets", {})

                # Process facets dictionary
                categories_dict = {}
                if isinstance(facets_dict, dict) and "categories.name" in facets_dict:
                    categories_dict = facets_dict.get("categories.name", {})

                pricing_dict = {}
                if isinstance(facets_dict, dict) and "pricing.type" in facets_dict:
                    pricing_dict = facets_dict.get("pricing.type", {})

                # Update known categories
                for category_name, count in categories_dict.items():
                    self.known_categories[category_name.lower()] = {
                        "name": category_name,
                        "count": count,
                    }

                # Create facets objects
                facets = SearchFacets(
                    categories=[
                        SearchFacet(name=name, count=count)
                        for name, count in categories_dict.items()
                    ],
                    pricing_types=[
                        SearchFacet(name=name, count=count)
                        for name, count in pricing_dict.items()
                    ],
                )

                # Calculate total pages
                total_pages = (
                    (nb_hits + params.per_page - 1) // params.per_page
                    if params.per_page > 0
                    else 0
                )

                # Prepare the search result
                search_result = SearchResult(
                    tools=hits,
                    total=nb_hits,
                    page=params.page,
                    per_page=params.per_page,
                    pages=total_pages,
                    facets=facets,
                    processing_time_ms=processing_time_ms,
                )

                return search_result

        except Exception as e:
            logger.error(f"Error searching tools with Algolia: {str(e)}")
            # Return empty result on error
            return SearchResult(
                tools=[], total=0, page=params.page, per_page=params.per_page, pages=0
            )

    async def search_glossary(
        self, query: str, page: int = 1, per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Search glossary terms using Algolia

        Args:
            query: Search query
            page: Page number (1-based)
            per_page: Number of results per page

        Returns:
            Dictionary with search results
        """
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Returning empty glossary results.")
            return {
                "hits": [],
                "total": 0,
                "page": page,
                "pages": 0,
                "processing_time_ms": 0,
            }

        try:
            # Build search parameters
            search_args = {
                "query": query,
                "page": page - 1,  # Algolia uses 0-based pagination
                "hitsPerPage": per_page,
                "attributesToRetrieve": [
                    "term",
                    "definition",
                    "related_terms",
                    "categories",
                    "letter_group",
                ],
                "attributesToHighlight": ["term", "definition"],
                "highlightPreTag": "<mark>",
                "highlightPostTag": "</mark>",
            }

            # Execute search using v4 client syntax
            result = self.config.client.search_single_index(
                self.config.glossary_index_name, search_args
            )

            # Try accessing response properties (handling both object attributes and dictionary access)
            try:
                # Try accessing as object attributes first
                hits = result.hits if hasattr(result, "hits") else []
                nb_hits = result.nbHits if hasattr(result, "nbHits") else 0
                processing_time_ms = (
                    result.processingTimeMS
                    if hasattr(result, "processingTimeMS")
                    else 0
                )

                # Calculate total pages
                total_pages = (
                    (nb_hits + per_page - 1) // per_page if per_page > 0 else 0
                )

                # Prepare the search result
                search_result = {
                    "hits": hits,
                    "total": nb_hits,
                    "page": page,
                    "pages": total_pages,
                    "processing_time_ms": processing_time_ms,
                }

                return search_result

            except Exception as e:
                logger.warning(
                    f"Error accessing response properties as attributes: {str(e)}. Falling back to dictionary access."
                )

                # Fall back to dictionary access
                hits = result.get("hits", []) if hasattr(result, "get") else []
                if not hits and isinstance(result, dict):
                    hits = result.get("hits", [])

                nb_hits = 0
                if hasattr(result, "get"):
                    nb_hits = result.get("nbHits", 0)
                elif isinstance(result, dict):
                    nb_hits = result.get("nbHits", 0)

                processing_time_ms = 0
                if hasattr(result, "get"):
                    processing_time_ms = result.get("processingTimeMS", 0)
                elif isinstance(result, dict):
                    processing_time_ms = result.get("processingTimeMS", 0)

                # Calculate total pages
                total_pages = (
                    (nb_hits + per_page - 1) // per_page if per_page > 0 else 0
                )

                # Prepare the search result
                search_result = {
                    "hits": hits,
                    "total": nb_hits,
                    "page": page,
                    "pages": total_pages,
                    "processing_time_ms": processing_time_ms,
                }

                return search_result

        except Exception as e:
            logger.error(f"Error searching glossary with Algolia: {str(e)}")
            # Return empty result on error
            return {
                "hits": [],
                "total": 0,
                "page": page,
                "pages": 0,
                "processing_time_ms": 0,
            }

    async def process_natural_language_query(
        self, nlq: NaturalLanguageQuery
    ) -> ProcessedQuery:
        """
        Process a natural language query into structured search parameters

        Args:
            nlq: Natural language query object

        Returns:
            ProcessedQuery object with structured search parameters
        """
        if not self.openai_api_key:
            logger.warning("OpenAI API key not configured. Using original query as-is.")
            return ProcessedQuery(
                original_question=nlq.question, search_query=nlq.question
            )

        try:
            # Define the enhanced system prompt for query processing
            system_prompt = """
            You are an AI tools search expert tasked with analyzing natural language questions to convert them into 
            optimized search parameters for an AI tool directory. 
            
            Follow these steps carefully:
            
            1. Understand the user's intent and identify what type of AI tool they are looking for.
            2. Extract key search terms and relevant filters.
            3. Map to appropriate categories and pricing preferences.
            4. Prepare a concise search query focusing on the most relevant keywords.
            
            Categories available include: Content Creation, Writing, Image Generation, Video Generation, Audio Processing, 
            Chat, Code Generation, Data Analysis, Marketing, SEO, Social Media, Productivity, Research, Education, and more.
            
            Price types include: Free, Freemium, Paid, Enterprise, Contact.
            
            Examples:
            
            Question: "How can AI help my marketing team?"
            {
                "search_query": "marketing AI tools",
                "categories": ["Marketing", "Content Creation", "Social Media"],
                "pricing_types": null,
                "filters": null,
                "interpreted_intent": "Looking for AI tools that can assist marketing teams with various tasks"
            }
            
            Question: "I need a free tool for writing blog posts"
            {
                "search_query": "blog post writing generator",
                "categories": ["Writing", "Content Creation"],
                "pricing_types": ["Free", "Freemium"],
                "filters": null,
                "interpreted_intent": "Seeking free or freemium AI writing tools specifically for blog content"
            }
            
            Question: "Show me AI code generators for Python with good documentation"
            {
                "search_query": "Python code generator documentation",
                "categories": ["Code Generation", "Development"],
                "pricing_types": null,
                "filters": null,
                "interpreted_intent": "Looking for AI tools that generate Python code and have good documentation"
            }
            
            Question: "I need a tool for creating marketing videos quickly"
            {
                "search_query": "AI marketing video creator fast",
                "categories": ["Video Generation", "Marketing"],
                "pricing_types": null,
                "filters": null,
                "interpreted_intent": "Seeking tools that can quickly generate marketing videos using AI"
            }
            
            Respond with a JSON object containing search_query, categories, pricing_types, filters, and interpreted_intent.
            Keep search_query concise and focused on keywords (5-7 words max).
            Only include categories and pricing_types that are clearly implied.
            Use null (not empty arrays) when a field is not applicable.
            """

            # Create the chat messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": nlq.question},
            ]

            # Add context if provided
            if nlq.context:
                context_str = (
                    "Additional context about the user or their needs: "
                    + json.dumps(nlq.context)
                )
                messages.append({"role": "user", "content": context_str})

            # Call OpenAI API - handle both sync and async clients
            try:
                # For the new OpenAI client (v1.0+)
                try:
                    from openai import AsyncOpenAI

                    client = AsyncOpenAI(api_key=self.openai_api_key)
                    response = await client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=messages,
                        temperature=0.3,
                        max_tokens=300,
                    )
                    response_text = response.choices[0].message.content
                except (ImportError, AttributeError):
                    # If AsyncOpenAI is not available, use the synchronous client
                    client = openai.OpenAI(api_key=self.openai_api_key)
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=messages,
                        temperature=0.3,
                        max_tokens=300,
                    )
                    response_text = response.choices[0].message.content
            except Exception as api_error:
                # Last resort - fall back to legacy OpenAI API format
                try:
                    response = await openai.ChatCompletion.acreate(
                        model="gpt-3.5-turbo",
                        messages=messages,
                        temperature=0.3,
                        max_tokens=300,
                    )
                    response_text = response.choices[0].message.content
                except Exception as legacy_error:
                    logger.error(f"OpenAI API error (modern): {str(api_error)}")
                    logger.error(f"OpenAI API error (legacy): {str(legacy_error)}")
                    raise RuntimeError(f"Failed to call OpenAI API: {str(api_error)}")

            # Try to extract JSON from response
            try:
                # Handle potential markdown code blocks or extract JSON
                json_str = self._extract_json_from_text(response_text)
                processed_data = json.loads(json_str)

                # Normalize and validate pricing types
                pricing_types = await self._normalize_pricing_types(
                    processed_data.get("pricing_types")
                )

                # Normalize and validate categories
                categories = await self._normalize_categories(
                    processed_data.get("categories")
                )

                # Build filter string if needed
                filters = processed_data.get("filters")

                # If no explicit filters were provided but we have categories or pricing,
                # we'll let the search API build the filters

                # Create the processed query object
                processed_query = ProcessedQuery(
                    original_question=nlq.question,
                    search_query=processed_data.get("search_query", nlq.question),
                    filters=filters,
                    categories=categories,
                    pricing_types=pricing_types,
                    interpreted_intent=processed_data.get("interpreted_intent"),
                )

                logger.info(
                    f"Processed natural language query: '{nlq.question}' -> '{processed_query.search_query}'"
                )
                return processed_query

            except (json.JSONDecodeError, ValueError, IndexError) as e:
                logger.error(f"Error parsing NLP response: {str(e)}")
                # Perform basic keyword extraction as fallback
                return await self._basic_keyword_extraction(nlq.question)

        except Exception as e:
            logger.error(f"Error processing natural language query: {str(e)}")
            # Fallback to using the original query
            return ProcessedQuery(
                original_question=nlq.question, search_query=nlq.question
            )

    def _extract_json_from_text(self, text: str) -> str:
        """Extract JSON from text that may contain markdown or other formatting"""
        # Check for code blocks with JSON
        if "```json" in text:
            match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                return match.group(1)

        # Check for any code blocks
        if "```" in text:
            match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                return match.group(1)

        # Look for JSON-like structure with curly braces
        match = re.search(r"({.*})", text, re.DOTALL)
        if match:
            return match.group(1)

        # If no JSON structure found, return the original text
        return text.strip()

    async def _normalize_pricing_types(
        self, pricing_types: Optional[List[str]]
    ) -> Optional[List[PricingType]]:
        """Normalize and validate pricing types"""
        if not pricing_types:
            return None

        normalized = []
        for pt in pricing_types:
            pt_lower = pt.lower()
            if pt_lower in self.price_type_mapping:
                normalized.append(self.price_type_mapping[pt_lower])

        return normalized if normalized else None

    async def _normalize_categories(
        self, categories: Optional[List[str]]
    ) -> Optional[List[str]]:
        """Normalize and validate categories against known categories"""
        if not categories:
            return None

        # First check exact matches in known categories
        normalized = []
        for cat in categories:
            cat_lower = cat.lower()

            # Direct match in known categories
            if cat_lower in self.known_categories:
                normalized.append(self.known_categories[cat_lower]["name"])
                continue

            # Check synonyms
            matched = False
            for main_cat, synonyms in self.category_synonyms.items():
                if cat_lower == main_cat or any(
                    syn.lower() in cat_lower for syn in synonyms
                ):
                    # Find a known category that matches this synonym
                    for known_cat in self.known_categories:
                        if main_cat in known_cat.lower():
                            normalized.append(
                                self.known_categories[known_cat.lower()]["name"]
                            )
                            matched = True
                            break
                    if matched:
                        break

            # If no match found, use the original category
            if not matched:
                normalized.append(cat)

        return normalized if normalized else None

    async def _basic_keyword_extraction(self, question: str) -> ProcessedQuery:
        """
        Basic keyword extraction as a fallback when NLP processing fails
        """
        # Remove common stop words and extract key terms
        stop_words = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "is",
            "are",
            "for",
            "with",
            "to",
            "in",
            "on",
            "at",
            "by",
            "of",
        }
        words = question.lower().split()
        keywords = [word for word in words if word not in stop_words and len(word) > 2]

        # Create a simple search query from the keywords
        search_query = " ".join(keywords[:6])  # Limit to 6 keywords

        # Try to detect pricing intent
        pricing_types = None
        if any(
            word in question.lower()
            for word in ["free", "freemium", "open source", "opensource"]
        ):
            pricing_types = [PricingType.FREE, PricingType.FREEMIUM]

        # Try to detect categories
        categories = []
        for keyword in keywords:
            # Check for category keywords
            for main_cat, synonyms in self.category_synonyms.items():
                if keyword == main_cat or any(
                    syn.lower() == keyword for syn in synonyms
                ):
                    categories.append(main_cat.capitalize())

        categories = categories if categories else None

        return ProcessedQuery(
            original_question=question,
            search_query=search_query,
            filters=None,
            categories=categories,
            pricing_types=pricing_types,
            interpreted_intent=f"Extracted keywords from: {question}",
        )

    async def execute_nlp_search(
        self, nlq: NaturalLanguageQuery, page: int = 1, per_page: int = 20
    ) -> SearchResult:
        """
        Process natural language query and execute search

        Args:
            nlq: Natural language query object
            page: Page number (1-based)
            per_page: Number of results per page

        Returns:
            SearchResult object with tools and metadata
        """
        processed_query = None

        try:
            # Process the query to extract search parameters
            processed_query = await self.process_natural_language_query(nlq)

            # Create search parameters
            params = SearchParams(
                query=processed_query.search_query,  # Use search_query instead of query
                page=page,
                per_page=per_page,
                categories=processed_query.categories,
                pricing_types=processed_query.pricing_types,
                min_rating=getattr(
                    processed_query, "min_rating", None
                ),  # Use getattr for optional attributes
                sort_by=getattr(processed_query, "sort_by", None),
                filters=processed_query.filters,
            )

            # Execute the search with the extracted parameters
            search_result = await self.search_tools(params)

            # Create a new search result with the processed query to avoid field not found errors
            result = SearchResult(
                tools=search_result.tools,
                total=search_result.total,
                page=search_result.page,
                per_page=search_result.per_page,
                pages=search_result.pages,
                facets=search_result.facets,
                processing_time_ms=search_result.processing_time_ms,
                processed_query=processed_query,  # Add processed query
            )

            return result

        except Exception as e:
            logger.error(f"Error executing NLP search: {str(e)}")

            # If we couldn't process the query, create a basic one
            if processed_query is None:
                processed_query = ProcessedQuery(
                    original_question=nlq.question,
                    search_query=nlq.question,
                    filters=None,
                    categories=None,
                    pricing_types=None,
                    interpreted_intent="Failed to process with NLP",
                )

            # Return empty result on error, but include the processed query if available
            return SearchResult(
                tools=[],
                total=0,
                page=page,
                per_page=per_page,
                pages=0,
                processing_time_ms=0,
                processed_query=processed_query,
            )

    async def search_by_category(
        self, category: str, page: int = 1, per_page: int = 20
    ) -> SearchResult:
        """
        Search tools by category

        Args:
            category: Category to search for
            page: Page number (1-based)
            per_page: Number of results per page

        Returns:
            SearchResult object with tools and metadata
        """
        try:
            # Create search parameters with category filter
            params = SearchParams(
                query="",  # Empty query for category browsing
                page=page,
                per_page=per_page,
                filters=f"categories.id:{category}",  # Filter by category ID
                sort_by="trending",  # Sort by trending score for browsing
            )

            # Execute the search with the category filter
            return await self.search_tools(params)
        except Exception as e:
            logger.error(f"Error searching by category: {str(e)}")
            # Return empty result on error
            return SearchResult(
                tools=[], total=0, page=page, per_page=per_page, pages=0
            )


# Create singleton instance
algolia_search = AlgoliaSearch()


# Script mode for command-line testing
if __name__ == "__main__":
    import asyncio
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Test NLP-powered Algolia search from the command line"
    )
    parser.add_argument("query", nargs="?", help="Natural language query to process")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock data instead of real Algolia search",
    )
    parser.add_argument("--page", type=int, default=1, help="Page number")
    parser.add_argument("--per-page", type=int, default=10, help="Results per page")
    args = parser.parse_args()

    async def run_search():
        # If no query provided, prompt for one
        query = args.query
        if not query:
            query = input("Enter your natural language query: ")

        print(f"\nProcessing query: '{query}'")
        print("-" * 80)

        # Create NLQ object
        nlq = NaturalLanguageQuery(question=query)

        # Process the query
        processed_query = await algolia_search.process_natural_language_query(nlq)

        print("Processed Query:")
        print(f"  Search query: {processed_query.search_query}")
        print(f"  Categories: {processed_query.categories}")
        print(f"  Pricing types: {processed_query.pricing_types}")
        print(f"  Filters: {processed_query.filters}")
        print(f"  Interpreted intent: {processed_query.interpreted_intent}")
        print("-" * 80)

        # If mock mode, return mock results
        if args.mock:
            print("Generating mock search results...")

            # Create mock tools based on the query
            mock_tools = []
            question = query.lower()

            # Writing tool example
            if "writing" in question or "blog" in question or "content" in question:
                mock_tools.append(
                    {
                        "objectID": "writing-tool-1",
                        "name": "BlogGenius AI",
                        "description": "AI-powered blog post generator with SEO optimization",
                        "categories": [
                            {"id": "writing", "name": "Writing", "slug": "writing"},
                            {
                                "id": "content",
                                "name": "Content Creation",
                                "slug": "content-creation",
                            },
                        ],
                        "pricing": {"type": "Freemium", "starting_at": "$0"},
                    }
                )

            # Image tool example
            if "image" in question or "picture" in question or "photo" in question:
                mock_tools.append(
                    {
                        "objectID": "image-tool-1",
                        "name": "PixelMaster AI",
                        "description": "Create stunning images with AI in seconds",
                        "categories": [
                            {
                                "id": "image",
                                "name": "Image Generation",
                                "slug": "image-generation",
                            },
                            {"id": "design", "name": "Design", "slug": "design"},
                        ],
                        "pricing": {"type": "Freemium", "starting_at": "$0"},
                    }
                )

            # Add a generic AI tool if no specific matches
            if len(mock_tools) < 1:
                mock_tools.append(
                    {
                        "objectID": "ai-tool-generic",
                        "name": "AI Assistant Pro",
                        "description": "A versatile AI assistant for everyday tasks",
                        "categories": [
                            {
                                "id": "productivity",
                                "name": "Productivity",
                                "slug": "productivity",
                            },
                            {
                                "id": "assistant",
                                "name": "Assistant",
                                "slug": "assistant",
                            },
                        ],
                        "pricing": {"type": "Free", "starting_at": "$0"},
                    }
                )

            print(f"Found {len(mock_tools)} mock tools")
            for i, tool in enumerate(mock_tools, 1):
                print(f"\nResult {i}:")
                print(f"  Name: {tool['name']}")
                print(f"  Description: {tool['description']}")
                print(
                    f"  Categories: {', '.join(cat['name'] for cat in tool['categories'])}"
                )
                print(f"  Pricing: {tool['pricing']['type']}")

        else:
            # Execute the actual search
            try:
                print("Executing search against Algolia...")
                result = await algolia_search.execute_nlp_search(
                    nlq, page=args.page, per_page=args.per_page
                )

                print(
                    f"Found {result.total} tools (page {result.page} of {result.pages})"
                )
                print(f"Processing time: {result.processing_time_ms}ms")

                # Display results
                for i, tool in enumerate(result.tools, 1):
                    print(f"\nResult {i}:")
                    print(f"  Name: {tool.name}")
                    print(f"  Description: {tool.description}")
                    if tool.categories:
                        print(
                            f"  Categories: {', '.join(cat.name for cat in tool.categories)}"
                        )
                    if tool.pricing:
                        print(f"  Pricing: {tool.pricing.type}")

                if not result.tools:
                    print("No tools found matching your query.")
            except Exception as e:
                print(f"Error executing search: {str(e)}")
                print(
                    "Note: If Algolia is not configured, try adding --mock to use mock data."
                )

    # Run the async function
    asyncio.run(run_search())
