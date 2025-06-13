#!/usr/bin/env python3
# scripts/remove_empty_categories.py

import asyncio
import logging
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

MONGO_URI = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "taaft_db")
TOOLS_COLLECTION_NAME = "tools"
CATEGORIES_COLLECTION_NAME = "categories"


async def get_tool_counts_by_category(tools_collection) -> Dict[str, int]:
    """
    Get counts of tools by category from the tools collection.
    Returns a dictionary of category names to counts.
    """
    pipeline = [
        {"$unwind": "$categories"},
        {"$group": {"_id": "$categories.id", "count": {"$sum": 1}}},
    ]
    category_counts = {}
    async for doc in tools_collection.aggregate(pipeline):
        category_counts[doc["_id"]] = doc["count"]
    return category_counts


async def main():
    """Main function to remove empty categories."""
    try:
        client = AsyncIOMotorClient(MONGO_URI)
        await client.admin.command("ping")
        logger.info(f"Successfully connected to MongoDB at {MONGO_URI}.")
    except ConnectionFailure:
        logger.error(
            f"Failed to connect to MongoDB. Please check your MONGO_URI: {MONGO_URI}"
        )
        return
    except Exception as e:
        logger.error(f"An error occurred during MongoDB connection: {e}")
        return

    db = client[DB_NAME]
    tools_collection = db[TOOLS_COLLECTION_NAME]
    categories_collection = db[CATEGORIES_COLLECTION_NAME]

    logger.info("Fetching tool counts by category...")
    tool_counts = await get_tool_counts_by_category(tools_collection)
    logger.info(f"Found {len(tool_counts)} categories with tools.")

    logger.info("Fetching all categories from the database...")
    all_categories = await categories_collection.find({}).to_list(length=None)
    logger.info(f"Found {len(all_categories)} total categories.")

    deleted_count = 0
    for category in all_categories:
        cat_id = category.get("id")
        if cat_id not in tool_counts or tool_counts[cat_id] == 0:
            logger.info(f"Deleting category '{category.get('name')}' (ID: {cat_id}) as it has no tools.")
            await categories_collection.delete_one({"_id": category["_id"]})
            deleted_count += 1

    logger.info(f"Finished. Deleted {deleted_count} empty categories.")


if __name__ == "__main__":
    # To allow running this script directly
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main()) 