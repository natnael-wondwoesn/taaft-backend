"""
Test script for keyword extraction from LLM responses
"""

import asyncio
import sys
import os

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.chat.llm_service import LLMService


async def test_keyword_extraction():
    """Test the keyword extraction functionality"""
    llm_service = LLMService()

    # Test cases with different keyword formats
    test_cases = [
        {
            "name": "Standard format",
            "text": """Here are some keywords to help you find AI tools that match your needs: Keywords = ['AI Chatbots', 'Customer Service Automation', 'Retail AI Solutions', 'Natural Language Processing']. What would you like to do next?""",
        },
        {
            "name": "Alternative format",
            "text": """Based on your needs, here are some keywords: ['AI Chatbots', 'Customer Service', 'Retail Solutions'].""",
        },
        {
            "name": "No keywords",
            "text": """How can I help you with your business needs today?""",
        },
    ]

    print("Testing keyword extraction from LLM responses...")

    for test_case in test_cases:
        print(f"\nTest case: {test_case['name']}")
        print(f"Input text: {test_case['text'][:100]}...")

        result = await llm_service.detect_and_extract_keywords(test_case["text"])

        if result:
            print(
                f"Keywords detected! Search results: {len(result.get('hits', []))} hits"
            )
        else:
            print("No keywords detected or search returned no results")


if __name__ == "__main__":
    asyncio.run(test_keyword_extraction())
