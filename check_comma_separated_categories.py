#!/usr/bin/env python3
"""
Script to check and report tools with comma-separated categories.
This script only reads and reports, it doesn't make any changes.
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("check_comma_separated_categories.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "taaft_db"
TOOLS_COLLECTION_NAME = "tools"


async def main():
    """Main function to check comma-separated categories in tools."""
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

    logger.info(f"Checking tools from '{TOOLS_COLLECTION_NAME}' collection in database '{DB_NAME}'")

    try:
        # Find tools with comma-separated categories
        query = {
            "category": {
                "$exists": True,
                "$type": "string",
                "$regex": ".*,.*"  # Contains comma
            }
        }
        
        tools_with_comma_categories = []
        cursor = tools_collection.find(query, {"name": 1, "category": 1})
        
        async for tool in cursor:
            category = tool.get("category")
            
            if category and "," in category:
                # Get the first category from the comma-separated string
                first_category = category.split(",")[0].strip()
                
                tools_with_comma_categories.append({
                    "_id": str(tool["_id"]),
                    "name": tool.get("name", "Unknown"),
                    "original_category": category,
                    "would_become": first_category
                })
        
        logger.info(f"Found {len(tools_with_comma_categories)} tools with comma-separated categories")
        
        # Report findings
        if tools_with_comma_categories:
            logger.info("Tools that would be updated:")
            for i, tool_info in enumerate(tools_with_comma_categories[:20]):  # Show first 20
                logger.info(
                    f"{i+1}. '{tool_info['name']}': "
                    f"'{tool_info['original_category']}' → '{tool_info['would_become']}'"
                )
            
            if len(tools_with_comma_categories) > 20:
                logger.info(f"... and {len(tools_with_comma_categories) - 20} more tools")
        
        # Summary of categories that would be created
        first_categories = set()
        for tool_info in tools_with_comma_categories:
            first_categories.add(tool_info['would_become'])
        
        logger.info(f"\nUnique first categories found: {len(first_categories)}")
        for category in sorted(first_categories):
            logger.info(f"  - {category}")
            
        logger.info(f"\n===== SUMMARY =====")
        logger.info(f"Total tools with comma-separated categories: {len(tools_with_comma_categories)}")
        logger.info(f"Unique first categories: {len(first_categories)}")
        
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
    finally:
        if 'client' in locals():
            await client.close()


if __name__ == "__main__":
    asyncio.run(main()) 