"""
Test script for formatted data in chat responses
"""

import asyncio
import sys
import os
import httpx
import json
import uuid
from typing import Dict, Any

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.chat.llm_service import LLMService
from app.algolia.search import format_search_results_summary


async def test_formatted_data_response():
    """Test that formatted_data is included in the chat response with the correct structure"""

    # Base URL for your API
    base_url = "http://localhost:8000"

    # Create a test chat session
    session_data = {
        "title": "Test Formatted Data",
        "system_prompt": "You are a helpful assistant.",
    }

    try:
        async with httpx.AsyncClient() as client:
            # Create a chat session
            response = await client.post(
                f"{base_url}/api/chat/sessions", json=session_data
            )
            response.raise_for_status()
            session = response.json()
            session_id = session["_id"]

            print(f"Created test session with ID: {session_id}")

            # Send a message that should trigger keyword extraction
            message = {
                "message": "Can you suggest keywords for finding AI tools for image generation? Keywords = ['image generation', 'AI art', 'picture creator']"
            }

            response = await client.post(
                f"{base_url}/api/chat/sessions/{session_id}/messages", json=message
            )
            response.raise_for_status()
            result = response.json()

            # Check if formatted_data is in the response with correct structure
            if "formatted_data" in result:
                print("SUCCESS: formatted_data is included in the response")

                # Check if the formatted_data has the correct fields
                formatted_data = result["formatted_data"]
                print(f"Number of hits: {formatted_data.get('nbHits', 0)}")

                if "hits" in formatted_data and formatted_data["hits"]:
                    sample_hit = formatted_data["hits"][0]
                    print("\nSample hit fields:")
                    for key in sample_hit:
                        print(f"  - {key}: {type(sample_hit[key]).__name__}")

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

                    missing_fields = [
                        field for field in required_fields if field not in sample_hit
                    ]
                    if missing_fields:
                        print(f"MISSING FIELDS: {', '.join(missing_fields)}")
                    else:
                        print("All required fields are present")

                    # Check that extraneous fields are not present
                    unwanted_fields = [
                        field for field in sample_hit if field not in required_fields
                    ]
                    if unwanted_fields:
                        print(f"UNWANTED FIELDS: {', '.join(unwanted_fields)}")
                    else:
                        print("No unwanted fields are present")
                else:
                    print("No hits found in formatted data")

                # Save the formatted response to a file for inspection
                with open("formatted_data_test_response.json", "w") as f:
                    json.dump(result, f, indent=2)
                print("Response saved to formatted_data_test_response.json")
            else:
                print("FAILED: formatted_data is not included in the response")
                print(f"Response: {json.dumps(result, indent=2)}")

    except Exception as e:
        print(f"Error during test: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_formatted_data_response())
