#!/usr/bin/env python3
"""
Script to fix tools that have duplicate categories in both 'category' field and 'categories' array.
This script will remove the category from the categories array if it already exists in the category field.
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
        logging.FileHandler("fix_duplicate_categories_in_tools.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "taaft_db"
TOOLS_COLLECTION_NAME = "tools"


async def main():
    """Main function to fix duplicate categories in tools."""
    result = {
        "success": False,
        "tools_examined": 0,
        "tools_with_duplicates": 0,
        "tools_fixed": 0,
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
        # Find tools that have both category field and categories array
        query = {
            "category": {"$exists": True, "$type": "string", "$ne": ""},
            "categories": {"$exists": True, "$type": "array", "$ne": []}
        }
        
        tools_to_fix = []
        cursor = tools_collection.find(query)
        
        async for tool in cursor:
            result["tools_examined"] += 1
            category_string = tool.get("category", "")
            categories_array = tool.get("categories", [])
            
            # Check if the category string matches any category in the array
            duplicate_found = False
            cleaned_categories = []
            
            for cat_obj in categories_array:
                if isinstance(cat_obj, dict):
                    cat_name = cat_obj.get("name", "")
                    cat_id = cat_obj.get("id", "")
                    
                    # Check for exact match or similar match
                    if (category_string == cat_name or 
                        category_string.lower() == cat_name.lower() or
                        category_string.replace(" ", "-").lower() == cat_id.lower()):
                        
                        # This is a duplicate, don't add it to cleaned_categories
                        duplicate_found = True
                        logger.debug(f"Found duplicate category '{cat_name}' in tool '{tool.get('name')}'")
                    else:
                        # Keep this category as it's not a duplicate
                        cleaned_categories.append(cat_obj)
                else:
                    # Keep non-dict items as-is (though this shouldn't happen)
                    cleaned_categories.append(cat_obj)
            
            if duplicate_found:
                result["tools_with_duplicates"] += 1
                tools_to_fix.append({
                    "_id": tool["_id"],
                    "name": tool.get("name", "Unknown"),
                    "category_string": category_string,
                    "original_categories": categories_array,
                    "cleaned_categories": cleaned_categories
                })
        
        logger.info(f"Found {result['tools_with_duplicates']} tools with duplicate categories out of {result['tools_examined']} examined")
        
        # Now fix the tools by updating their categories array
        for tool_info in tools_to_fix:
            try:
                update_result = await tools_collection.update_one(
                    {"_id": tool_info["_id"]},
                    {
                        "$set": {
                            "categories": tool_info["cleaned_categories"],
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                if update_result.modified_count > 0:
                    result["tools_fixed"] += 1
                    logger.info(
                        f"Fixed tool '{tool_info['name']}': "
                        f"Removed duplicate '{tool_info['category_string']}' from categories array"
                    )
                    logger.debug(
                        f"  Categories before: {len(tool_info['original_categories'])}, "
                        f"after: {len(tool_info['cleaned_categories'])}"
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
        Tools with duplicates: {result['tools_with_duplicates']}
        Tools successfully fixed: {result['tools_fixed']}
        Errors: {result['errors']}
        """)
        
        result["success"] = True
        
        # Verify the fix for SEO Tools specifically
        logger.info("\n=== SEO Tools Verification ===")
        
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
        
        if category_count + array_count == or_count:
            logger.info("✅ SEO Tools count is now correct!")
        else:
            logger.warning(f"⚠️  Still have an issue: {category_count} + {array_count} != {or_count}")
        
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
        result["error"] = str(e)
    finally:
        if 'client' in locals():
            await client.close()
    
    return result


if __name__ == "__main__":
    result = asyncio.run(main())
    
    if result.get("success"):
        print(f"✅ Fix completed successfully!")
        print(f"📊 Tools fixed: {result['tools_fixed']}")
        print(f"🔧 Tools examined: {result['tools_examined']}")
    else:
        print(f"❌ Fix failed: {result.get('error', 'Unknown error')}") 