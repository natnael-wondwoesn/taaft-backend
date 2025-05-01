#!/usr/bin/env python3
"""
Script to generate tool categories using an LLM based on keywords from the database.
This script will:
1. Fetch all keywords from the database
2. Use an LLM to generate meaningful tool categories
3. Insert the generated categories into the categories collection
"""

import asyncio
import os
import json
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.server_api import ServerApi
import openai

# Fallback to the keywords.py file if direct DB access fails
try:
    from keywords import KEYWORDS
except ImportError:
    KEYWORDS = []

# Load environment variables
load_dotenv()

# OpenAI API setup
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# Database connection setup
MONGODB_URL = os.getenv("MONGODB_URL")
if not MONGODB_URL:
    raise ValueError("MONGODB_URL environment variable not set")

client = AsyncIOMotorClient(MONGODB_URL, server_api=ServerApi("1"))
database = client.get_database("taaft_db")
categories_collection = database.get_collection("categories")
keywords_collection = database.get_collection("keywords")


async def fetch_keywords_from_db() -> List[str]:
    """
    Fetch all keywords from the database.

    Returns:
        List of unique keywords from the database
    """
    print("Fetching keywords from database...")

    # Fetch all keywords from the database
    cursor = keywords_collection.find({})

    # Process results
    keywords_list = []
    async for keyword_doc in cursor:
        # Check the field name - could be either 'keyword' or 'word' depending on
        # which function created it
        keyword_value = keyword_doc.get("keyword") or keyword_doc.get("word")

        if keyword_value and keyword_value not in keywords_list:
            keywords_list.append(keyword_value)

    # Sort the keywords alphabetically for consistency
    keywords_list.sort()

    # Count the number of keywords found
    keywords_count = len(keywords_list)
    print(f"Found {keywords_count} unique keywords in the database.")

    return keywords_list


async def generate_categories_with_llm(
    keywords: List[str], num_categories: int = 15
) -> List[Dict[str, str]]:
    """
    Use LLM to generate tool categories based on the provided keywords.

    Args:
        keywords: List of keywords to use for category generation
        num_categories: Number of categories to generate (default: 15)

    Returns:
        List of category dictionaries with id, name, and slug
    """
    print(
        f"Generating {num_categories} categories using LLM based on {len(keywords)} keywords..."
    )

    # Prepare the prompt for the LLM
    prompt = f"""
    Based on the following list of keywords from a tools database, generate {num_categories} meaningful tool categories.
    Keywords: {', '.join(keywords)}
    
    For each category:
    1. Consider what types of tools might be represented by these keywords
    2. Create logical groupings that would be helpful for users browsing tools
    3. Use short, clear names that accurately describe the category
    
    Return the results as a JSON array of objects, where each object has:
    - id: a short lowercase identifier with no spaces (use hyphens if needed)
    - name: a human-readable name for the category
    - slug: the name in lowercase with spaces replaced by hyphens
    
    Example format:
    [
      {{
        "id": "marketing",
        "name": "Marketing",
        "slug": "marketing"
      }},
      {{
        "id": "content-creation",
        "name": "Content Creation",
        "slug": "content-creation"
      }}
    ]
    
    Return ONLY the JSON array, no additional text.
    """

    # Call the OpenAI API
    response = openai.ChatCompletion.create(
        model="gpt-4",  # You can use "gpt-3.5-turbo" for a cheaper but less capable option
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that generates structured data based on keywords.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=2000,
    )

    # Extract and parse the response
    result = response.choices[0].message.content.strip()

    # Sometimes the API might return markdown-formatted JSON
    if result.startswith("```json"):
        result = result.strip("```json").strip()
    elif result.startswith("```"):
        result = result.strip("```").strip()

    try:
        categories = json.loads(result)
        print(f"Successfully generated {len(categories)} categories")
        return categories
    except json.JSONDecodeError as e:
        print(f"Error parsing LLM response: {e}")
        print(f"Raw response: {result}")
        raise


async def save_categories_to_db(categories: List[Dict[str, str]]) -> None:
    """
    Save the generated categories to the database.

    Args:
        categories: List of category dictionaries to save
    """
    print(f"Saving {len(categories)} categories to database...")

    # Get existing categories to check for duplicates
    existing_categories = await categories_collection.find({}).to_list(length=1000)
    existing_ids = {cat["id"] for cat in existing_categories}
    existing_slugs = {cat["slug"] for cat in existing_categories}

    # Filter out categories that already exist (by id or slug)
    new_categories = []
    for category in categories:
        if category["id"] in existing_ids or category["slug"] in existing_slugs:
            print(
                f"Category already exists with id {category['id']} or slug {category['slug']}"
            )
            continue

        # Add a timestamp and initialize count to 0
        category["created_at"] = datetime.utcnow()
        category["count"] = 0
        new_categories.append(category)

    # Insert new categories if any
    if new_categories:
        await categories_collection.insert_many(new_categories)
        print(f"Successfully saved {len(new_categories)} new categories to database")
    else:
        print("No new categories to save")


async def main():
    """Main function to execute the category generation process"""
    try:
        # Fetch keywords from database
        db_keywords = await fetch_keywords_from_db()

        # Use DB keywords if available, otherwise fall back to imported KEYWORDS
        keywords = db_keywords if db_keywords else KEYWORDS

        if not keywords:
            print(
                "No keywords found. Please ensure either the database contains keywords or the keywords.py file is available."
            )
            return

        # Generate categories using LLM
        categories = await generate_categories_with_llm(keywords)

        # Save categories to database
        await save_categories_to_db(categories)

        print("Category generation completed successfully!")

    except Exception as e:
        print(f"Error during category generation: {str(e)}")
    finally:
        # Close the MongoDB connection
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
