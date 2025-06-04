#!/usr/bin/env python3
# scripts/update_category_counts.py

import asyncio
import logging
import os
import re
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

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


def generate_slug(name: str) -> str:
    """Generates a URL-friendly slug from a string."""
    s = name.lower()
    s = re.sub(r"[^\w\s-]", "", s)  # Remove non-alphanumeric, non-space, non-hyphen
    s = re.sub(r"\s+", "-", s)  # Replace spaces with hyphens
    s = re.sub(r"-+", "-", s)  # Replace multiple hyphens with single hyphen
    s = s.strip("-")  # Trim leading/trailing hyphens
    if not s: # Handle empty string case after stripping
        # Fallback for empty or special character only names
        s = re.sub(r"[^a-z0-9]+", "", name.lower(), flags=re.IGNORECASE)
        if not s:
            # Extremely basic fallback if still empty, though unlikely for category names
            return "default-category" 
    return s


async def main():
    """Main function to update category counts."""
    try:
        client = AsyncIOMotorClient(MONGO_URI)
        # Test connection by pinging the admin database
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

    logger.info(
        f"Processing tools from '{TOOLS_COLLECTION_NAME}' collection in database '{DB_NAME}'."
    )

    # Aggregation pipeline to get distinct category names and their counts
    # from the 'tools' collection, based on the 'category' string field.
    pipeline = [
        {
            "$match": {
                "category": {
                    "$exists": True,
                    "$ne": None,
                    "$ne": "",
                }  # Ensure category field exists and is not empty/null
            }
        },
        {"$group": {"_id": "$category", "count": {"$sum": 1}}}, # Group by category string and count
        {"$project": {"name": "$_id", "count": 1, "_id": 0}}, # Project to 'name' and 'count'
    ]

    try:
        aggregated_tool_categories = await tools_collection.aggregate(pipeline).to_list(
            None
        )
        logger.info(
            f"Found {len(aggregated_tool_categories)} distinct categories with counts from tools collection."
        )
    except Exception as e:
        logger.error(f"Error during aggregation on '{TOOLS_COLLECTION_NAME}': {e}")
        await client.close()
        return

    if not aggregated_tool_categories:
        logger.info(
            f"No categories found in '{TOOLS_COLLECTION_NAME}' collection to process."
        )
        await client.close()
        return

    updated_count = 0
    created_count = 0

    for cat_data in aggregated_tool_categories:
        category_name = cat_data["name"]
        tool_count = cat_data["count"]

        # Generate ID and slug from the category name
        category_id = generate_slug(category_name)
        category_slug = category_id  # Typically, id and slug are the same

        logger.info(
            f"Processing: Name='{category_name}', ID='{category_id}', Calculated Count={tool_count}"
        )

        try:
            # Upsert into the categories collection
            # This will update existing categories or insert new ones.
            # Existing fields like 'svg' will be preserved on update.
            update_result = await categories_collection.update_one(
                {"id": category_id},  # Match documents by 'id'
                {
                    "$set": {
                        "name": category_name,
                        "slug": category_slug,
                        "count": tool_count,
                    },
                    "$setOnInsert": {
                        "id": category_id 
                        # 'svg' field is not set here, will be null/absent on new inserts
                        # or preserved if it exists from a previous manual/scripted update.
                    },
                },
                upsert=True,
            )

            if update_result.upserted_id:
                created_count += 1
                logger.info(
                    f"CREATED category: ID='{category_id}', Name='{category_name}', Count={tool_count}"
                )
            elif update_result.matched_count > 0:
                if update_result.modified_count > 0:
                    updated_count += 1
                    logger.info(
                        f"UPDATED category: ID='{category_id}', Name='{category_name}', Count={tool_count}"
                    )
                else:
                    logger.info(
                        f"NO CHANGE for category: ID='{category_id}', Name='{category_name}', Count={tool_count} (data already matched)"
                    )
            else:
                 # This case should ideally not be reached if upsert logic is correct
                logger.warning(f"UNEXPECTED: No action for category ID='{category_id}', Name='{category_name}'. Matched: {update_result.matched_count}, Upserted ID: {update_result.upserted_id}")


        except Exception as e:
            logger.error(
                f"Error updating/creating category ID='{category_id}', Name='{category_name}' in '{CATEGORIES_COLLECTION_NAME}': {e}"
            )

    logger.info(
        f"Script finished. Categories created: {created_count}, Categories updated: {updated_count}."
    )
    await client.close()
    logger.info("MongoDB connection closed.")


if __name__ == "__main__":
    # Ensure the script is run within an asyncio event loop
    asyncio.run(main()) 