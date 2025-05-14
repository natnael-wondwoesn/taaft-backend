#!/usr/bin/env python3
"""
Script to remove duplicate tools from the database based on their names
"""

import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

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


async def remove_duplicate_tools():
    """Removes duplicate tools based on their names, keeping the newest one."""

    # Get all tool names
    all_tools = {}
    async for tool in tools_collection.find({}, {"name": 1, "created_at": 1}):
        name = tool.get("name")
        if not name:
            continue

        # If we haven't seen this name before, add it
        if name not in all_tools:
            all_tools[name] = []

        # Add this tool's ID to the list for this name
        all_tools[name].append(tool["_id"])

    # Find duplicate names
    duplicates = {name: ids for name, ids in all_tools.items() if len(ids) > 1}

    if not duplicates:
        print("No duplicate tools found. Exiting.")
        return

    total_duplicates = sum(len(ids) - 1 for ids in duplicates.values())
    print(f"Found {len(duplicates)} unique tool names with duplicates")
    print(f"Total of {total_duplicates} duplicate tools to remove")

    # Ask for confirmation before deletion
    if not sys.argv[-1] == "--force":
        confirmation = input(
            f"Are you sure you want to remove {total_duplicates} duplicate tools? (y/n): "
        )
        if confirmation.lower() != "y":
            print("Operation cancelled.")
            return

    # For each duplicate name, keep the newest one and remove the others
    removed_tools = []
    for name, ids in duplicates.items():
        # Get full tool details for all duplicates
        tools = []
        async for tool in tools_collection.find({"_id": {"$in": ids}}):
            tools.append(tool)

        # Sort by created_at (newest first) or _id if created_at not available
        tools.sort(key=lambda x: x.get("created_at", x["_id"]), reverse=True)

        # Keep the first one (newest), remove the rest
        keep_id = tools[0]["_id"]
        remove_ids = [t["_id"] for t in tools[1:]]

        # Store info about removed tools
        for tool in tools[1:]:
            removed_tools.append(
                {
                    "name": tool.get("name", "Unknown"),
                    "id": str(tool["_id"]),
                    "created_at": tool.get("created_at", "Unknown"),
                }
            )

        # Remove the duplicates
        result = await tools_collection.delete_many({"_id": {"$in": remove_ids}})
        print(f"Removed {result.deleted_count} duplicates of '{name}'")

    # Report results
    print(f"\nSuccessfully removed {len(removed_tools)} duplicate tools")

    # Print details of removed tools
    print("\nRemoved tools:")
    for i, tool in enumerate(removed_tools, 1):
        print(f"{i}. {tool['name']} (ID: {tool['id']}, Created: {tool['created_at']})")


async def main():
    """Main function to run the script."""
    print("Starting duplicate tool removal process...")
    await remove_duplicate_tools()
    print("Process completed")


if __name__ == "__main__":
    # Run the async script
    asyncio.run(main())
