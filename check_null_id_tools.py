#!/usr/bin/env python3
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.database.database import database, client
from app.logger import logger


async def check_null_id_tools():
    # Connect to MongoDB
    try:
        await client.admin.command("ping")
        print("Connected to MongoDB")
    except Exception as e:
        print(f"Could not connect to MongoDB: {str(e)}")
        raise

    # Look for tools with null id
    null_id_count = await database.tools.count_documents({"id": None})
    print(f"Found {null_id_count} tools with null id")

    # Find and print tools with null id
    if null_id_count > 0:
        cursor = database.tools.find({"id": None})
        print("\nTools with null id:")
        async for tool in cursor:
            print(f"  - _id: {tool.get('_id')}")
            print(f"    name: {tool.get('name')}")
            print(f"    unique_id: {tool.get('unique_id')}")
            print()


async def main():
    try:
        await check_null_id_tools()
    finally:
        # Close database connections
        client.close()
        print("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
