"""
Test script for pagination handling in the Algolia search and formatter
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


async def test_pagination_retrieval():
    """Test retrieving and formatting results across multiple pages"""
    print("\n=== Testing pagination handling ===")

    # Use a common search term that should return many results
    keywords = ["ai", "productivity"]

    # Set a small per_page value to force pagination
    per_page = 10

    # First, do a search with a high per_page to get the total number of hits
    print("\nGetting total hit count with high per_page...")
    full_results = await algolia_search.perform_keyword_search(keywords, per_page=1000)
    total_hits = full_results.get("nbHits", 0)
    print(f"Total hits available: {total_hits}")

    if total_hits == 0:
        print("No results found, cannot test pagination")
        return False

    # Now perform paginated searches
    print(f"\nRetrieving results in chunks of {per_page}...")
    paginated_hits = []

    # Calculate number of pages needed
    pages_needed = (total_hits + per_page - 1) // per_page  # Ceiling division
    pages_to_retrieve = min(5, pages_needed)  # Limit to 5 pages for test duration

    print(f"Will retrieve {pages_to_retrieve} pages out of {pages_needed}")

    for page in range(pages_to_retrieve):
        print(f"Retrieving page {page+1}...")
        page_results = await algolia_search.perform_keyword_search(
            keywords, page=page, per_page=per_page
        )

        page_hits = page_results.get("hits", [])
        page_hit_count = len(page_hits)
        print(f"Retrieved {page_hit_count} hits from page {page+1}")

        paginated_hits.extend(page_hits)

    # Create a combined result object
    combined_results = {
        "hits": paginated_hits,
        "nbHits": total_hits,
    }

    print(
        f"\nRetrieved {len(paginated_hits)} hits in total over {pages_to_retrieve} pages"
    )

    # Format the combined results
    formatted_data = format_tools_to_desired_format(combined_results)

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

    # Verify that we're formatting all available hits from our pages
    assert formatted_hits == len(
        paginated_hits
    ), f"Expected {len(paginated_hits)} formatted hits, got {formatted_hits}"

    # Check the formatting of a few hits
    if formatted_hits > 0:
        print("\nSample of formatted hits from different pages:")
        for i in [
            0,
            min(formatted_hits - 1, per_page - 1),
            min(formatted_hits - 1, per_page * 2 - 1),
        ]:
            if i < formatted_hits:
                hit = formatted_data["hits"][i]
                print(f"\nHit {i+1}:")
                print(f"  objectID: {hit.get('objectID', 'MISSING')}")
                print(f"  name: {hit.get('name', 'MISSING')}")
                print(f"  description: {hit.get('description', 'MISSING')[:50]}...")

                # Verify required fields
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
                    assert (
                        field in hit
                    ), f"Required field '{field}' missing from hit {i+1}"
                    assert (
                        hit[field] is not None
                    ), f"Field '{field}' is None in hit {i+1}"

    print("\nPagination test completed successfully")
    return True


async def test_large_result_handling():
    """
    Test that we can handle the reported case of 204 hits correctly
    by combining multiple paginated requests if needed
    """
    print("\n=== Testing large result handling (204 hits case) ===")

    # Use a query that should return many results
    keywords = ["ai", "chatbot", "automation", "tool"]

    # First, do a search with a high per_page to get the total number of hits
    full_results = await algolia_search.perform_keyword_search(keywords, per_page=1000)
    total_hits = full_results.get("nbHits", 0)
    actual_hits = len(full_results.get("hits", []))

    print(f"Total hits: {total_hits}, Actual hits received: {actual_hits}")

    # Format the full results
    formatted_data = format_tools_to_desired_format(full_results)
    formatted_hits = len(formatted_data.get("hits", []))

    print(f"Formatted hits: {formatted_hits}")

    # Verify that we're preserving the correct hit count and receiving all available hits
    assert (
        formatted_hits == actual_hits
    ), f"Not all hits were formatted, got {formatted_hits}, expected {actual_hits}"

    # Check if we have at least as many hits as the reported issue (204)
    if total_hits >= 200:
        print(
            f"Found {total_hits} hits which is enough to simulate the reported issue of 204 hits"
        )
    else:
        print(
            f"Found {total_hits} hits which is less than the reported issue of 204 hits"
        )
        print(
            "This test is still valuable but doesn't fully replicate the reported issue"
        )

    # Verify the hits are properly formatted
    if formatted_hits > 0:
        # Check the formatting of the first, middle, and last hits
        for i in [0, formatted_hits // 2, formatted_hits - 1]:
            hit = formatted_data["hits"][i]

            # Verify required fields
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

    print(f"\nSuccessfully processed and formatted {formatted_hits} hits")
    return True


async def run_all_tests():
    """Run all pagination tests and report results"""
    tests = [
        ("Pagination retrieval", test_pagination_retrieval),
        ("Large result handling", test_large_result_handling),
    ]

    results = []

    for name, test_func in tests:
        print(f"\n{'=' * 50}")
        print(f"Running test: {name}")
        print(f"{'=' * 50}")

        try:
            success = await test_func()
            results.append((name, success, None))
            print(f"\n✓ Test '{name}' PASSED")
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"\n✗ Test '{name}' FAILED: {str(e)}")

    # Print summary
    print("\n\n" + "=" * 50)
    print("PAGINATION TEST SUMMARY")
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
