"""
Test script that specifically verifies the fix for the reported issue
where 204 hits are available but only 10 were returned in formatted data
"""

import json
import sys
import os
import time
from copy import deepcopy
from typing import Dict, List, Any

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.algolia.tools_formatter import format_tools_to_desired_format


def test_204_hit_issue():
    """
    Specifically test the reported issue where 204 hits are available
    but only 10 are returned in the formatted data
    """
    print("\n=== Testing the specific 204 hit issue ===")

    # Create a template hit with all required fields
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
        "keywords": ["ai", "tool", "automation"],
        "extra_field": "This should be ignored",
    }

    # Generate exactly 204 hits (the number mentioned in the issue)
    mock_hits = []
    for i in range(204):
        hit = deepcopy(template_hit)
        hit["objectID"] = f"hit-{i}"
        hit["name"] = f"Test Tool {i}"
        hit["description"] = f"Description for test tool {i}"
        hit["unique_id"] = f"test-tool-{i}"

        # Add some variety to the data
        if i % 3 == 0:
            hit["price"] = "Paid"
        elif i % 3 == 1:
            hit["price"] = "Freemium"

        if i % 5 == 0:
            hit["category_id"] = '"category456"'

        mock_hits.append(hit)

    # Create a mock search result with exactly 204 hits
    mock_results = {
        "hits": mock_hits,
        "nbHits": 204,
        "page": 0,
        "nbPages": 21,  # With 10 hits per page, we'd need 21 pages
        "hitsPerPage": 10,  # Simulate the 10 hit pagination limit
        "processingTimeMS": 42,
        "query": "ai tool automation chatbot",  # Added search query for tags
        "params": "query=ai%20tool%20automation%20chatbot",
    }

    print(f"Created mock dataset with {len(mock_hits)} hits")

    # Time the formatting operation
    start_time = time.time()
    formatted_data = format_tools_to_desired_format(mock_results)
    end_time = time.time()

    formatting_time = end_time - start_time
    print(f"Time to format data: {formatting_time:.4f} seconds")

    # Check the formatted data
    formatted_hits = len(formatted_data.get("hits", []))
    formatted_total = formatted_data.get("nbHits", 0)

    print(
        f"Formatted data contains {formatted_hits} hits out of {formatted_total} total hits"
    )

    # Verify that ALL hits are included
    assert formatted_hits == 204, f"Expected 204 hits, but got {formatted_hits}"
    assert (
        formatted_total == 204
    ), f"Expected nbHits to be 204, but got {formatted_total}"

    # Verify the first, middle, and last hits for quality check
    first_hit = formatted_data["hits"][0]
    middle_hit = formatted_data["hits"][102]
    last_hit = formatted_data["hits"][203]

    # Check that the hits are correctly formatted
    assert first_hit["name"] == "Test Tool 0", "First hit not formatted correctly"
    assert middle_hit["name"] == "Test Tool 102", "Middle hit not formatted correctly"
    assert last_hit["name"] == "Test Tool 203", "Last hit not formatted correctly"

    # Verify category_id is correctly processed (quotes removed)
    assert (
        first_hit["category_id"] == "category456"
    ), "Category ID not formatted correctly"
    assert middle_hit["category_id"] == (
        "category456" if 102 % 5 == 0 else "category123"
    ), "Category ID not formatted correctly"

    # Check that no extra fields are included
    for hit in [first_hit, middle_hit, last_hit]:
        assert "extra_field" not in hit, "Extra field was included in the formatted hit"
        assert "keywords" not in hit, "Keywords field was included in the formatted hit"

    # Verify all required fields are present in every hit
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
        "search_tags",
    ]

    for i, hit in enumerate(formatted_data["hits"]):
        for field in required_fields:
            assert field in hit, f"Required field '{field}' missing from hit {i}"
            assert (
                hit[field] is not None
            ), f"Required field '{field}' is None in hit {i}"

    # Verify search tags are correctly embedded
    expected_tags = ["ai", "tool", "automation", "chatbot"]
    first_hit_tags = first_hit.get("search_tags", [])

    print(f"\nVerifying search tags in hits...")
    print(f"First hit search tags: {first_hit_tags}")

    # Check all expected tags are in each hit
    for tag in expected_tags:
        assert tag in first_hit_tags, f"Expected tag '{tag}' missing from first hit"
        assert tag in middle_hit.get(
            "search_tags", []
        ), f"Expected tag '{tag}' missing from middle hit"
        assert tag in last_hit.get(
            "search_tags", []
        ), f"Expected tag '{tag}' missing from last hit"

    print("\n✓ All 204 hits were correctly formatted with all required fields")
    print("✓ The issue where only 10 hits were returned has been fixed")
    print("✓ Search tags were correctly embedded in all hits")

    return True


if __name__ == "__main__":
    result = test_204_hit_issue()
    print(f"\nTest {'PASSED' if result else 'FAILED'}")
