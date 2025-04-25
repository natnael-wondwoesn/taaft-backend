"""
Test script for keyword extraction from LLM responses
"""

import asyncio
import sys
import os
from typing import Dict, Any

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.chat.llm_service import LLMService
from app.algolia.search import format_search_results_summary


async def test_keyword_extraction():
    """Test the keyword extraction functionality"""
    llm_service = LLMService()

    # Test cases with different keyword formats
    test_cases = [
        {
            "name": "Standard format",
            "text": """Here are some keywords to help you find AI tools that match your needs: Keywords = ['Image Generation', 'Customer Service Automation', 'Retail AI Solutions', 'Natural Language Processing']. What would you like to do next?""",
        },
        {
            "name": "Alternative format",
            "text": """Based on your needs, here are some keywords: ['Image Generation', 'Customer Service', 'Retail Solutions'].""",
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
            print(f"result Bomboclat: {result}")
            print(
                f"Keywords detected! Search results: {len(result.get('hits', []))} hits"
            )

            # Test the new format_search_results_summary function
            summary = await format_search_results_summary(result)
            print("\nFormatted summary:")
            print(summary)
        else:
            print("No keywords detected or search returned no results")


async def test_result_formatter():
    """Test the search results summary formatter with mock data"""
    print("\n\nTesting search results formatter...")

    # Create a mock search result
    mock_result = type(
        "obj",
        (object,),
        {
            "nb_hits": 3,
            "hits": [
                {
                    "name": "AI Image Creator",
                    "description": "Generate stunning images from text descriptions using advanced AI models.",
                    "pricing_type": "freemium",
                    "categories": ["image generation", "art", "creative"],
                    "url": "https://example.com/ai-image-creator",
                },
                {
                    "name": "ChatGPT",
                    "description": "Conversational AI assistant powered by OpenAI.",
                    "pricing_type": "freemium",
                    "categories": ["chatbot", "assistant", "nlp"],
                    "url": "https://chat.openai.com",
                },
                {
                    "name": "Midjourney",
                    "description": "Create beautiful artwork with AI-powered image generation.",
                    "pricing_type": "paid",
                    "categories": ["image generation", "art", "creative"],
                    "url": "https://midjourney.com",
                },
            ],
        },
    )

    # Test the formatter
    summary = await format_search_results_summary(mock_result)
    print(summary)

    # Test with empty results
    empty_result = type("obj", (object,), {"nb_hits": 0, "hits": []})
    empty_summary = await format_search_results_summary(empty_result)
    print("\nEmpty results test:")
    print(empty_summary)


if __name__ == "__main__":
    asyncio.run(test_keyword_extraction())
    asyncio.run(test_result_formatter())
