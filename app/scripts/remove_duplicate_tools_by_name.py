#!/usr/bin/env python3
"""
Script to remove duplicate tools from the database based only on the 'name' field.

This script identifies tools that have the same name and removes all but one instance (the oldest) of each duplicate set.

To run manually:
python app/scripts/remove_duplicate_tools_by_name.py
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
from typing import Dict, List
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
        logging.FileHandler("duplicate_tools_by_name_removal.log"),
    ],
)
script_logger = logging.getLogger("duplicate_tools_by_name_remover")

def get_created_at(tool):
    created_at = tool.get("created_at")
    if created_at is None:
        return None
    if isinstance(created_at, datetime):
        if created_at.tzinfo is not None:
            return created_at.replace(tzinfo=None)
        return created_at
    if isinstance(created_at, str):
        try:
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
    return None

def sort_key(tool):
    created_at = get_created_at(tool)
    if created_at is not None:
        return (0, created_at)
    try:
        if isinstance(tool.get("_id"), ObjectId):
            gen_time = tool["_id"].generation_time
            return (1, gen_time.replace(tzinfo=None))
        elif isinstance(tool.get("_id"), str) and ObjectId.is_valid(tool["_id"]):
            gen_time = ObjectId(tool["_id"]).generation_time
            return (1, gen_time.replace(tzinfo=None))
    except (AttributeError, TypeError):
        pass
    return (2, datetime.max)

async def find_duplicate_tools_by_name():
    tools_collection = database.tools
    all_tools = await tools_collection.find().to_list(length=None)
    script_logger.info(f"Found {len(all_tools)} total tools in database")
    duplicates = {}
    for tool in all_tools:
        name = tool.get("name")
        if not name:
            continue
        if name not in duplicates:
            duplicates[name] = []
        duplicates[name].append(tool)
    actual_duplicates = {k: v for k, v in duplicates.items() if len(v) > 1}
    return actual_duplicates

async def remove_duplicate_tools_by_name():
    start_time = datetime.now()
    script_logger.info(f"Starting duplicate tools (by name) removal at {start_time}")
    try:
        tools_collection = database.tools
        duplicates = await find_duplicate_tools_by_name()
        if not duplicates:
            script_logger.info("No duplicate tools found by name")
            return
        duplicate_count = sum(len(tools) - 1 for tools in duplicates.values())
        script_logger.info(
            f"Found {len(duplicates)} sets of duplicates with a total of {duplicate_count} duplicate tools to remove (by name)"
        )
        removed_count = 0
        for name, duplicate_tools in duplicates.items():
            duplicate_tools.sort(key=sort_key)
            tool_to_keep = duplicate_tools[0]
            tools_to_remove = duplicate_tools[1:]
            ids_to_remove = [tool.get("_id") for tool in tools_to_remove]
            if ids_to_remove:
                result = await tools_collection.delete_many({"_id": {"$in": ids_to_remove}})
                removed_count += result.deleted_count
                script_logger.info(
                    f"Kept tool '{name}' (ID: {tool_to_keep.get('_id')}) and removed {result.deleted_count} duplicates by name"
                )
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        script_logger.info(
            f"Duplicate tools (by name) removal completed in {duration:.2f} seconds"
        )
        script_logger.info(f"Removed {removed_count} duplicate tools by name")
    except Exception as e:
        script_logger.error(f"Error removing duplicate tools by name: {str(e)}")
        raise

async def main():
    try:
        script_logger.info("Starting duplicate tools (by name) removal script")
        await remove_duplicate_tools_by_name()
        script_logger.info("Duplicate tools (by name) removal completed successfully")
        return 0
    except Exception as e:
        script_logger.error(f"Error during duplicate tools (by name) removal: {str(e)}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 