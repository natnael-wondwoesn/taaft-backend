"""
Test script for tools formatter with None values
"""

import json
import sys
import os
from typing import Dict, Any

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.algolia.tools_formatter import format_tools_to_desired_format


def test_tools_formatter_with_none():
    """Test the tools formatter with sample data including None values"""

    # Sample search results with None values
    sample_data = {
        "hits": [
            {
                "objectID": "1379404000",
                "name": "Jane Turing AI",
                "description": None,  # None value
                "link": "https://theresanaiforthat.com/ai/jane-turing-ai/",
                "logo_url": None,  # None value
                "keywords": ["business automation", "AI", "small business"],
                "category_id": None,  # None value
                "unique_id": "jane-turing-ai",
                "price": "Free",
                "rating": None,  # None value
            },
            {
                # Missing some fields entirely
                "objectID": "1379408000",
                "name": "Ridvay",
                "link": "https://theresanaiforthat.com/ai/ridvay/",
                "keywords": ["business automation", "AI", "insights"],
            },
            # A completely different object structure (like a Hit object)
            type(
                "CustomHit",
                (),
                {
                    "objectID": "1379409000",
                    "name": "CustomHit Object",
                    "description": "This is a custom hit object, not a dictionary",
                    "link": None,
                    "category_id": "6806415d856a3a9ff0979444",
                },
            ),
        ],
        "nbHits": 3,
    }

    # Format the data
    formatted_data = format_tools_to_desired_format(sample_data)

    print("\nOriginal data with None values:")
    for hit in sample_data["hits"]:
        if isinstance(hit, dict):
            print(json.dumps(hit, indent=2, default=str))
        else:
            print(f"Custom object: {hit}")

    print("\nFormatted data:")
    for hit in formatted_data["hits"]:
        print(json.dumps(hit, indent=2))

    # Check that all hits have all required fields with non-None values
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
            # Check field exists
            assert field in hit, f"Field {field} missing from hit {idx}"

            # Check field is not None
            assert hit[field] is not None, f"Field {field} is None in hit {idx}"

            # Print field value
            print(f"  ✓ {field}: {hit[field]}")

        # Check no unwanted fields
        unwanted_fields = [field for field in hit if field not in required_fields]
        assert not unwanted_fields, f"Unwanted fields found: {unwanted_fields}"
        print("  ✓ No unwanted fields")

    print("\nAll assertions passed. Format is correct with None values handled.")


if __name__ == "__main__":
    test_tools_formatter_with_none()
