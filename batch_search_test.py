#!/usr/bin/env python3
"""
Batch test multiple NLP search queries from a file.
This is useful for testing a variety of query types at once.
"""
import os
import sys
from pathlib import Path
import asyncio
import argparse
import json
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.algolia.search import NaturalLanguageQuery, ProcessedQuery, algolia_search


async def process_queries(queries, output_file=None, mock=False):
    """Process multiple queries and optionally save the results"""
    results = []

    for i, query in enumerate(queries, 1):
        print(f"\n[{i}/{len(queries)}] Processing query: '{query}'")
        print("-" * 80)

        # Create NLQ object
        nlq = NaturalLanguageQuery(question=query)

        # Process the query
        try:
            processed_query = await algolia_search.process_natural_language_query(nlq)

            result = {
                "original_query": query,
                "processed_query": {
                    "search_query": processed_query.search_query,
                    "categories": processed_query.categories,
                    "pricing_types": (
                        [str(pt) for pt in processed_query.pricing_types]
                        if processed_query.pricing_types
                        else None
                    ),
                    "filters": processed_query.filters,
                    "interpreted_intent": processed_query.interpreted_intent,
                },
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"Error processing query: {str(e)}")
            print("Using fallback keyword processing...")

            # Use fallback keyword extraction
            search_query = basic_keyword_extraction(query)

            result = {
                "original_query": query,
                "processed_query": {
                    "search_query": search_query,
                    "categories": None,
                    "pricing_types": None,
                    "filters": None,
                    "interpreted_intent": f"Used fallback keyword extraction: {search_query}",
                },
                "fallback_used": True,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

            # Create a ProcessedQuery object for later use
            processed_query = ProcessedQuery(
                original_question=query,
                search_query=search_query,
                filters=None,
                categories=None,
                pricing_types=None,
                interpreted_intent=f"Used fallback keyword extraction: {search_query}",
            )

        # Print results
        print("Processed Query:")
        print(f"  Search query: {processed_query.search_query}")
        print(f"  Categories: {processed_query.categories}")
        print(f"  Pricing types: {processed_query.pricing_types}")
        print(f"  Filters: {processed_query.filters}")
        print(f"  Interpreted intent: {processed_query.interpreted_intent}")

        # If mock mode, add mock search results
        if mock:
            tools = await generate_mock_results(query)
            result["mock_results"] = tools
            print(f"Generated {len(tools)} mock results")

        results.append(result)

    # Save results if output file is specified
    if output_file:
        try:
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to {output_file}")
        except Exception as e:
            print(f"Error saving results: {str(e)}")

    return results


async def generate_mock_results(query):
    """Generate mock search results based on the query"""
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

    # Code tool example
    if "code" in question or "programming" in question or "developer" in question:
        mock_tools.append(
            {
                "objectID": "code-tool-1",
                "name": "CodeCompanion AI",
                "description": "AI assistant for developers that helps write, debug and optimize code",
                "categories": [
                    {
                        "id": "code",
                        "name": "Code Generation",
                        "slug": "code-generation",
                    },
                    {"id": "development", "name": "Development", "slug": "development"},
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
                    {"id": "assistant", "name": "Assistant", "slug": "assistant"},
                ],
                "pricing": {"type": "Free", "starting_at": "$0"},
            }
        )

    return mock_tools


# Simple fallback function for keyword extraction when OpenAI API fails
def basic_keyword_extraction(question: str) -> str:
    """Extract keywords from a natural language query as a fallback"""
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
        "about",
        "like",
        "what",
        "which",
        "who",
        "when",
        "where",
        "how",
        "why",
        "i",
        "me",
        "my",
        "mine",
        "we",
        "us",
        "our",
        "ours",
        "you",
        "your",
        "yours",
        "need",
        "want",
        "looking",
        "show",
        "find",
        "tell",
        "give",
        "help",
    }

    # Extract words that are not stop words
    words = question.lower().split()
    keywords = [word for word in words if word not in stop_words and len(word) > 2]

    # If we have no keywords, use the original query
    if not keywords:
        return question

    # Join the keywords
    return " ".join(keywords)


def main():
    parser = argparse.ArgumentParser(
        description="Batch test multiple NLP search queries"
    )
    parser.add_argument("input_file", help="File containing one query per line")
    parser.add_argument("--output", "-o", help="Output file to save results (JSON)")
    parser.add_argument(
        "--mock", action="store_true", help="Generate mock search results"
    )
    parser.add_argument(
        "--openai-key",
        help="OpenAI API key to use for processing (overrides environment variable)",
    )
    args = parser.parse_args()

    # Set OpenAI API key if provided
    if args.openai_key:
        os.environ["OPENAI_API_KEY"] = args.openai_key
        # Also set it directly on algolia_search
        algolia_search.openai_api_key = args.openai_key

    # Read queries from input file
    try:
        with open(args.input_file, "r") as f:
            # Skip empty lines and comments
            queries = [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]
    except Exception as e:
        print(f"Error reading input file: {str(e)}")
        return

    print(f"Loaded {len(queries)} queries from {args.input_file}")

    # Process queries
    asyncio.run(process_queries(queries, args.output, args.mock))

    print("\nBatch processing complete.")


if __name__ == "__main__":
    main()
