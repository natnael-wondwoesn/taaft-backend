#!/usr/bin/env python3
"""
Optimized script to recalculate category counts.
First resets all category counts to 0, then iterates through tools to rebuild counts.
"""

import asyncio
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Database configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "taaft_db"
TOOLS_COLLECTION_NAME = "tools"
CATEGORIES_COLLECTION_NAME = "categories"


def generate_slug(name: str) -> str:
    """
    Generate a URL-friendly slug from a category name.
    """
    import re
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


async def recalculate_categories_optimized() -> Dict[str, Any]:
    """
    Optimized recalculation of category counts.
    
    Returns:
        Dictionary with operation results
    """
    result = {
        "success": False,
        "categories_reset": 0,
        "tools_processed": 0,
        "categories_updated": 0,
        "categories_created": 0,
        "errors": 0,
        "start_time": datetime.utcnow(),
        "end_time": None,
        "duration_seconds": 0
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
    categories_collection = db[CATEGORIES_COLLECTION_NAME]

    try:
        # Step 1: Reset all category counts to 0
        logger.info("Step 1: Resetting all category counts to 0...")
        reset_result = await categories_collection.update_many(
            {},  # Match all documents
            {"$set": {"count": 0}}
        )
        result["categories_reset"] = reset_result.modified_count
        logger.info(f"Reset counts for {result['categories_reset']} categories")

        # Step 2: Build a category lookup cache for optimization
        logger.info("Step 2: Building category lookup cache...")
        category_cache = {}
        async for category in categories_collection.find({}):
            cat_name = category.get("name")
            if cat_name:
                category_cache[cat_name] = {
                    "id": category.get("id"),
                    "slug": category.get("slug"),
                    "count": 0  # Start with 0, we'll increment as we go
                }
        logger.info(f"Loaded {len(category_cache)} existing categories into cache")

        # Step 3: Iterate through all tools and count categories
        logger.info("Step 3: Processing tools and counting categories...")
        cursor = tools_collection.find(
            {"category": {"$exists": True, "$type": "string", "$ne": ""}},
            {"category": 1}  # Only fetch the category field for performance
        )

        batch_updates = {}  # Track counts for batch update
        tools_processed = 0

        async for tool in cursor:
            tools_processed += 1
            category = tool.get("category")
            
            if not category:
                continue

            # Handle comma-separated categories (take only the first one)
            if "," in category:
                category = category.split(",")[0].strip()

            # Check if category exists in cache
            if category in category_cache:
                # Increment count in our batch updates
                if category not in batch_updates:
                    batch_updates[category] = 0
                batch_updates[category] += 1
            else:
                # Category doesn't exist, we'll need to create it
                cat_slug = generate_slug(category)
                cat_id = cat_slug
                
                # Add to cache
                category_cache[category] = {
                    "id": cat_id,
                    "slug": cat_slug,
                    "count": 0
                }
                
                # Initialize in batch updates
                if category not in batch_updates:
                    batch_updates[category] = 0
                batch_updates[category] += 1

            # Process in batches of 1000 for progress logging
            if tools_processed % 1000 == 0:
                logger.info(f"Processed {tools_processed} tools...")

        result["tools_processed"] = tools_processed
        logger.info(f"Finished processing {tools_processed} tools")

        # Step 4: Apply batch updates to database
        logger.info("Step 4: Applying batch updates to categories...")
        
        for category_name, count in batch_updates.items():
            category_info = category_cache[category_name]
            cat_id = category_info["id"]
            
            try:
                # Try to update existing category
                update_result = await categories_collection.update_one(
                    {"name": category_name},
                    {"$set": {"count": count}}
                )
                
                if update_result.matched_count > 0:
                    result["categories_updated"] += 1
                    logger.debug(f"Updated category '{category_name}' with count {count}")
                else:
                    # Category doesn't exist, create it
                    new_category = {
                        "id": cat_id,
                        "name": category_name,
                        "slug": category_info["slug"],
                        "count": count,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                    
                    await categories_collection.insert_one(new_category)
                    result["categories_created"] += 1
                    logger.info(f"Created new category '{category_name}' with count {count}")
                    
            except Exception as e:
                result["errors"] += 1
                logger.error(f"Error updating category '{category_name}': {str(e)}")

        result["success"] = True
        logger.info(f"""
        ===== RECALCULATION COMPLETE =====
        Categories reset: {result['categories_reset']}
        Tools processed: {result['tools_processed']}
        Categories updated: {result['categories_updated']}
        Categories created: {result['categories_created']}
        Errors: {result['errors']}
        """)

    except Exception as e:
        logger.error(f"Error during recalculation: {str(e)}")
        result["error"] = str(e)
    finally:
        if 'client' in locals():
            await client.close()
        
        result["end_time"] = datetime.utcnow()
        result["duration_seconds"] = (result["end_time"] - result["start_time"]).total_seconds()
    
    return result


async def main():
    """Main function for standalone execution."""
    result = await recalculate_categories_optimized()
    
    if result["success"]:
        print(f"✅ Recalculation completed successfully in {result['duration_seconds']:.2f} seconds")
        print(f"📊 Categories updated: {result['categories_updated']}")
        print(f"🆕 Categories created: {result['categories_created']}")
        print(f"🔧 Tools processed: {result['tools_processed']}")
    else:
        print(f"❌ Recalculation failed: {result.get('error', 'Unknown error')}")
    
    return result


if __name__ == "__main__":
    asyncio.run(main()) 