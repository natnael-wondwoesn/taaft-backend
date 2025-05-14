#!/usr/bin/env python3
"""
Script to identify and remove duplicate categories from the database.
Duplicates are determined by having the same name (case-insensitive).
The script will keep the category with the highest count and remove others.
"""

import asyncio
import os
from typing import Dict, List, Set
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# MongoDB connection string
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "taaft")


async def connect_to_db():
    """Connect to MongoDB database."""
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    return db


async def remove_duplicate_categories():
    """
    Find and remove duplicate categories from the database.
    Duplicates are determined by having the same name (case-insensitive).
    """
    db = await connect_to_db()
    categories_collection = db.categories

    # Get all categories
    categories = await categories_collection.find().to_list(length=1000)
    logger.info(f"Found {len(categories)} total categories")

    # Group categories by lowercase name
    name_groups: Dict[str, List] = {}
    for category in categories:
        name_lower = category["name"].lower()
        if name_lower not in name_groups:
            name_groups[name_lower] = []
        name_groups[name_lower].append(category)

    # Find duplicate groups (more than one category with the same name)
    duplicate_groups = {
        name: cats for name, cats in name_groups.items() if len(cats) > 1
    }

    if not duplicate_groups:
        logger.info("No duplicate categories found")
        return

    logger.info(f"Found {len(duplicate_groups)} duplicate category names")

    # IDs of categories to delete
    to_delete_ids = []

    # Process each group of duplicates
    for name, group in duplicate_groups.items():
        logger.info(f"Processing duplicate group: {name}")

        # Sort by count (highest first) then by created_at (newest first) if available
        sorted_group = sorted(
            group,
            key=lambda x: (x.get("count", 0), x.get("created_at", None) or 0),
            reverse=True,
        )

        # Keep the one with highest count, mark others for deletion
        keep = sorted_group[0]
        to_delete = sorted_group[1:]

        logger.info(
            f"  Keeping: {keep['id']} - {keep['name']} (count: {keep.get('count', 0)})"
        )

        for cat in to_delete:
            logger.info(
                f"  Deleting: {cat['id']} - {cat['name']} (count: {cat.get('count', 0)})"
            )
            to_delete_ids.append(cat["_id"])

    # Delete duplicate categories
    if to_delete_ids:
        result = await categories_collection.delete_many(
            {"_id": {"$in": to_delete_ids}}
        )
        logger.info(f"Deleted {result.deleted_count} duplicate categories")

    # Get updated count
    count = await categories_collection.count_documents({})
    logger.info(f"Now have {count} categories in the database")


async def list_all_categories():
    """List all categories in the database for verification."""
    db = await connect_to_db()
    categories = await db.categories.find().sort("name", 1).to_list(length=1000)

    logger.info("\nCurrent categories in the database:")
    for cat in categories:
        logger.info(f"  {cat['name']} (id: {cat['id']}, count: {cat.get('count', 0)})")


async def main():
    """Main function to run the script."""
    logger.info("Starting duplicate category removal")

    # List categories before changes
    logger.info("Categories before removal:")
    await list_all_categories()

    # Remove duplicates
    await remove_duplicate_categories()

    # List categories after changes
    logger.info("\nCategories after removal:")
    await list_all_categories()

    logger.info("Finished duplicate category removal")


if __name__ == "__main__":
    asyncio.run(main())
