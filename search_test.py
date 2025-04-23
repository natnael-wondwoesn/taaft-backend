#!/usr/bin/env python3
"""
A simple wrapper script to run NLP search tests.
This makes it easier to access the search features from the command line.
"""
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.algolia.search import NaturalLanguageQuery, ProcessedQuery, algolia_search
import asyncio
import argparse


def main():
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
    parser.add_argument(
        "--process-only",
        action="store_true",
        help="Only process the query, don't search",
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
        try:
            processed_query = await algolia_search.process_natural_language_query(nlq)
        except Exception as e:
            print(f"Error processing query: {str(e)}")
            print("Using fallback keyword processing...")
            # Use a basic fallback method with keyword extraction
            search_query = basic_keyword_extraction(query)
            processed_query = ProcessedQuery(
                original_question=query,
                search_query=search_query,
                filters=None,
                categories=None,
                pricing_types=None,
                interpreted_intent=f"Used fallback keyword extraction: {search_query}",
            )

        print("Processed Query:")
        print(f"  Search query: {processed_query.search_query}")
        print(f"  Categories: {processed_query.categories}")
        print(f"  Pricing types: {processed_query.pricing_types}")
        print(f"  Filters: {processed_query.filters}")
        print(f"  Interpreted intent: {processed_query.interpreted_intent}")
        print("-" * 80)

        # If process-only flag is set, stop here
        if args.process_only:
            return

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

            # Code tool example
            if (
                "code" in question
                or "programming" in question
                or "developer" in question
            ):
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
                            {
                                "id": "development",
                                "name": "Development",
                                "slug": "development",
                            },
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


if __name__ == "__main__":
    main()
