#!/usr/bin/env python3
"""
Script to remove the 'category_id' field from all tools in the database.

To run manually:
python app/scripts/remove_category_id_from_tools.py
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

# Configure logging for this script
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("remove_category_id_from_tools.log"),
    ],
)
script_logger = logging.getLogger("remove_category_id_remover")


async def remove_category_id_from_tools():
    """
    Remove the 'category_id' field from all tools in the database.
    """
    start_time = datetime.now()
    script_logger.info(f"Starting removal of 'category_id' from tools at {start_time}")

    try:
        tools_collection = database.tools

        # Find all tools with a 'category_id' field
        query = {"category_id": {"$exists": True}}
        count = await tools_collection.count_documents(query)
        script_logger.info(f"Found {count} tools with 'category_id' field")

        if count == 0:
            script_logger.info("No tools found with 'category_id' field. Nothing to do.")
            return

        # Remove the 'category_id' field from all matching documents
        result = await tools_collection.update_many(query, {"$unset": {"category_id": ""}})
        script_logger.info(f"Removed 'category_id' field from {result.modified_count} tools")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        script_logger.info(f"Completed in {duration:.2f} seconds")

    except Exception as e:
        script_logger.error(f"Error removing 'category_id' from tools: {str(e)}")
        raise


async def main():
    await remove_category_id_from_tools()

if __name__ == "__main__":
    asyncio.run(main()) 