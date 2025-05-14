#!/usr/bin/env python3
"""
Tool Migration Script
Updates existing tools in the database with the new schema fields
"""

import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL")
if not MONGODB_URL:
    print("MONGODB_URL environment variable is not set")
    sys.exit(1)

client = AsyncIOMotorClient(MONGODB_URL)
db = client.get_database("taaft_db")
tools_collection = db.get_collection("tools")


async def migrate_tools():
    """Migrates existing tools to include the new schema fields."""

    # Get total count for progress tracking
    total_count = await tools_collection.count_documents({})
    print(f"Found {total_count} tools to migrate")

    # Fields to add if missing:
    # - category: Optional string
    # - features: Optional list of strings
    # - is_featured: Boolean (default False)
    # - unique_id: String
    # - keywords: Optional list of strings
    # - categories: Optional list of dictionaries
    # - logo_url: String (required, default placeholder URL)
    # - user_reviews: Optional dictionary
    # - feature_list: Optional list of strings
    # - referral_allow: Boolean (default False)
    # - generated_description: Optional string
    # - industry: Optional string

    # Default placeholder for logo URL
    DEFAULT_LOGO_URL = "None"

    # Set default values for new fields
    update_fields = {
        "$set": {"updated_at": datetime.utcnow()},
        "$setOnInsert": {
            "category": None,
            "features": [],
            "is_featured": False,
            "keywords": [],
            "categories": [],
            "logo_url": DEFAULT_LOGO_URL,
            "user_reviews": {},
            "feature_list": [],
            "referral_allow": False,
            "generated_description": None,
            "industry": None,
        },
    }

    # Update all tools that don't have the new fields
    updated_count = 0
    async for tool in tools_collection.find({}):
        needs_update = False
        update_ops = {}

        # Check which fields need to be added
        if "category" not in tool:
            update_ops["category"] = None
            needs_update = True

        if "features" not in tool:
            update_ops["features"] = []
            needs_update = True

        if "is_featured" not in tool:
            update_ops["is_featured"] = False
            needs_update = True

        if "unique_id" not in tool and "id" in tool:
            update_ops["unique_id"] = tool["id"]
            needs_update = True

        if "keywords" not in tool:
            update_ops["keywords"] = []
            needs_update = True

        if "categories" not in tool:
            update_ops["categories"] = []
            needs_update = True

        if "logo_url" not in tool or not tool["logo_url"]:
            update_ops["logo_url"] = DEFAULT_LOGO_URL
            needs_update = True

        if "user_reviews" not in tool:
            update_ops["user_reviews"] = {}
            needs_update = True

        if "feature_list" not in tool:
            update_ops["feature_list"] = []
            needs_update = True

        if "referral_allow" not in tool:
            update_ops["referral_allow"] = False
            needs_update = True

        if "generated_description" not in tool:
            update_ops["generated_description"] = None
            needs_update = True

        if "industry" not in tool:
            update_ops["industry"] = None
            needs_update = True

        # Update if needed
        if needs_update:
            update_ops["updated_at"] = datetime.utcnow()
            result = await tools_collection.update_one(
                {"_id": tool["_id"]}, {"$set": update_ops}
            )
            if result.modified_count:
                updated_count += 1
                print(f"Updated tool: {tool.get('name')}")

    print(f"Migration completed: {updated_count} tools updated out of {total_count}")


async def verify_migration():
    """Verifies that all tools have the new fields."""
    missing_fields_count = await tools_collection.count_documents(
        {
            "$or": [
                {"category": {"$exists": False}},
                {"features": {"$exists": False}},
                {"is_featured": {"$exists": False}},
                {"unique_id": {"$exists": False}},
                {"keywords": {"$exists": False}},
                {"categories": {"$exists": False}},
                {"logo_url": {"$exists": False}},
                {"user_reviews": {"$exists": False}},
                {"feature_list": {"$exists": False}},
                {"referral_allow": {"$exists": False}},
                {"generated_description": {"$exists": False}},
                {"industry": {"$exists": False}},
            ]
        }
    )

    if missing_fields_count == 0:
        print("Verification successful: All tools have the new schema fields")
    else:
        print(
            f"Verification failed: {missing_fields_count} tools are missing new fields"
        )


async def main():
    """Main function to run the migration."""
    print("Starting tool migration...")
    await migrate_tools()
    await verify_migration()
    print("Migration process completed")


if __name__ == "__main__":
    # Run the async migration
    asyncio.run(main())
