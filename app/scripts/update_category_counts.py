#!/usr/bin/env python3
"""
Cron job script to update category counts in the database.

This script counts the number of tools in each category and updates the count field
in the categories collection. It should be run periodically to keep the counts accurate.

Example cron entry (run daily at 2 AM):
0 2 * * * /path/to/python /path/to/app/scripts/update_category_counts.py

To run manually:
python app/scripts/update_category_counts.py
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
from typing import Dict, Any

# Add the parent directory to sys.path so we can import app modules
# Only needed when running as a standalone script
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database.database import database
from app.logger import logger

# Configure logging specifically for this script
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("category_counts_update.log"),
    ],
)
script_logger = logging.getLogger("category_counts_updater")


async def update_category_counts() -> Dict[str, Any]:
    """
    Count the number of tools in each category and update the counts in the categories collection.

    Returns:
        Dictionary with summary information about the update operation
    """
    start_time = datetime.now()
    script_logger.info(f"Starting category count update at {start_time}")

    result = {
        "success": False,
        "start_time": start_time,
        "categories_updated": 0,
        "categories_total": 0,
        "duration_seconds": 0,
        "errors": [],
    }

    try:
        # Get collections
        tools_collection = database.tools
        categories_collection = database.get_collection("categories")

        # Get all categories
        categories = await categories_collection.find().to_list(length=100)

        if not categories:
            script_logger.warning("No categories found in database")
            result["success"] = True
            result["message"] = "No categories found in database"
            return result

        result["categories_total"] = len(categories)
        script_logger.info(f"Found {len(categories)} categories to update")

        # Update count for each category
        updated_count = 0
        for category in categories:
            category_id = category.get("id")
            if not category_id:
                script_logger.warning(f"Category missing ID: {category}")
                result["errors"].append(
                    f"Category missing ID: {category.get('name', 'Unknown')}"
                )
                continue

            # Count tools in this category
            # First try with the category field directly
            count = await tools_collection.count_documents({"category": category_id})

            # If no results, try with categories array (for multi-category support)
            if count == 0:
                count = await tools_collection.count_documents(
                    {"categories.id": category_id}
                )

            # Update the category with the new count
            update_result = await categories_collection.update_one(
                {"id": category_id}, {"$set": {"count": count}}
            )

            if update_result.modified_count > 0:
                updated_count += 1
                script_logger.info(
                    f"Updated category '{category.get('name', category_id)}' with count: {count}"
                )
            else:
                script_logger.info(
                    f"No change needed for category '{category.get('name', category_id)}' with count: {count}"
                )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Update result dictionary
        result["success"] = True
        result["categories_updated"] = updated_count
        result["end_time"] = end_time
        result["duration_seconds"] = duration

        script_logger.info(f"Category count update completed in {duration:.2f} seconds")
        script_logger.info(
            f"Updated {updated_count} categories out of {len(categories)}"
        )

    except Exception as e:
        error_message = f"Error updating category counts: {str(e)}"
        script_logger.error(error_message)
        result["success"] = False
        result["errors"].append(error_message)

    return result


async def main():
    """Main entry point for the script."""
    try:
        script_logger.info("Starting category counts update script")
        result = await update_category_counts()

        if result["success"]:
            script_logger.info("Category counts update completed successfully")
            print(
                f"Updated {result['categories_updated']} out of {result['categories_total']} categories"
            )
            return 0
        else:
            script_logger.error(f"Category counts update failed: {result['errors']}")
            print(f"Failed to update category counts: {result['errors']}")
            return 1

    except Exception as e:
        script_logger.error(f"Error during category counts update: {str(e)}")
        print(f"Error during category counts update: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
