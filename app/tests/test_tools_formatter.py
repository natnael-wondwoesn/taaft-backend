"""
Test script for tools formatter
"""

import json
import sys
import os
from typing import Dict, Any

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.algolia.tools_formatter import format_tools_to_desired_format


def test_tools_formatter():
    """Test the tools formatter with sample data"""

    # Sample search results
    sample_data = {
        "hits": [
            {
                "objectID": "1379404000",
                "name": "Jane Turing AI",
                "description": "Your tireless AI employee for small businesses.",
                "link": "https://theresanaiforthat.com/ai/jane-turing-ai/",
                "logo_url": "",
                "keywords": ["business automation", "AI", "small business"],
                "category_id": '"6806415d856a3a9ff0979444"',
                "unique_id": "jane-turing-ai",
                "price": "Free",
                "rating": "4.4",
            },
            {
                "objectID": "1379408000",
                "name": "Ridvay",
                "description": "Elevate your business with AI-powered insights and automation.",
                "link": "https://theresanaiforthat.com/ai/ridvay/",
                "logo_url": "",
                "keywords": ["business automation", "AI", "insights"],
                "category_id": '"6806415d856a3a9ff0979444"',
                "unique_id": "ridvay",
                "price": "Free + from $12.5/mo",
                "rating": "5.0",
            },
        ],
        "nbHits": 2,
    }

    # Format the data
    formatted_data = format_tools_to_desired_format(sample_data)

    print("\nOriginal data:")
    print(json.dumps(sample_data["hits"][0], indent=2))
    print(json.dumps(sample_data["hits"][1], indent=2))

    print("\nFormatted data:")
    if len(formatted_data["hits"]) >= 2:
        print(json.dumps(formatted_data["hits"][0], indent=2))
        print(json.dumps(formatted_data["hits"][1], indent=2))
    else:
        print("Not enough hits in formatted data")

    # Check format is correct
    assert "hits" in formatted_data
    assert "nbHits" in formatted_data
    assert formatted_data["nbHits"] == len(formatted_data["hits"])

    # Check field structure for each hit
    for idx, hit in enumerate(formatted_data["hits"]):
        print(f"\nChecking hit {idx} ({hit.get('name', 'unknown')}):")

        # Check for required fields in the correct format
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
            if field in hit:
                print(f"  ✓ {field}: {hit[field]}")
            else:
                print(f"  ✗ {field}: MISSING")
                assert False, f"Field {field} missing from hit {idx}"

        # Check that extraneous fields are not present
        unwanted_fields = [field for field in hit if field not in required_fields]
        if unwanted_fields:
            print(f"  ✗ Unwanted fields: {', '.join(unwanted_fields)}")
            assert False, f"Unwanted fields found: {unwanted_fields}"
        else:
            print("  ✓ No unwanted fields")

        # Check that category_id doesn't have quotes
        if '"' in hit.get("category_id", ""):
            print("  ✗ category_id contains quotes")
            assert False, "category_id should not contain quotes"
        else:
            print("  ✓ category_id format is correct")

    print("\nAll assertions passed. Format is correct.")


if __name__ == "__main__":
    test_tools_formatter()
