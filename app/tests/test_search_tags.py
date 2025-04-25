"""
Test script to verify search query tags are correctly embedded in formatted hits
"""

import json
import sys
import os
from typing import Dict, List, Any
import asyncio

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.algolia.tools_formatter import format_tools_to_desired_format
from app.algolia.search import algolia_search


async def test_embedded_search_tags_with_real_search():
    """Test that search query tags are properly embedded in real search results"""
    print("\n=== Testing embedded search tags with real search ===")

    # Define search terms that should appear as tags
    search_terms = ["ai", "chatbot", "productivity"]
    search_query = ", ".join(search_terms)
    print(f"Searching with query: '{search_query}'")

    # Perform a real search
    search_results = await algolia_search.perform_keyword_search(
        search_terms, per_page=20
    )

    # Check if search returned results
    total_hits = search_results.get("nbHits", 0)
    if total_hits == 0:
        print("No search results found. Cannot verify tags.")
        return False

    # Format the results
    formatted_data = format_tools_to_desired_format(search_results)
    formatted_hits = len(formatted_data.get("hits", []))

    print(f"Retrieved and formatted {formatted_hits} hits")

    # Verify search tags are present in all hits
    if formatted_hits > 0:
        # Check the first hit for tags
        first_hit = formatted_data["hits"][0]
        print(f"\nExample hit ({first_hit.get('name', 'Unknown')}):")

        # Verify search_tags field exists and contains expected tags
        assert "search_tags" in first_hit, "search_tags field is missing"

        # Print the actual tags for inspection
        print(f"  search_tags: {first_hit['search_tags']}")

        # Verify all hits have the search_tags field with the same tags
        for hit in formatted_data["hits"]:
            assert "search_tags" in hit, "search_tags field is missing in a hit"
            assert isinstance(hit["search_tags"], list), "search_tags is not a list"

            # Verify tags match the search terms (order might be different)
            for term in search_terms:
                assert (
                    term in hit["search_tags"]
                ), f"Expected tag '{term}' not found in search_tags"

        print(f"✓ All {formatted_hits} hits contain the correct search tags")

    return True


def test_embedded_search_tags_with_mock_data():
    """Test that search query tags are properly embedded in mock search results"""
    print("\n=== Testing embedded search tags with mock data ===")

    # Test cases with different search query formats
    test_cases = [
        {
            "name": "Simple query",
            "query": "productivity tool",
            "expected_tags": ["productivity", "tool"],
        },
        {
            "name": "Comma-separated query",
            "query": "ai, automation, assistant",
            "expected_tags": ["ai", "automation", "assistant"],
        },
        {
            "name": "Mixed format query",
            "query": "chatbot, virtual assistant automation",
            "expected_tags": ["chatbot", "virtual", "assistant", "automation"],
        },
        {"name": "Empty query", "query": "", "expected_tags": []},
    ]

    for test_case in test_cases:
        print(f"\nTesting: {test_case['name']}")
        print(f"Query: '{test_case['query']}'")

        # Create mock search results with the test query
        mock_results = {
            "hits": [
                {
                    "objectID": "1",
                    "name": "Test Tool 1",
                    "description": "A test tool",
                    "link": "https://example.com",
                    "logo_url": "https://example.com/logo.png",
                },
                {
                    "objectID": "2",
                    "name": "Test Tool 2",
                    "description": "Another test tool",
                    "link": "https://example.com/tool2",
                    "logo_url": "",
                },
            ],
            "nbHits": 2,
            "query": test_case["query"],
        }

        # Format the mock results
        formatted_data = format_tools_to_desired_format(mock_results)

        # Check the tags in the formatted hits
        for hit in formatted_data["hits"]:
            assert "search_tags" in hit, "search_tags field is missing"

            actual_tags = hit["search_tags"]
            expected_tags = test_case["expected_tags"]

            print(f"  Expected tags: {expected_tags}")
            print(f"  Actual tags: {actual_tags}")

            # Check that all expected tags are present
            if expected_tags:
                for tag in expected_tags:
                    assert (
                        tag in actual_tags
                    ), f"Expected tag '{tag}' not found in search_tags"
            else:
                # If no tags expected, verify empty list
                assert (
                    len(actual_tags) == 0
                ), "Expected empty tags list but got some tags"

            # Check no unexpected tags
            assert len(actual_tags) == len(
                expected_tags
            ), "Unexpected number of tags found"

        print(f"✓ {test_case['name']} - Tags correctly embedded")

    return True


async def run_all_tests():
    """Run all tag embedding tests and report results"""
    tests = [
        (
            "Embedded search tags with real search",
            test_embedded_search_tags_with_real_search,
        ),
        (
            "Embedded search tags with mock data",
            test_embedded_search_tags_with_mock_data,
        ),
    ]

    results = []

    for name, test_func in tests:
        print(f"\n{'=' * 60}")
        print(f"Running test: {name}")
        print(f"{'=' * 60}")

        try:
            if asyncio.iscoroutinefunction(test_func):
                success = await test_func()
            else:
                success = test_func()

            results.append((name, success, None))
            print(f"\n✓ Test '{name}' PASSED")
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"\n✗ Test '{name}' FAILED: {str(e)}")

    # Print summary
    print("\n\n" + "=" * 60)
    print("SEARCH TAGS TEST SUMMARY")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, success, error in results:
        if success:
            print(f"✓ {name}: PASSED")
            passed += 1
        else:
            print(f"✗ {name}: FAILED - {error}")
            failed += 1

    print(f"\nTOTAL: {len(results)} tests, {passed} passed, {failed} failed")

    # Return True only if all tests passed
    return all(success for _, success, _ in results)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
