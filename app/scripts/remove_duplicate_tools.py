#!/usr/bin/env python3
"""
Script to remove duplicate tools from the database.

This script identifies tools that have the same name and link, and removes all but one
instance of each duplicate set. This helps maintain data integrity by eliminating redundant entries.

To run manually:
python app/scripts/remove_duplicate_tools.py
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
from typing import Dict, List, Set, Tuple
from bson import ObjectId

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
        logging.FileHandler("duplicate_tools_removal.log"),
    ],
)
script_logger = logging.getLogger("duplicate_tools_remover")


def get_created_at(tool):
    """
    Safely get the created_at value from a tool, handling various formats.
    Returns a datetime object or None if not available.
    All returned datetimes are offset-naive (timezone info removed).
    """
    created_at = tool.get("created_at")

    if created_at is None:
        return None

    # If it's already a datetime object, ensure it's offset-naive
    if isinstance(created_at, datetime):
        if created_at.tzinfo is not None:
            # Convert to offset-naive by replacing tzinfo with None
            return created_at.replace(tzinfo=None)
        return created_at

    # If it's a string, try to parse it
    if isinstance(created_at, str):
        try:
            # Parse with timezone info then remove it
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return dt.replace(tzinfo=None)
        except (ValueError, AttributeError):
            try:
                return datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                try:
                    return datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    script_logger.warning(f"Could not parse created_at: {created_at}")
                    return None

    # If we couldn't parse it, return None
    return None


def sort_key(tool):
    """
    Custom sort key function for tools.
    First tries to sort by created_at, then by _id.
    Ensures all datetime objects are offset-naive for consistent comparison.
    """
    created_at = get_created_at(tool)

    # If we have a valid created_at, use it
    if created_at is not None:
        return (0, created_at)

    # Otherwise, try to use _id
    try:
        # If _id is an ObjectId, use its generation time (ensure it's offset-naive)
        if isinstance(tool.get("_id"), ObjectId):
            gen_time = tool["_id"].generation_time
            return (1, gen_time.replace(tzinfo=None))
        # If _id is a string that can be converted to ObjectId
        elif isinstance(tool.get("_id"), str) and ObjectId.is_valid(tool["_id"]):
            gen_time = ObjectId(tool["_id"]).generation_time
            return (1, gen_time.replace(tzinfo=None))
    except (AttributeError, TypeError):
        pass

    # Default to maximum datetime (will be sorted last)
    return (2, datetime.max)


async def find_duplicate_tools():
    """
    Find duplicate tools based on having the same name and link.

    Returns:
        A dictionary where keys are (name, link) tuples and values are lists of document IDs
    """
    tools_collection = database.tools

    # Get all tools
    all_tools = await tools_collection.find().to_list(length=None)
    script_logger.info(f"Found {len(all_tools)} total tools in database")

    # Group tools by name and link
    duplicates = {}
    for tool in all_tools:
        name = tool.get("name")
        link = tool.get("link")

        if not name or not link:
            continue

        key = (name, link)
        if key not in duplicates:
            duplicates[key] = []

        duplicates[key].append(tool)

    # Filter to only include keys with more than one tool (actual duplicates)
    actual_duplicates = {k: v for k, v in duplicates.items() if len(v) > 1}

    return actual_duplicates


async def remove_duplicate_tools():
    """
    Find and remove duplicate tools, keeping only one instance of each duplicate set.
    """
    start_time = datetime.now()
    script_logger.info(f"Starting duplicate tools removal at {start_time}")

    try:
        tools_collection = database.tools

        # Find duplicate tools
        duplicates = await find_duplicate_tools()

        if not duplicates:
            script_logger.info("No duplicate tools found")
            return

        duplicate_count = sum(len(tools) - 1 for tools in duplicates.values())
        script_logger.info(
            f"Found {len(duplicates)} sets of duplicates with a total of {duplicate_count} duplicate tools to remove"
        )

        # Process each set of duplicates
        removed_count = 0
        for (name, link), duplicate_tools in duplicates.items():
            # Sort using our custom sort key function
            duplicate_tools.sort(key=sort_key)

            # Keep the oldest tool (first after sorting)
            tool_to_keep = duplicate_tools[0]
            tools_to_remove = duplicate_tools[1:]

            # Extract IDs of tools to remove
            ids_to_remove = [tool.get("_id") for tool in tools_to_remove]

            # Remove the duplicate tools
            if ids_to_remove:
                result = await tools_collection.delete_many(
                    {"_id": {"$in": ids_to_remove}}
                )
                removed_count += result.deleted_count

                script_logger.info(
                    f"Kept tool '{name}' (ID: {tool_to_keep.get('_id')}) and removed {result.deleted_count} duplicates"
                )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        script_logger.info(
            f"Duplicate tools removal completed in {duration:.2f} seconds"
        )
        script_logger.info(f"Removed {removed_count} duplicate tools")

    except Exception as e:
        script_logger.error(f"Error removing duplicate tools: {str(e)}")
        raise


async def main():
    """Main entry point for the script."""
    try:
        script_logger.info("Starting duplicate tools removal script")
        await remove_duplicate_tools()
        script_logger.info("Duplicate tools removal completed successfully")
        return 0
    except Exception as e:
        script_logger.error(f"Error during duplicate tools removal: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
