#!/usr/bin/env python3
"""
Script to check for tools that have duplicate categories in both 'category' field and 'categories' array.
This can cause duplicate counting in API endpoints.
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
        logging.FileHandler("check_duplicate_categories.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "taaft_db"
TOOLS_COLLECTION_NAME = "tools"


async def main():
    """Main function to check for duplicate categories."""
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
        # Find tools that have both category field and categories array
        query = {
            "category": {"$exists": True, "$type": "string", "$ne": ""},
            "categories": {"$exists": True, "$type": "array", "$ne": []}
        }
        
        duplicate_tools = []
        cursor = tools_collection.find(query, {"name": 1, "category": 1, "categories": 1})
        
        async for tool in cursor:
            category_string = tool.get("category", "")
            categories_array = tool.get("categories", [])
            
            # Check if the category string matches any category in the array
            for cat_obj in categories_array:
                if isinstance(cat_obj, dict):
                    cat_name = cat_obj.get("name", "")
                    cat_id = cat_obj.get("id", "")
                    
                    # Check for exact match or similar match
                    if (category_string == cat_name or 
                        category_string.lower() == cat_name.lower() or
                        category_string.replace(" ", "-").lower() == cat_id.lower()):
                        
                        duplicate_tools.append({
                            "_id": str(tool["_id"]),
                            "name": tool.get("name", "Unknown"),
                            "category_string": category_string,
                            "matching_category": {
                                "id": cat_id,
                                "name": cat_name
                            },
                            "all_categories": categories_array
                        })
                        break  # Found a match, no need to check other categories
        
        logger.info(f"Found {len(duplicate_tools)} tools with duplicate categories")
        
        if duplicate_tools:
            logger.info("Tools with duplicate categories:")
            for i, tool_info in enumerate(duplicate_tools[:10]):  # Show first 10
                logger.info(
                    f"{i+1}. '{tool_info['name']}': "
                    f"category='{tool_info['category_string']}' matches "
                    f"categories['{tool_info['matching_category']['name']}']"
                )
            
            if len(duplicate_tools) > 10:
                logger.info(f"... and {len(duplicate_tools) - 10} more tools")
            
            # Check specifically for SEO Tools
            seo_tools_duplicates = [t for t in duplicate_tools if "SEO" in t['category_string']]
            if seo_tools_duplicates:
                logger.info(f"\nFound {len(seo_tools_duplicates)} SEO Tools with duplicates:")
                for tool in seo_tools_duplicates:
                    logger.info(f"  - {tool['name']}: '{tool['category_string']}'")
                    
        # Check the specific count for SEO Tools using both methods
        logger.info("\n=== SEO Tools Analysis ===")
        
        # Count using category field only
        category_count = await tools_collection.count_documents({"category": "SEO Tools"})
        logger.info(f"Tools with category='SEO Tools': {category_count}")
        
        # Count using categories array only
        array_count = await tools_collection.count_documents({"categories.name": "SEO Tools"})
        logger.info(f"Tools with categories.name='SEO Tools': {array_count}")
        
        # Count using the OR query (like the API endpoint)
        or_count = await tools_collection.count_documents({
            "$or": [
                {"categories.name": "SEO Tools"},
                {"category": "SEO Tools"}
            ]
        })
        logger.info(f"Tools using $or query (API method): {or_count}")
        
        # Count using distinct aggregation (deduplicated)
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"categories.name": "SEO Tools"},
                        {"category": "SEO Tools"}
                    ]
                }
            },
            {
                "$group": {
                    "_id": "$_id"
                }
            },
            {
                "$count": "total"
            }
        ]
        
        agg_result = await tools_collection.aggregate(pipeline).to_list(length=1)
        deduplicated_count = agg_result[0]["total"] if agg_result else 0
        logger.info(f"Tools using aggregation deduplication: {deduplicated_count}")
        
        if or_count != deduplicated_count:
            logger.warning(f"ISSUE FOUND: OR query returns {or_count} but deduplicated count is {deduplicated_count}")
            logger.warning("This suggests there are tools matching both conditions!")
            
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
    finally:
        if 'client' in locals():
            await client.close()


if __name__ == "__main__":
    asyncio.run(main()) 