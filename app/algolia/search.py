# app/algolia/search.py
"""
Search service for Algolia integration
Handles tool search and natural language query processing
"""
from typing import Dict, List, Optional, Any, Union
import datetime
import json
import openai
import os
from pydantic import ValidationError

from .config import algolia_config
from .models import (
    SearchParams,
    SearchResult,
    SearchFacets,
    SearchFacet,
    NaturalLanguageQuery,
    ProcessedQuery,
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
            search_args["facets"] = ["categories.name", "pricing.type"]

            # Execute search
            result = self.config.tools_index.search(**search_args)

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
                    "facets": ["letter_group"],
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
            # Define the system prompt for query processing
            system_prompt = """
            You are an AI tools search expert. Your task is to analyze a user's natural language question and convert it 
            into an optimized search query and filters for an AI tool directory.
            
            Examples:
            
            Question: "How can AI help my marketing team?"
            {
                "search_query": "AI marketing tools",
                "categories": ["Marketing", "Content Creation"],
                "pricing_types": null,
                "interpreted_intent": "Looking for AI tools that can assist with marketing tasks"
            }
            
            Question: "I need a free tool for writing blog posts"
            {
                "search_query": "blog post writing",
                "categories": ["Content Creation", "Writing"],
                "pricing_types": ["Free", "Freemium"],
                "interpreted_intent": "Seeking free AI writing tools for blog content"
            }
            
            Respond with a JSON object containing search_query, categories, pricing_types, and interpreted_intent.
            Keep search_query concise and focused on keywords. Only include categories and pricing_types if clearly implied.
            """

            # Create the chat messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": nlq.question},
            ]

            # Add context if provided
            if nlq.context:
                context_str = "Additional context: " + json.dumps(nlq.context)
                messages.append({"role": "user", "content": context_str})

            # Call OpenAI API
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.3,
                max_tokens=200,
            )

            # Extract and parse the response
            response_text = response.choices[0].message.content

            # Try to extract JSON from response
            try:
                # Handle potential markdown code blocks
                if "```json" in response_text:
                    json_str = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    json_str = response_text.split("```")[1].strip()
                else:
                    json_str = response_text.strip()

                processed_data = json.loads(json_str)

                # Create the processed query object
                processed_query = ProcessedQuery(
                    original_question=nlq.question,
                    search_query=processed_data.get("search_query", nlq.question),
                    filters=None,  # We'll build this from individual filters if needed
                    categories=processed_data.get("categories"),
                    pricing_types=processed_data.get("pricing_types"),
                    interpreted_intent=processed_data.get("interpreted_intent"),
                )

                return processed_query

            except (json.JSONDecodeError, ValueError, IndexError) as e:
                logger.error(f"Error parsing NLP response: {str(e)}")
                # Fallback to using the original query
                return ProcessedQuery(
                    original_question=nlq.question, search_query=nlq.question
                )

        except Exception as e:
            logger.error(f"Error processing natural language query: {str(e)}")
            # Fallback to using the original query
            return ProcessedQuery(
                original_question=nlq.question, search_query=nlq.question
            )


# Create singleton instance
algolia_search = AlgoliaSearch()
