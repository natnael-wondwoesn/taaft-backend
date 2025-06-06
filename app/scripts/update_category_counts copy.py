#!/usr/bin/env python3
# scripts/update_category_counts.py

import asyncio
import logging
import os
import re
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional, Set

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

# For debugging purposes
VERBOSE = True  # Set to True for more detailed logs


def generate_slug(name: str) -> str:
    """Generates a URL-friendly slug from a string."""
    s = name.lower()
    s = re.sub(r"[^\w\s-]", "", s)  # Remove non-alphanumeric, non-space, non-hyphen
    s = re.sub(r"\s+", "-", s)  # Replace spaces with hyphens
    s = re.sub(r"-+", "-", s)  # Replace multiple hyphens with single hyphen
    s = s.strip("-")  # Trim leading/trailing hyphens
    if not s:  # Handle empty string case after stripping
        # Fallback for empty or special character only names
        s = re.sub(r"[^a-z0-9]+", "", name.lower(), flags=re.IGNORECASE)
        if not s:
            # Extremely basic fallback if still empty, though unlikely for category names
            return "default-category"
    return s


async def get_tool_counts_by_category(tools_collection) -> Dict[str, Dict[str, Any]]:
    """
    Get counts of tools by category from the tools collection.
    Returns both case-sensitive and case-insensitive dictionaries of counts.
    """
    # Get all tools with category field
    cursor = tools_collection.find(
        {"category": {"$exists": True, "$ne": None, "$ne": ""}},
        {"category": 1}  # Only return the category field
    )
    
    # Count by exact category name (case-sensitive)
    category_counts = {}
    # Count by lowercase category name (case-insensitive)
    category_counts_lower = {}
    # Map from lowercase to original case
    lowercase_to_original = {}
    
    async for tool in cursor:
        category = tool.get("category")
        if not category or not isinstance(category, str):
            continue
            
        # Case-sensitive counting
        if category not in category_counts:
            category_counts[category] = {"count": 0, "slug": generate_slug(category)}
        category_counts[category]["count"] += 1
        
        # Case-insensitive counting
        category_lower = category.lower()
        if category_lower not in category_counts_lower:
            category_counts_lower[category_lower] = {"count": 0, "slug": generate_slug(category)}
            lowercase_to_original[category_lower] = category
        category_counts_lower[category_lower]["count"] += 1
    
    # Combine the dictionaries into a single result
    return {
        "case_sensitive": category_counts,
        "case_insensitive": category_counts_lower,
        "lowercase_to_original": lowercase_to_original
    }


async def get_existing_categories(categories_collection) -> Dict[str, Dict[str, Any]]:
    """
    Get existing categories from the categories collection.
    Returns dictionaries indexed by ID and by name (lowercase).
    """
    categories_by_id = {}
    categories_by_name_lower = {}
    
    async for cat in categories_collection.find():
        cat_id = cat.get("id")
        cat_name = cat.get("name")
        
        if cat_id:
            categories_by_id[cat_id] = cat
        
        if cat_name:
            cat_name_lower = cat_name.lower()
            categories_by_name_lower[cat_name_lower] = cat
    
    return {
        "by_id": categories_by_id,
        "by_name_lower": categories_by_name_lower
    }


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

    # Get tool counts by category from tools collection
    tool_counts = await get_tool_counts_by_category(tools_collection)
    category_counts = tool_counts["case_sensitive"]
    category_counts_lower = tool_counts["case_insensitive"]
    lowercase_to_original = tool_counts["lowercase_to_original"]
    
    logger.info(f"Found {len(category_counts)} distinct categories in tools collection.")
    if VERBOSE:
        for cat_name, data in category_counts.items():
            logger.info(f"Category '{cat_name}' has {data['count']} tools (slug: {data['slug']})")
    
    # Get existing categories from categories collection
    existing_categories = await get_existing_categories(categories_collection)
    categories_by_id = existing_categories["by_id"]
    categories_by_name_lower = existing_categories["by_name_lower"]
    
    logger.info(f"Found {len(categories_by_id)} existing categories in categories collection.")
    
    # Track statistics
    updated_count = 0
    created_count = 0
    mismatched_count = 0
    reconciled_count = 0

    # Process each category from tools collection
    for cat_name, data in category_counts.items():
        tool_count = data["count"]
        cat_slug = data["slug"]
        cat_id = cat_slug  # Use slug as ID
        
        cat_name_lower = cat_name.lower()
        
        # Strategy 1: Try to find existing category by ID
        existing_cat_by_id = categories_by_id.get(cat_id)
        
        # Strategy 2: Try to find by case-insensitive name
        existing_cat_by_name = categories_by_name_lower.get(cat_name_lower)
        
        existing_cat = existing_cat_by_id or existing_cat_by_name
        
        if existing_cat:
            # Category exists, check for count mismatch
            existing_count = existing_cat.get("count", 0)
            existing_id = existing_cat.get("id")
            existing_name = existing_cat.get("name")
            
            if existing_count != tool_count:
                logger.warning(
                    f"Count mismatch for category '{cat_name}' (ID: {existing_id}): "
                    f"Database has {existing_count}, actual count is {tool_count}"
                )
                mismatched_count += 1
            
            # Update if:
            # 1. The count is different
            # 2. The name case is different but should be the same
            # 3. The ID doesn't match the expected slug
            update_needed = (
                existing_count != tool_count or
                (existing_name != cat_name and existing_name.lower() == cat_name_lower) or
                (existing_id != cat_id and existing_cat_by_name)
            )
            
            if update_needed:
                # If found by name but ID is different, this is a reconciliation case
                if existing_cat_by_name and not existing_cat_by_id and existing_id != cat_id:
                    logger.info(
                        f"Reconciling category '{cat_name}': ID '{existing_id}' → '{cat_id}'"
                    )
                    reconciled_count += 1
                
                # Update the category
                update_data = {
                    "count": tool_count,
                    "name": cat_name,  # Use original case from tools collection
                }
                
                # Only update the ID if this is a reconciliation case
                if existing_cat_by_name and not existing_cat_by_id:
                    update_data["id"] = cat_id
                    update_data["slug"] = cat_slug
                
                try:
                    # Use the existing ID for the query, not the generated one
                    query_id = existing_id
                    
                    update_result = await categories_collection.update_one(
                        {"id": query_id},
                        {"$set": update_data},
                    )
                    
                    if update_result.modified_count > 0:
                        updated_count += 1
                        logger.info(
                            f"UPDATED category: ID='{query_id}', Name='{cat_name}', "
                            f"Count={tool_count} (was {existing_count})"
                        )
                except Exception as e:
                    logger.error(
                        f"Error updating category ID='{existing_id}', Name='{cat_name}': {e}"
                    )
            else:
                logger.info(
                    f"No change needed for category: ID='{existing_id}', "
                    f"Name='{existing_name}', Count={existing_count}"
                )
        else:
            # Category doesn't exist, create it
            try:
                new_category = {
                    "id": cat_id,
                    "name": cat_name,
                    "slug": cat_slug,
                    "count": tool_count,
                }
                
                insert_result = await categories_collection.insert_one(new_category)
                
                if insert_result.inserted_id:
                    created_count += 1
                    logger.info(
                        f"CREATED category: ID='{cat_id}', Name='{cat_name}', Count={tool_count}"
                    )
            except Exception as e:
                logger.error(
                    f"Error creating category ID='{cat_id}', Name='{cat_name}': {e}"
                )
    
    # Look for categories in the categories collection that don't match any tools
    orphaned_categories = []
    for cat_id, cat_data in categories_by_id.items():
        cat_name = cat_data.get("name", "")
        cat_name_lower = cat_name.lower() if cat_name else ""
        
        # Check if this category exists in the tools collection
        if cat_name not in category_counts and cat_name_lower not in category_counts_lower:
            orphaned_categories.append(cat_data)
    
    if orphaned_categories:
        logger.warning(
            f"Found {len(orphaned_categories)} categories in categories collection "
            "that don't match any tools in the tools collection:"
        )
        for cat in orphaned_categories:
            logger.warning(
                f"Orphaned category: ID='{cat.get('id')}', Name='{cat.get('name')}', "
                f"Count={cat.get('count', 0)}"
            )
    
    logger.info(
        f"Script finished. Categories created: {created_count}, "
        f"Categories updated: {updated_count}, "
        f"Categories with count mismatches: {mismatched_count}, "
        f"Categories reconciled: {reconciled_count}, "
        f"Orphaned categories: {len(orphaned_categories)}"
    )
    client.close()
    logger.info("MongoDB connection closed.")


if __name__ == "__main__":
    # Ensure the script is run within an asyncio event loop
    asyncio.run(main()) 