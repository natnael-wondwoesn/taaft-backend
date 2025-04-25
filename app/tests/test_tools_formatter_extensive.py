"""
Extensive test script for tools formatter
Tests multiple scenarios including high hit counts, edge cases, and unusual data formats
"""

import json
import sys
import os
import time
from typing import Dict, List, Any, Union
import asyncio
from copy import deepcopy

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.algolia.tools_formatter import format_tools_to_desired_format
from app.algolia.search import algolia_search


async def test_real_search_high_hit_count():
    """Test with a real search that should return a large number of hits"""
    print("\n=== Testing with real search (high hit count) ===")
    keywords = ["ai", "automation", "assistant", "productivity", "chatbot"]
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

    return True


def test_edge_cases():
    """Test edge cases such as empty results, null values, and unusual data structures"""
    print("\n=== Testing edge cases ===")

    # Case 1: Empty results
    print("\nCase 1: Empty results")
    empty_results = {"hits": [], "nbHits": 0}
    formatted_empty = format_tools_to_desired_format(empty_results)
    assert formatted_empty["nbHits"] == 0, "NbHits should be 0 for empty results"
    assert (
        len(formatted_empty["hits"]) == 0
    ), "No hits should be returned for empty results"
    print("✓ Empty results handled correctly")

    # Case 2: None results
    print("\nCase 2: None results")
    none_results = None
    formatted_none = format_tools_to_desired_format(none_results)
    assert formatted_none["nbHits"] == 0, "NbHits should be 0 for None results"
    assert (
        len(formatted_none["hits"]) == 0
    ), "No hits should be returned for None results"
    print("✓ None results handled correctly")

    # Case 3: Mixed type of hit objects
    print("\nCase 3: Mixed type hit objects")
    mixed_results = {
        "hits": [
            {
                "objectID": "1",
                "name": "Regular Hit",
                "description": "A normal hit object",
            },
            # A custom object with attributes instead of dict keys
            type(
                "CustomHit",
                (),
                {
                    "objectID": "2",
                    "name": "Custom Hit Object",
                    "description": "This is a custom object with attributes",
                },
            ),
            # Minimal hit with just an ID
            {"objectID": "3"},
            # Hit with None values
            {
                "objectID": "4",
                "name": None,
                "description": None,
                "link": None,
                "logo_url": None,
                "category_id": None,
                "unique_id": None,
                "price": None,
                "rating": None,
            },
        ],
        "nbHits": 4,
    }

    formatted_mixed = format_tools_to_desired_format(mixed_results)
    assert formatted_mixed["nbHits"] == 4, "NbHits should be 4 for mixed results"
    assert (
        len(formatted_mixed["hits"]) == 4
    ), "All 4 hits should be returned for mixed results"

    # Check that each hit has all required fields
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

    for i, hit in enumerate(formatted_mixed["hits"]):
        for field in required_fields:
            assert field in hit, f"Required field '{field}' missing from hit {i+1}"
            assert hit[field] is not None, f"Field '{field}' is None in hit {i+1}"

    print("✓ Mixed type hit objects handled correctly")

    return True


def test_simulated_high_hit_count():
    """Test with simulated high hit count to ensure all hits are processed"""
    print("\n=== Testing with simulated high hit count ===")

    # Create a sample hit template
    template_hit = {
        "objectID": "template",
        "name": "Template Tool",
        "description": "This is a template tool description",
        "link": "https://example.com/tool",
        "logo_url": "https://example.com/logo.png",
        "category_id": '"category123"',
        "unique_id": "template-tool",
        "price": "Free",
        "rating": "4.5",
    }

    # Generate 204 hits based on the template (the number mentioned in the issue)
    simulated_hits = []
    for i in range(204):
        hit = deepcopy(template_hit)
        hit["objectID"] = f"sim-{i}"
        hit["name"] = f"Simulated Tool {i}"
        hit["unique_id"] = f"simulated-tool-{i}"
        simulated_hits.append(hit)

    simulated_results = {
        "hits": simulated_hits,
        "nbHits": 204,
    }

    # Measure performance
    start_time = time.time()
    formatted_high_count = format_tools_to_desired_format(simulated_results)
    end_time = time.time()

    format_time = end_time - start_time
    print(f"Time to format 204 hits: {format_time:.4f} seconds")

    assert formatted_high_count["nbHits"] == 204, "NbHits should be 204"
    assert len(formatted_high_count["hits"]) == 204, "All 204 hits should be returned"

    # Verify the first and last hit to ensure they're properly formatted
    first_hit = formatted_high_count["hits"][0]
    last_hit = formatted_high_count["hits"][-1]

    assert (
        first_hit["name"] == "Simulated Tool 0"
    ), "First hit should be correctly formatted"
    assert (
        last_hit["name"] == "Simulated Tool 203"
    ), "Last hit should be correctly formatted"

    # Verify category_id is properly formatted (quotes removed)
    for hit in [first_hit, last_hit]:
        assert (
            hit["category_id"] == "category123"
        ), "Category ID should have quotes removed"

    print(f"✓ Successfully formatted all 204 hits in {format_time:.4f} seconds")
    return True


def test_unusual_data_formats():
    """Test with unusual data formats to ensure robust handling"""
    print("\n=== Testing unusual data formats ===")

    # Case 1: Different structure for hits
    print("\nCase 1: Different structure for hits")
    unusual_format = {
        "results": {  # Nested results structure
            "items": [  # Different key for hits
                {
                    "id": "unusual-1",  # Different key for objectID
                    "title": "Unusual Tool",  # Different key for name
                    "summary": "This is an unusual tool",  # Different key for description
                    "url": "https://example.com/unusual",  # Different key for link
                    "image": "https://example.com/image.png",  # Different key for logo_url
                }
            ],
            "total": 1,  # Different key for nbHits
        }
    }

    # The formatter should handle this by using the default empty structure
    formatted_unusual = format_tools_to_desired_format(unusual_format)

    # Since our formatter doesn't try to map these different keys, we expect defaults
    assert formatted_unusual["nbHits"] == 0, "Should fall back to default handling"
    assert len(formatted_unusual["hits"]) == 0, "Should fall back to default handling"
    print("✓ Unusual format handled safely (returns empty defaults)")

    # Case 2: Extra fields in hits
    print("\nCase 2: Extra fields in hits")
    extra_fields = {
        "hits": [
            {
                "objectID": "extra-1",
                "name": "Extra Fields Tool",
                "description": "This tool has extra fields",
                "link": "https://example.com/extra",
                "logo_url": "https://example.com/logo.png",
                "category_id": '"category456"',
                "unique_id": "extra-fields-tool",
                "price": "Paid",
                "rating": "4.8",
                "extra_field_1": "This should be ignored",
                "extra_field_2": {
                    "nested": "data",
                    "that": ["should", "be", "ignored"],
                },
                "metrics": {
                    "views": 1000,
                    "downloads": 500,
                    "ratings": [5, 4, 5, 5, 4],
                },
            }
        ],
        "nbHits": 1,
    }

    formatted_extra = format_tools_to_desired_format(extra_fields)
    assert formatted_extra["nbHits"] == 1, "NbHits should be 1"
    assert len(formatted_extra["hits"]) == 1, "Should return 1 hit"

    # Verify the hit only contains the expected fields
    expected_fields = [
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

    hit_keys = list(formatted_extra["hits"][0].keys())
    assert sorted(hit_keys) == sorted(
        expected_fields
    ), "Hit should only contain expected fields"

    # Check that category_id is properly formatted
    assert (
        formatted_extra["hits"][0]["category_id"] == "category456"
    ), "Category ID should have quotes removed"

    print("✓ Extra fields handled correctly (ignored)")

    return True


async def run_all_tests():
    """Run all tests and report results"""
    tests = [
        ("Real search with high hit count", test_real_search_high_hit_count),
        ("Edge cases", test_edge_cases),
        ("Simulated high hit count", test_simulated_high_hit_count),
        ("Unusual data formats", test_unusual_data_formats),
    ]

    results = []

    for name, test_func in tests:
        print(f"\n{'=' * 50}")
        print(f"Running test: {name}")
        print(f"{'=' * 50}")

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
    print("\n\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)

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
