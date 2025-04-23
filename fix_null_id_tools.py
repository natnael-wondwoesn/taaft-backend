#!/usr/bin/env python3
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.database.database import database, client
from app.logger import logger
from uuid import uuid4


async def fix_null_id_tools():
    # Connect to MongoDB
    try:
        await client.admin.command("ping")
        print("Connected to MongoDB")
    except Exception as e:
        print(f"Could not connect to MongoDB: {str(e)}")
        raise

    # Count tools with null id
    null_id_count = await database.tools.count_documents({"id": None})
    print(f"Found {null_id_count} tools with null id")

    if null_id_count > 0:
        # Find and fix tools with null id
        cursor = database.tools.find({"id": None})
        fixed_count = 0

        async for tool in cursor:
            # Generate a new UUID
            new_id = str(uuid4())

            # Update the tool with the new ID
            result = await database.tools.update_one(
                {"_id": tool["_id"]}, {"$set": {"id": new_id}}
            )

            if result.modified_count:
                fixed_count += 1
                print(f"Fixed tool: {tool.get('name', 'Unknown')} - New ID: {new_id}")
            else:
                print(f"Failed to fix tool: {tool.get('name', 'Unknown')}")

        print(f"\nFixed {fixed_count} out of {null_id_count} tools with null id")
    else:
        print("No tools with null id found")

    # Verify fix
    null_id_count_after = await database.tools.count_documents({"id": None})
    print(f"Tools with null id after fix: {null_id_count_after}")


async def main():
    try:
        await fix_null_id_tools()
    finally:
        # Close database connections
        client.close()
        print("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
