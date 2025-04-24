# app/algolia/search.py
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

    # Utility methods for extracting JSON from OpenAI responses
    def _extract_json_from_text(self, text: str) -> str:
        """Extract JSON data from text response"""
        # Check if the entire text is JSON
        if text.strip().startswith("{") and text.strip().endswith("}"):
            return text.strip()

        # Look for JSON-like structure with regex
        pattern = r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}"
        matches = re.findall(pattern, text)
        if matches:
            # Return the largest match as it's more likely to be the complete JSON
            return max(matches, key=len)

        return ""

    async def _normalize_categories(
        self, categories: Union[List[str], str]
    ) -> List[str]:
        """
        Normalize category names to category IDs

        Args:
            categories: List of category names or single category name

        Returns:
            List of normalized category IDs
        """
        # Placeholder implementation - ideally would map to actual category IDs
        if isinstance(categories, str):
            categories = [categories]
        return categories

    async def _normalize_pricing_types(
        self, pricing_types: Union[List[str], str]
    ) -> List[str]:
        """
        Normalize pricing type names to enum values

        Args:
            pricing_types: List of pricing type names or single pricing type name

        Returns:
            List of normalized pricing type enum values
        """
        if isinstance(pricing_types, str):
            pricing_types = [pricing_types]

        normalized = []
        for pt in pricing_types:
            pt_lower = pt.lower()
            if pt_lower in self.price_type_mapping:
                normalized.append(self.price_type_mapping[pt_lower])
            else:
                # Default to the original value if not found
                normalized.append(pt)

        return normalized

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
            optimized search parameters for an AI tool directory. Our database contains AI tools with the following structure:

            {
              "link": "https://replicate.com/playgroundai/playground-v2-1024px-aesthetic",
              "name": "playgroundai/playground-v2-1024px-aesthetic",
              "price": "Public",
              "rating": null,
              "unique_id": "playgroundai/playground-v2-1024px-aesthetic",
              "saved numbers": 447600,
              "category_id": "\"6806415d856a3a9ff0979444\"",
              "image_url": "https://tjzk.replicate.delivery/models_models_featured_image/e61adb01-bb73-448f-b2d5-3e8827577128/out-0.png",
              "logo_url": "",
              "description": "Playground v2 is a diffusion-based text-to-image generative model trained from scratch by the research team at Playground",
              "keywords": [
                "playground",
                "text-to-image",
                "generative model",
                "diffusion"
              ]
            }
            
            IMPORTANT: Our search focuses ONLY on the "keywords" and "description" fields. 
            Searching is restricted to these fields only.
            
            Follow these steps carefully:
            
            1. Understand the user's intent and identify what type of AI tool they are looking for.
            2. Extract key search terms that would match tool keywords or description.
            3. Identify any filters related to category or price if mentioned.
            4. Prepare a concise search query focusing on the most relevant keywords.
            
            Search parameters should include:
            
            1. search_query: The optimized keywords for the search (3-7 words max) that would match tool keywords or description
            2. price_filter: Price range or type if mentioned (Free, Paid, Public, etc.)
            3. keywords: Relevant tool keywords based on user's request
            4. interpreted_intent: A brief description of what the user is looking for
            
            Examples:
            
            Question: "I need an AI image generation tool"
            {
                "search_query": "text-to-image generative model",
                "price_filter": null,
                "keywords": ["AI", "Image Generation"],
                "interpreted_intent": "Looking for tools that can generate images from text"
            }
            
            Question: "Find me free diffusion models"
            {
                "search_query": "diffusion generative model",
                "price_filter": "Free",
                "keywords": ["image generation", "diffusion"],
                "interpreted_intent": "Seeking free diffusion-based image generation tools"
            }
            
            Question: "Show me playground AI tools"
            {
                "search_query": "playground AI",
                "price_filter": null,
                "keywords": ["playground", "AI"],
                "interpreted_intent": "Looking for AI tools from Playground"
            }
            """

            # Include the user's context info if available
            context_info = ""
            if nlq.context and hasattr(nlq.context, "items"):
                context_info = "User context information:\n"
                for k, v in nlq.context.items():
                    if v and str(v).strip():
                        context_info += f"- {k}: {str(v).strip()}\n"

            # Create the user prompt
            user_prompt = f"Question: {nlq.question}"
            if context_info:
                user_prompt += f"\n\n{context_info}"

            # Set up the messages for the chat completion
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Try to use the new OpenAI client format (v1.0+)
            try:
                import openai

                # Check if we're using the new OpenAI client (v1.0+)
                if hasattr(openai, "OpenAI"):
                    # New OpenAI client (v1.0+)
                    client = openai.OpenAI(api_key=self.openai_api_key)
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=messages,
                        temperature=0.1,
                        max_tokens=500,
                    )
                    response_text = response.choices[0].message.content
                else:
                    # Fall back to legacy client (<v1.0)
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=messages,
                        temperature=0.1,
                        max_tokens=500,
                    )
                    response_text = response.choices[0].message.content

                logger.info(f"OpenAI response: {response_text}")

            except (ImportError, AttributeError) as e:
                logger.error(f"Error with OpenAI API: {e}")
                # Use basic keyword extraction as fallback
                return await self._basic_keyword_extraction(nlq.question)

            # Extract JSON from the response
            json_str = self._extract_json_from_text(response_text)
            if not json_str:
                logger.warning("No valid JSON found in OpenAI response.")
                return ProcessedQuery(
                    original_question=nlq.question,
                    search_query=nlq.question,
                    interpreted_intent="Failed to extract structured query from natural language",
                )

            try:
                query_data = json.loads(json_str)
                logger.info(f"Extracted query data: {query_data}")

                # Extract query parameters from the parsed JSON
                search_query = query_data.get("search_query", nlq.question)
                price_filter = query_data.get("price_filter")
                rating_filter = query_data.get("rating_filter")
                categories = query_data.get("categories")
                interpreted_intent = query_data.get("interpreted_intent")

                # Convert pricing type names to enum values
                pricing_types = None
                if price_filter:
                    if isinstance(price_filter, list):
                        pricing_types = await self._normalize_pricing_types(
                            price_filter
                        )
                    else:
                        pricing_types = await self._normalize_pricing_types(
                            [price_filter]
                        )

                # Normalize categories if present
                if categories:
                    categories = await self._normalize_categories(categories)

                # Create the processed query object
                processed_query = ProcessedQuery(
                    original_question=nlq.question,
                    search_query=search_query,
                    filters=None,  # We'll build this from individual filters
                    categories=categories,
                    pricing_types=pricing_types,
                    interpreted_intent=interpreted_intent,
                    price_filter=price_filter,
                    rating_filter=rating_filter,
                    min_rating=rating_filter,  # Alias for backward compatibility
                )

                return processed_query

            except ValidationError as e:
                logger.error(f"Validation error processing query data: {str(e)}")
                # Fall back to using the original query on validation error
                return ProcessedQuery(
                    original_question=nlq.question,
                    search_query=nlq.question,
                    interpreted_intent="Error validating structured query",
                )

        except Exception as e:
            logger.error(f"Error processing natural language query: {str(e)}")
            # Fall back to using the original query on error
            return ProcessedQuery(
                original_question=nlq.question,
                search_query=nlq.question,
                interpreted_intent=f"Error processing with NLP: {str(e)}",
            )

    async def _basic_keyword_extraction(self, question: str) -> ProcessedQuery:
        """
        Basic keyword extraction fallback when OpenAI is not available
        Extracts meaningful keywords from a natural language question

        Args:
            question: The natural language question

        Returns:
            ProcessedQuery object with extracted search parameters
        """
        # Basic stopwords to filter out
        stopwords = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "if",
            "because",
            "as",
            "what",
            "which",
            "who",
            "whom",
            "this",
            "that",
            "these",
            "those",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "i",
            "me",
            "my",
            "mine",
            "you",
            "your",
            "yours",
            "he",
            "him",
            "his",
            "she",
            "her",
            "hers",
            "it",
            "its",
            "we",
            "us",
            "our",
            "ours",
            "they",
            "them",
            "their",
            "theirs",
            "want",
            "need",
            "looking",
            "for",
            "to",
            "of",
            "in",
            "on",
            "at",
            "by",
            "with",
            "about",
            "tool",
            "tools",
            "ai",
        }

        # Convert to lowercase and tokenize by splitting on spaces and punctuation
        words = re.findall(r"\b\w+\b", question.lower())

        # Filter out stopwords and short words
        keywords = [word for word in words if word not in stopwords and len(word) > 2]

        # Extract pricing information
        pricing_types = None
        if "free" in words:
            pricing_types = ["FREE"]
        elif "paid" in words or "premium" in words:
            pricing_types = ["PAID"]

        # Extract categories based on common keywords
        categories = None
        category_keywords = {
            "image": ["image", "photo", "picture", "art", "design", "graphic"],
            "writing": ["writing", "write", "text", "content", "article", "blog"],
            "video": ["video", "movie", "film", "animation"],
            "audio": ["audio", "sound", "music", "voice", "speech"],
            "code": ["code", "coding", "programming", "development", "software"],
        }

        # Check if any category keywords are in the question
        matched_categories = []
        for category, cat_keywords in category_keywords.items():
            if any(kw in words for kw in cat_keywords):
                matched_categories.append(category)

        if matched_categories:
            categories = matched_categories

        # Create a space-separated search query from keywords (limit to first 7)
        search_query = " ".join(keywords[:7])

        # Create the processed query
        return ProcessedQuery(
            original_question=question,
            search_query=search_query,
            filters=None,
            categories=categories,
            pricing_types=pricing_types,
            interpreted_intent=f"Basic keyword extraction from: {question}",
        )

    async def execute_nlp_search(
        self, nlq: NaturalLanguageQuery, page: int = 1, per_page: int = 20
    ) -> SearchResult:
        """
        Process natural language query and execute search
        Search is restricted to only the keywords and description fields.

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

            logger.info(
                f"NLP search query: '{processed_query.search_query}' - Search restricted to keywords and description"
            )

            # If Algolia is not configured, return empty results
            if not self.config.is_configured():
                logger.warning(
                    "Algolia not configured. Returning empty search results."
                )
                return SearchResult(
                    tools=[],
                    total=0,
                    page=page,
                    per_page=per_page,
                    pages=0,
                    processing_time_ms=0,
                    processed_query=processed_query,
                )

            # Build search parameters for Algolia
            search_args = {
                "query": processed_query.search_query,
                "page": page - 1,  # Algolia uses 0-based pagination
                "hitsPerPage": per_page,
                # Restrict search to only keywords and description fields
                "restrictSearchableAttributes": ["keywords", "description"],
            }

            # Add facet filters if provided
            facet_filters = []

            if processed_query.categories:
                category_filters = [
                    f"categories.id:{cat_id}" for cat_id in processed_query.categories
                ]
                facet_filters.append(category_filters)

            if processed_query.pricing_types:
                pricing_filters = [
                    f"pricing.type:{pricing}"
                    for pricing in processed_query.pricing_types
                ]
                facet_filters.append(pricing_filters)

            if processed_query.min_rating:
                # For numeric filters like ratings
                search_args["numericFilters"] = [
                    f"ratings.average>={processed_query.min_rating}"
                ]

            # Add custom filters if provided
            if processed_query.filters:
                search_args["filters"] = processed_query.filters

            # Add facet filters to search args if any
            if facet_filters:
                search_args["facetFilters"] = facet_filters

            # Request facets for filtering options
            search_args["facets"] = ["categories.name", "pricing.type", "features"]

            # Execute direct search using Algolia config client
            result = self.config.client.search_single_index(
                self.config.tools_index_name, search_args
            )

            # Extract data from the search response
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

                # Extract categories and pricing info for facets
                categories_dict = {}
                if hasattr(facets, "categories_name"):
                    categories_dict = facets.categories_name
                elif isinstance(facets, dict) and "categories.name" in facets:
                    categories_dict = facets["categories.name"]

                pricing_dict = {}
                if hasattr(facets, "pricing_type"):
                    pricing_dict = facets.pricing_type
                elif isinstance(facets, dict) and "pricing.type" in facets:
                    pricing_dict = facets["pricing.type"]

                # Create facets objects
                search_facets = SearchFacets(
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
                    (nb_hits + per_page - 1) // per_page if per_page > 0 else 0
                )

                # Create the search result
                search_result = SearchResult(
                    tools=hits,
                    total=nb_hits,
                    page=page,
                    per_page=per_page,
                    pages=total_pages,
                    facets=search_facets,
                    processing_time_ms=processing_time_ms,
                    processed_query=processed_query,
                )

                return search_result

            except Exception as e:
                logger.error(f"Error processing Algolia search results: {str(e)}")
                # Return empty result with the processed query on error
                return SearchResult(
                    tools=[],
                    total=0,
                    page=page,
                    per_page=per_page,
                    pages=0,
                    processing_time_ms=0,
                    processed_query=processed_query,
                )

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
