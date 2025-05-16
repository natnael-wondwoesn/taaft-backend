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

# Add the parent directory to sys.path so we can import app modules
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


async def update_category_counts():
    """
    Count the number of tools in each category and update the counts in the categories collection.
    """
    start_time = datetime.now()
    script_logger.info(f"Starting category count update at {start_time}")

    try:
        # Get collections
        tools_collection = database.tools
        categories_collection = database.get_collection("categories")

        # Get all categories
        categories = await categories_collection.find().to_list(length=100)

        if not categories:
            script_logger.warning("No categories found in database")
            return

        script_logger.info(f"Found {len(categories)} categories to update")

        # Update count for each category
        updated_count = 0
        for category in categories:
            category_id = category.get("id")
            if not category_id:
                script_logger.warning(f"Category missing ID: {category}")
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
            result = await categories_collection.update_one(
                {"id": category_id}, {"$set": {"count": count}}
            )

            if result.modified_count > 0:
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
        script_logger.info(f"Category count update completed in {duration:.2f} seconds")
        script_logger.info(
            f"Updated {updated_count} categories out of {len(categories)}"
        )

    except Exception as e:
        script_logger.error(f"Error updating category counts: {str(e)}")
        raise


async def main():
    """Main entry point for the script."""
    try:
        script_logger.info("Starting category counts update script")
        await update_category_counts()
        script_logger.info("Category counts update completed successfully")
        return 0
    except Exception as e:
        script_logger.error(f"Error during category counts update: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
