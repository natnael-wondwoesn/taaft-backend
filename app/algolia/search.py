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

            # Execute search
            result = self.config.tools_index.search(**search_args)

            # Log the search parameters and result summary
            logger.info(f"Algolia search with params: {search_args}")
            logger.info(f"Search found {result.get('nbHits', 0)} results")

            # Cache category information from facets
            if "facets" in result and "categories.name" in result["facets"]:
                for category_name, count in result["facets"]["categories.name"].items():
                    self.known_categories[category_name.lower()] = {
                        "name": category_name,
                        "count": count,
                    }

            # Extract facets
            facets = SearchFacets(
                categories=[
                    SearchFacet(name=name, count=count)
                    for name, count in result.get("facets", {})
                    .get("categories.name", {})
                    .items()
                ],
                pricing_types=[
                    SearchFacet(name=name, count=count)
                    for name, count in result.get("facets", {})
                    .get("pricing.type", {})
                    .items()
                ],
            )

            # Calculate total pages
            total_hits = result.get("nbHits", 0)
            total_pages = (
                (total_hits + params.per_page - 1) // params.per_page
                if params.per_page > 0
                else 0
            )

            # Prepare the search result
            search_result = SearchResult(
                tools=result.get("hits", []),
                total=total_hits,
                page=params.page,
                per_page=params.per_page,
                pages=total_pages,
                facets=facets,
                processing_time_ms=result.get("processingTimeMS"),
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
            logger.warning(
                "Algolia not configured. Returning empty glossary search results."
            )
            return {
                "terms": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "pages": 0,
            }

        try:
            # Execute search
            result = self.config.glossary_index.search(
                query,
                {
                    "page": page - 1,  # Algolia uses 0-based pagination
                    "hitsPerPage": per_page,
                    "facets": ["letter_group", "categories"],
                },
            )

            # Calculate total pages
            total_hits = result.get("nbHits", 0)
            total_pages = (total_hits + per_page - 1) // per_page if per_page > 0 else 0

            # Return the search result
            return {
                "terms": result.get("hits", []),
                "total": total_hits,
                "page": page,
                "per_page": per_page,
                "pages": total_pages,
                "facets": result.get("facets", {}),
                "processing_time_ms": result.get("processingTimeMS"),
            }

        except Exception as e:
            logger.error(f"Error searching glossary with Algolia: {str(e)}")
            # Return empty result on error
            return {
                "terms": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "pages": 0,
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

            # Call OpenAI API
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.3,
                max_tokens=300,
            )

            # Extract and parse the response
            response_text = response.choices[0].message.content

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
        Process a natural language query and execute search in one operation

        Args:
            nlq: Natural language query object
            page: Page number (1-based)
            per_page: Number of results per page

        Returns:
            SearchResult with processed query information
        """
        # Process the natural language query
        processed_query = await self.process_natural_language_query(nlq)

        # Create search parameters
        params = SearchParams(
            query=processed_query.search_query,
            categories=processed_query.categories,
            pricing_types=processed_query.pricing_types,
            page=page,
            per_page=per_page,
            filters=processed_query.filters,
        )

        # Execute search
        result = await self.search_tools(params)

        # Add the processed query to the result
        result_dict = result.dict()
        result_dict["processed_query"] = processed_query

        return SearchResult(**result_dict)

    async def search_by_category(
        self, category: str, page: int = 1, per_page: int = 20
    ) -> SearchResult:
        """
        Search for tools by category

        Args:
            category: Category ID or name to search for
            page: Page number (1-based)
            per_page: Number of results per page

        Returns:
            SearchResult with tools in the specified category
        """
        # Create search parameters with category filter
        params = SearchParams(
            query="",  # Empty query to match all documents
            categories=[category],  # Filter by this category
            page=page,
            per_page=per_page,
        )

        # Execute the search using the existing search method
        result = await self.search_tools(params)
        return result


# Create singleton instance
algolia_search = AlgoliaSearch()
