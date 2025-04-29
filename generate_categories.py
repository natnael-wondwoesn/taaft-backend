#!/usr/bin/env python3
"""
Script to generate tool categories using an LLM based on keywords from the database.
This script will:
1. Fetch all keywords from the database
2. Use an LLM to generate meaningful tool categories
3. Insert the generated categories into the categories collection
4. Map existing tools to the generated categories

Usage:
    1. Make sure you have set the following environment variables:
       - MONGODB_URL: Your MongoDB connection string
       - OPENAI_API_KEY: Your OpenAI API key

    2. Run the script:
       $ python generate_categories.py

    The script will:
    - Connect to the MongoDB database
    - Fetch all keywords from the keywords collection
    - Use OpenAI GPT to generate logical categories based on the keywords
    - Clear the existing categories collection
    - Insert the newly generated categories
    - Map each tool in the database to appropriate categories

    If no keywords are found in the database, the script will fall back to using
    the KEYWORDS list from keywords.py if available.
"""

import asyncio
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.server_api import ServerApi
from bson import ObjectId
from openai import OpenAI

# Fallback to the keywords.py file if direct DB access fails
try:
    from keywords import KEYWORDS
except ImportError:
    KEYWORDS = []

# Load environment variables
load_dotenv()

# OpenAI API setup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Database connection setup
MONGODB_URL = os.getenv("MONGODB_URL")
if not MONGODB_URL:
    raise ValueError("MONGODB_URL environment variable not set")

client = AsyncIOMotorClient(MONGODB_URL, server_api=ServerApi("1"))
database = client.get_database("taaft_db")
categories_collection = database.get_collection("categories")
keywords_collection = database.get_collection("keywords")
tools_collection = database.get_collection("tools")


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

    # Call the OpenAI API using the new client approach
    response = openai_client.chat.completions.create(
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

    # Clear existing categories
    await categories_collection.delete_many({})

    # Add a timestamp and initialize count to 0
    timestamp = datetime.utcnow()
    for category in categories:
        category["created_at"] = timestamp
        category["count"] = 0

    # Insert new categories
    if categories:
        await categories_collection.insert_many(categories)
        print(f"Successfully saved {len(categories)} categories to database")


async def map_tools_to_categories(
    categories: List[Dict[str, str]], batch_size: int = 10
) -> None:
    """
    Map each tool in the database to appropriate categories using the LLM.
    Process tools in batches to optimize API usage.

    Args:
        categories: List of category dictionaries to map tools to
        batch_size: Number of tools to process in each batch (default: 10 to avoid context window limits)
    """
    print("Mapping tools to categories...")

    # Prepare categories information for prompt
    categories_info = json.dumps(
        [{"id": cat["id"], "name": cat["name"]} for cat in categories], indent=2
    )

    # Count total tools
    total_tools = await tools_collection.count_documents({})
    print(f"Found {total_tools} tools to categorize")

    if total_tools == 0:
        print("No tools found in the database. Skipping categorization.")
        return

    # Process tools in batches
    processed_count = 0
    updated_count = 0
    error_count = 0

    try:
        # Use smaller batch size for more reliable processing
        batch_cursor = tools_collection.find({}).batch_size(batch_size)

        current_batch = []
        async for tool in batch_cursor:
            # Skip tools that already have categories if needed
            # Uncomment the following lines to skip tools with existing categories
            # if tool.get("categories") and len(tool.get("categories")) > 0:
            #     processed_count += 1
            #     continue

            current_batch.append(tool)

            # Process batch when it reaches the desired size or at the end
            if (
                len(current_batch) >= batch_size
                or processed_count + len(current_batch) >= total_tools
            ):
                try:
                    # Prepare tool information for the batch
                    tools_info = []
                    for t in current_batch:
                        # Convert ObjectId to string for serialization
                        tool_id_str = str(t.get("_id"))

                        # Get keywords as a list of strings if available
                        keywords = []
                        if isinstance(t.get("keywords"), list):
                            keywords = t.get("keywords")

                        tool_info = {
                            "id": tool_id_str,
                            "name": t.get("name", ""),
                            "description": t.get("description", ""),
                            "keywords": keywords,
                        }
                        tools_info.append(tool_info)

                    # Categorize the batch
                    batch_categories = await categorize_tools_batch(
                        tools_info, categories_info
                    )

                    # Update each tool with its categories
                    for i, tool in enumerate(current_batch):
                        if i >= len(tools_info):
                            # Skip if index out of range (shouldn't happen but just in case)
                            continue

                        tool_id_str = tools_info[i]["id"]
                        tool_categories = batch_categories.get(tool_id_str, [])

                        if tool_categories:
                            try:
                                # Update the tool in the database
                                result = await tools_collection.update_one(
                                    {"_id": tool["_id"]},
                                    {"$set": {"categories": tool_categories}},
                                )
                                if result.modified_count > 0:
                                    updated_count += 1
                            except Exception as e:
                                print(f"Error updating tool {tool_id_str}: {str(e)}")
                                error_count += 1

                except Exception as batch_error:
                    print(f"Error processing batch: {str(batch_error)}")
                    error_count += len(current_batch)

                processed_count += len(current_batch)
                print(
                    f"Processed {processed_count}/{total_tools} tools, updated {updated_count}, errors {error_count}"
                )

                # Clear the batch
                current_batch = []

        print(
            f"Finished mapping {processed_count} tools to categories. Updated {updated_count} tools. Errors: {error_count}"
        )

    except Exception as e:
        print(f"Error in tool mapping process: {str(e)}")

    # Update category counts even if there were errors
    await update_category_counts()


async def categorize_tools_batch(
    tools_info: List[Dict[str, Any]], categories_info: str, max_retries: int = 2
) -> Dict[str, List[Dict[str, str]]]:
    """
    Categorize a batch of tools using the LLM.

    Args:
        tools_info: List of tool information dictionaries
        categories_info: JSON string of available categories
        max_retries: Maximum number of retries on failure

    Returns:
        Dictionary mapping tool IDs to their categories
    """
    # Prepare the prompt for the LLM
    prompt = f"""
    You are tasked with categorizing tools into the most relevant categories.
    
    Available categories:
    {categories_info}
    
    For each tool, assign 1-3 most relevant categories from the list above.
    
    Tools to categorize:
    {json.dumps(tools_info, indent=2)}
    
    Return a JSON object where each key is the tool ID and the value is an array of category objects.
    Each category object should include the category id and name.
    
    Example format:
    {{
      "tool_id_1": [
        {{ "id": "marketing", "name": "Marketing" }},
        {{ "id": "content-creation", "name": "Content Creation" }}
      ],
      "tool_id_2": [
        {{ "id": "analytics", "name": "Analytics" }}
      ]
    }}
    
    Return ONLY the JSON object, no additional text.
    """

    retries = 0
    while retries <= max_retries:
        try:
            # Call the OpenAI API
            response = openai_client.chat.completions.create(
                model="gpt-4",  # You can use "gpt-3.5-turbo" for a cheaper but less capable option
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that categorizes tools based on their descriptions and keywords.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # Lower temperature for more consistent results
                max_tokens=4000,
            )

            # Extract and parse the response
            result = response.choices[0].message.content.strip()

            # Clean up the response if needed
            if result.startswith("```json"):
                result = result.strip("```json").strip()
            elif result.startswith("```"):
                result = result.strip("```").strip()

            # Parse the JSON response
            categorization_result = json.loads(result)

            # Validate the result structure
            for tool_id, categories in categorization_result.items():
                if not isinstance(categories, list):
                    print(
                        f"Warning: Invalid categories format for tool {tool_id}, expected list but got {type(categories)}"
                    )
                    categorization_result[tool_id] = []
                    continue

                for i, category in enumerate(categories):
                    if (
                        not isinstance(category, dict)
                        or "id" not in category
                        or "name" not in category
                    ):
                        print(
                            f"Warning: Invalid category format for tool {tool_id}, category at index {i}"
                        )
                        categories[i] = {"id": "other", "name": "Other"}

            return categorization_result

        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response on attempt {retries + 1}: {str(e)}")
            print(
                f"Raw response: {result[:200]}..."
            )  # Print first 200 chars to diagnose
            retries += 1
            if retries <= max_retries:
                print(f"Retrying... ({retries}/{max_retries})")
                await asyncio.sleep(2)  # Wait a bit before retrying

        except Exception as e:
            print(f"Error during categorization on attempt {retries + 1}: {str(e)}")
            retries += 1
            if retries <= max_retries:
                print(f"Retrying... ({retries}/{max_retries})")
                await asyncio.sleep(2)  # Wait a bit before retrying

    # If we've exhausted all retries, return empty categorization
    print(f"Failed to categorize tools after {max_retries + 1} attempts")
    return {tool["id"]: [] for tool in tools_info}


async def update_category_counts() -> None:
    """
    Update the count field for each category in the categories collection
    based on how many tools are assigned to each category.
    """
    print("Updating category counts...")

    # Get all categories
    categories = await categories_collection.find().to_list(length=100)

    updated_counts = 0
    for category in categories:
        # Count tools in this category
        count = await tools_collection.count_documents(
            {"categories.id": category["id"]}
        )

        # Update category count
        result = await categories_collection.update_one(
            {"id": category["id"]}, {"$set": {"count": count}}
        )

        if result.modified_count > 0:
            updated_counts += 1

        print(f"Category '{category['name']}' has {count} tools")

    print(f"Updated counts for {updated_counts} categories")


async def validate_category_counts() -> None:
    """
    Validate that category counts match the actual number of tools assigned to each category.
    This is a verification step to ensure counts are accurate.
    """
    print("Validating category counts...")

    # Get all categories
    categories = await categories_collection.find().to_list(length=100)

    all_counts_valid = True
    for category in categories:
        # Get stored count
        stored_count = category.get("count", 0)

        # Count tools in this category
        actual_count = await tools_collection.count_documents(
            {"categories.id": category["id"]}
        )

        # Compare counts
        if stored_count != actual_count:
            print(
                f"WARNING: Category '{category['name']}' has incorrect count. Stored: {stored_count}, Actual: {actual_count}"
            )
            all_counts_valid = False

            # Fix the count
            await categories_collection.update_one(
                {"id": category["id"]}, {"$set": {"count": actual_count}}
            )
            print(f"  - Fixed count for '{category['name']}' to {actual_count}")

    if all_counts_valid:
        print("All category counts are valid!")
    else:
        print("Some category counts were incorrect and have been fixed.")


async def main():
    """Main function to execute the category generation and tool mapping process"""
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

        # Map tools to categories
        await map_tools_to_categories(categories)

        # Validate category counts as a final check
        await validate_category_counts()

        print("Category generation and tool mapping completed successfully!")

    except Exception as e:
        print(f"Error during category generation: {str(e)}")
    finally:
        # Close the MongoDB connection
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
