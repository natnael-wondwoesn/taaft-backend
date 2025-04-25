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
    """Test that formatted_data is included in the chat response"""

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

            # Check if formatted_data is in the response
            if "formatted_data" in result:
                print("SUCCESS: formatted_data is included in the response")
                print(f"Message: {result['message']}")
                print(
                    f"Formatted data: {json.dumps(result['formatted_data'], indent=2)}"
                )
            else:
                print("FAILED: formatted_data is not included in the response")
                print(f"Response: {json.dumps(result, indent=2)}")

    except Exception as e:
        print(f"Error during test: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_formatted_data_response())
