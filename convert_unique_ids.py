#!/usr/bin/env python3
"""
Script to convert unique IDs with slashes to hyphens in the database.
For example, "deepseek-ai/DeepSeek-V3" becomes "deepseek-ai-DeepSeek-V3".
"""

import asyncio
import sys
import os
from typing import List, Dict, Any

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database.database import database, tools, favorites, shares
from app.logger import logger


async def convert_unique_ids():
    """
    Find all tools with slashes in their unique_id and convert them to hyphens.
    Also update any references to these unique_ids in other collections.
    """
    logger.info("Starting unique_id conversion process...")

    # Find all tools with slashes in their unique_id
    cursor = tools.find({"unique_id": {"$regex": "/"}})

    # Dictionary to track old and new unique_ids for updating references
    id_mapping = {}

    # Process each tool
    count = 0
    async for tool in cursor:
        old_unique_id = tool.get("unique_id", "")
        if not old_unique_id or "/" not in old_unique_id:
            continue

        # Convert slashes to hyphens
        new_unique_id = old_unique_id.replace("/", "-")

        logger.info(f"Converting unique_id: '{old_unique_id}' -> '{new_unique_id}'")

        # Update the tool document
        result = await tools.update_one(
            {"_id": tool["_id"]}, {"$set": {"unique_id": new_unique_id}}
        )

        if result.modified_count > 0:
            count += 1
            id_mapping[old_unique_id] = new_unique_id
        else:
            logger.warning(f"Failed to update tool with unique_id: {old_unique_id}")

    logger.info(f"Updated {count} tools with new unique_ids")

    # Update references in favorites collection
    await update_favorites(id_mapping)

    # Update references in shares collection
    await update_shares(id_mapping)

    # Update references in users' saved_tools arrays
    await update_saved_tools_in_users(id_mapping)

    return count


async def update_favorites(id_mapping: Dict[str, str]):
    """
    Update references to unique_ids in the favorites collection.

    Args:
        id_mapping: Dictionary mapping old unique_ids to new unique_ids
    """
    if not id_mapping:
        return

    logger.info("Updating references in favorites collection...")

    total_updated = 0
    for old_id, new_id in id_mapping.items():
        result = await favorites.update_many(
            {"tool_unique_id": old_id}, {"$set": {"tool_unique_id": new_id}}
        )

        if result.modified_count > 0:
            total_updated += result.modified_count
            logger.info(
                f"Updated {result.modified_count} favorites with unique_id: {old_id} -> {new_id}"
            )

    logger.info(f"Updated a total of {total_updated} favorites")


async def update_shares(id_mapping: Dict[str, str]):
    """
    Update references to unique_ids in the shares collection.

    Args:
        id_mapping: Dictionary mapping old unique_ids to new unique_ids
    """
    if not id_mapping:
        return

    logger.info("Updating references in shares collection...")

    total_updated = 0
    for old_id, new_id in id_mapping.items():
        result = await shares.update_many(
            {"tool_unique_id": old_id}, {"$set": {"tool_unique_id": new_id}}
        )

        if result.modified_count > 0:
            total_updated += result.modified_count
            logger.info(
                f"Updated {result.modified_count} shares with unique_id: {old_id} -> {new_id}"
            )

    logger.info(f"Updated a total of {total_updated} shares")


async def update_saved_tools_in_users(id_mapping: Dict[str, str]):
    """
    Update references to unique_ids in users' saved_tools arrays.

    Args:
        id_mapping: Dictionary mapping old unique_ids to new unique_ids
    """
    if not id_mapping:
        return

    logger.info("Updating references in users' saved_tools arrays...")

    users_collection = database.users
    total_updated = 0

    for old_id, new_id in id_mapping.items():
        result = await users_collection.update_many(
            {"saved_tools": old_id}, {"$set": {"saved_tools.$": new_id}}
        )

        if result.modified_count > 0:
            total_updated += result.modified_count
            logger.info(
                f"Updated {result.modified_count} users with saved tool: {old_id} -> {new_id}"
            )

    logger.info(f"Updated saved_tools for {total_updated} users")


async def main():
    """Main entry point for the script."""
    try:
        logger.info("Starting unique ID conversion script")

        # Convert unique_ids
        count = await convert_unique_ids()

        logger.info(f"Conversion complete. Processed {count} tools.")

    except Exception as e:
        logger.error(f"Error during unique ID conversion: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
