#!/usr/bin/env python3
"""
Script to fetch all keywords from the database and store them as a string literal.
"""

import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.server_api import ServerApi

# Load environment variables
load_dotenv()

# Database connection setup
MONGODB_URL = os.getenv("MONGODB_URL")
client = AsyncIOMotorClient(MONGODB_URL, server_api=ServerApi("1"))
database = client.get_database("taaft_db")
keywords_collection = database.get_collection("keywords")


async def fetch_keywords():
    """
    Fetch all keywords from the database and store them as a string literal in a file.
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

    # Format the keywords as a string literal
    # Join the keywords with double quotes and comma separators
    keywords_literal = (
        "[\n    " + ",\n    ".join(f'"{keyword}"' for keyword in keywords_list) + "\n]"
    )

    # Write to file
    output_file = "keywords.py"
    with open(output_file, "w", encoding="utf-8") as file:
        file.write("# Auto-generated file containing all keywords from the database\n")
        file.write(f"# Generated on: {asyncio.get_event_loop().time()}\n")
        file.write(f"# Total keywords: {keywords_count}\n\n")
        file.write("KEYWORDS = ")
        file.write(keywords_literal)

    print(f"Keywords successfully written to {output_file}")


if __name__ == "__main__":
    asyncio.run(fetch_keywords())
