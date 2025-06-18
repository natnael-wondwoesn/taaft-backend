#!/usr/bin/env python3
"""
Script to fix tools with comma-separated categories.
Updates tools to use only the first category from comma-separated category strings.
"""

import asyncio
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("fix_comma_separated_categories.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "taaft_db"
TOOLS_COLLECTION_NAME = "tools"


async def main():
    """Main function to fix comma-separated categories in tools."""
    result = {
        "success": False,
        "tools_examined": 0,
        "tools_with_comma_categories": 0,
        "tools_updated": 0,
        "errors": 0
    }
    
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(MONGO_URI)
        await client.admin.command("ping")
        logger.info(f"Successfully connected to MongoDB at {MONGO_URI}")
    except ConnectionFailure:
        logger.error(f"Failed to connect to MongoDB. Please check your MONGO_URI: {MONGO_URI}")
        result["error"] = "Failed to connect to MongoDB"
        return result
    except Exception as e:
        logger.error(f"An error occurred during MongoDB connection: {e}")
        result["error"] = f"Connection error: {str(e)}"
        return result

    db = client[DB_NAME]
    tools_collection = db[TOOLS_COLLECTION_NAME]

    logger.info(f"Processing tools from '{TOOLS_COLLECTION_NAME}' collection in database '{DB_NAME}'")

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
        cursor = tools_collection.find(query)
        
        async for tool in cursor:
            result["tools_examined"] += 1
            category = tool.get("category")
            
            if category and "," in category:
                result["tools_with_comma_categories"] += 1
                
                # Get the first category from the comma-separated string
                first_category = category.split(",")[0].strip()
                
                tools_with_comma_categories.append({
                    "_id": tool["_id"],
                    "name": tool.get("name", "Unknown"),
                    "original_category": category,
                    "new_category": first_category
                })
        
        logger.info(f"Found {result['tools_with_comma_categories']} tools with comma-separated categories")
        
        # Update each tool
        for tool_info in tools_with_comma_categories:
            try:
                # Update the tool with only the first category
                update_result = await tools_collection.update_one(
                    {"_id": tool_info["_id"]},
                    {
                        "$set": {
                            "category": tool_info["new_category"],
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                if update_result.modified_count > 0:
                    result["tools_updated"] += 1
                    logger.info(
                        f"Updated tool '{tool_info['name']}': "
                        f"'{tool_info['original_category']}' → '{tool_info['new_category']}'"
                    )
                else:
                    logger.warning(f"Failed to update tool '{tool_info['name']}'")
                    
            except Exception as e:
                result["errors"] += 1
                logger.error(f"Error updating tool '{tool_info['name']}': {str(e)}")
        
        # Summary
        logger.info(f"""
        ===== SUMMARY =====
        Tools examined: {result['tools_examined']}
        Tools with comma-separated categories: {result['tools_with_comma_categories']}
        Tools successfully updated: {result['tools_updated']}
        Errors: {result['errors']}
        """)
        
        result["success"] = True
        
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
        result["error"] = str(e)
    finally:
        if 'client' in locals():
            await client.close()
    
    return result


if __name__ == "__main__":
    asyncio.run(main()) 