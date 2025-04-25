"""
Test script for tools formatter with all hits
"""

import json
import sys
import os
from typing import Dict, Any

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.algolia.tools_formatter import format_tools_to_desired_format
from app.algolia.search import algolia_search


async def test_all_hits_formatter():
    """Test the tools formatter with a large number of hits to ensure all are processed"""

    print("\nTesting tools formatter with all hits...")

    # Perform a search that should return many results
    keywords = ["ai", "automation", "chatbot", "productivity"]
    print(f"Searching with keywords: {keywords}")

    # Perform the search with maximum hits per page
    search_results = await algolia_search.perform_keyword_search(
        keywords, per_page=1000
    )

    # Check the number of hits returned by Algolia
    total_hits = search_results.get("nbHits", 0)
    actual_hits = len(search_results.get("hits", []))

    print(f"Algolia search returned nbHits: {total_hits}, actual hits: {actual_hits}")

    # Format the data
    formatted_data = format_tools_to_desired_format(search_results)

    # Check the number of hits in the formatted data
    formatted_hits = len(formatted_data.get("hits", []))
    formatted_total = formatted_data.get("nbHits", 0)

    print(
        f"Formatted data contains {formatted_hits} hits out of {formatted_total} total"
    )

    # Verify that we're preserving the correct hit count
    assert (
        formatted_total == total_hits
    ), f"Expected nbHits to be {total_hits}, got {formatted_total}"

    # Verify that we're formatting all available hits
    assert (
        formatted_hits == actual_hits
    ), f"Expected {actual_hits} formatted hits, got {formatted_hits}"

    # Check a few hits to ensure they're properly formatted
    if formatted_hits > 0:
        print("\nSample of formatted hits:")
        for i in range(min(3, formatted_hits)):
            hit = formatted_data["hits"][i]
            print(f"\nHit {i+1}:")
            print(f"  objectID: {hit.get('objectID', 'MISSING')}")
            print(f"  name: {hit.get('name', 'MISSING')}")
            print(f"  description: {hit.get('description', 'MISSING')[:50]}...")

            # Verify all required fields are present
            required_fields = [
                "objectID",
                "name",
                "description",
                "link",
                "logo_url",
                "category_id",
                "unique_id",
                "price",
                "rating",
            ]

            for field in required_fields:
                assert field in hit, f"Required field '{field}' missing from hit {i+1}"
                assert hit[field] is not None, f"Field '{field}' is None in hit {i+1}"

    print("\nAll checks passed. Formatter is correctly processing all hits.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_all_hits_formatter())
