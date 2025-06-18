#!/usr/bin/env python3
"""
Test script to verify the new priority-based filtering for SEO Tools.
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Database configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "taaft_db"
TOOLS_COLLECTION_NAME = "tools"


async def test_seo_tools_filtering():
    """Test the new priority-based filtering logic for SEO Tools."""
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(MONGO_URI)
        await client.admin.command("ping")
        logger.info(f"Successfully connected to MongoDB at {MONGO_URI}")
    except ConnectionFailure:
        logger.error(f"Failed to connect to MongoDB. Please check your MONGO_URI: {MONGO_URI}")
        return
    except Exception as e:
        logger.error(f"An error occurred during MongoDB connection: {e}")
        return

    db = client[DB_NAME]
    tools_collection = db[TOOLS_COLLECTION_NAME]

    try:
        # Test the old OR logic (what we had before)
        old_filters = {
            "$or": [
                {"categories.name": "SEO Tools"},  # Array-based categories
                {"category": "SEO Tools"}          # String-based category
            ]
        }
        
        old_count = await tools_collection.count_documents(old_filters)
        logger.info(f"Old OR logic count: {old_count}")

        # Test the new priority-based logic (what we want now)
        new_filters = {
            "$or": [
                # Tools with the category in string field (regardless of categories array)
                {"category": "SEO Tools"},
                # Tools without string category but with the category in array
                {
                    "$and": [
                        {"$or": [{"category": {"$exists": False}}, {"category": ""}, {"category": None}]},
                        {"categories.name": "SEO Tools"}
                    ]
                }
            ]
        }
        
        new_count = await tools_collection.count_documents(new_filters)
        logger.info(f"New priority-based logic count: {new_count}")

        # Test just the string category count
        string_only_count = await tools_collection.count_documents({"category": "SEO Tools"})
        logger.info(f"String category only count: {string_only_count}")

        # Test just the array category count for tools without string category
        array_only_filters = {
            "$and": [
                {"$or": [{"category": {"$exists": False}}, {"category": ""}, {"category": None}]},
                {"categories.name": "SEO Tools"}
            ]
        }
        array_only_count = await tools_collection.count_documents(array_only_filters)
        logger.info(f"Array category only (no string) count: {array_only_count}")

        # Verify the math
        expected_new_count = string_only_count + array_only_count
        logger.info(f"Expected new count: {string_only_count} + {array_only_count} = {expected_new_count}")

        if new_count == expected_new_count:
            logger.info("✅ New filtering logic is working correctly!")
        else:
            logger.warning(f"⚠️  New filtering logic issue: {new_count} != {expected_new_count}")

        if new_count == 57:
            logger.info("✅ SEO Tools now returns exactly 57 tools as requested!")
        else:
            logger.info(f"ℹ️  SEO Tools returns {new_count} tools")

        # Show some example tools from each category
        logger.info("\n=== Examples ===")
        
        # String category tools
        string_tools = tools_collection.find({"category": "SEO Tools"}, {"name": 1}).limit(3)
        logger.info("Tools with string category 'SEO Tools':")
        async for tool in string_tools:
            logger.info(f"  - {tool.get('name')}")

        # Array category tools (without string category)
        array_tools = tools_collection.find(array_only_filters, {"name": 1}).limit(3)
        logger.info("Tools with array category 'SEO Tools' (no string category):")
        async for tool in array_tools:
            logger.info(f"  - {tool.get('name')}")

    except Exception as e:
        logger.error(f"Error during testing: {str(e)}")
    finally:
        if 'client' in locals():
            await client.close()


if __name__ == "__main__":
    asyncio.run(test_seo_tools_filtering()) 