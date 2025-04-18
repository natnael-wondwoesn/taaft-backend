# utils/test_nlp_search.py
"""
Utility script to test the NLP search functionality
Run this script to check if the NLP search is working as expected
"""
import asyncio
import json
import sys
import os

# Add the parent directory to sys.path so we can import the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from app.algolia.models import NaturalLanguageQuery, ProcessedQuery
from app.algolia.search import algolia_search

# Load environment variables
load_dotenv()

# Test queries
TEST_QUERIES = [
    "I need a free AI tool to help write blog posts",
    "What are the best image generation tools for marketing?",
    "Show me AI code assistants with good documentation",
    "I'm looking for an AI that can transcribe my meetings",
    "Can AI help with data visualization for my research?",
    "What AI tools can help me with social media content?",
]


async def test_nlp_search():
    """Run tests on the NLP search functionality"""
    print("Testing NLP Search Functionality\n")

    if not algolia_search.openai_api_key:
        print(
            "ERROR: OpenAI API Key not configured. Set OPENAI_API_KEY in your .env file."
        )
        return

    if not algolia_search.config.is_configured():
        print(
            "WARNING: Algolia not configured. Only testing NLP processing, not actual search."
        )

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\nTest Query {i}: '{query}'")
        print("-" * 80)

        # Create NLP query object
        nlq = NaturalLanguageQuery(question=query)

        # Process the query
        processed_query = await algolia_search.process_natural_language_query(nlq)

        # Display the processed query
        print(f"Original Question: {processed_query.original_question}")
        print(f"Search Query: {processed_query.search_query}")
        print(f"Categories: {processed_query.categories}")
        print(f"Pricing Types: {processed_query.pricing_types}")
        print(f"Filters: {processed_query.filters}")
        print(f"Interpreted Intent: {processed_query.interpreted_intent}")

        # If Algolia is configured, also test the search
        if algolia_search.config.is_configured():
            print("\nExecuting search...")
            result = await algolia_search.execute_nlp_search(nlq, page=1, per_page=5)
            print(f"Found {result.total} results")
            print(f"Top results: {', '.join([tool.name for tool in result.tools[:3]])}")

        print("-" * 80)


if __name__ == "__main__":
    asyncio.run(test_nlp_search())
