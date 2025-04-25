#!/usr/bin/env python3
import asyncio
from uuid import UUID, uuid4, uuid5, NAMESPACE_OID
from app.database.database import database, client
from app.logger import logger


def objectid_to_uuid(objectid_str: str) -> UUID:
    """
    Converts an ObjectId string to a deterministic UUID.
    Uses UUID v5 with the ObjectId as the name and NAMESPACE_OID as namespace.
    """
    try:
        # Ensure we have a string representation of the ObjectId
        if hasattr(objectid_str, "_id"):
            objectid_str = str(objectid_str._id)
        elif hasattr(objectid_str, "__str__"):
            objectid_str = str(objectid_str)

        # Create a UUID5 (name-based) using the ObjectId string
        return uuid5(NAMESPACE_OID, objectid_str)
    except Exception as e:
        # Fall back to a random UUID if conversion fails
        logger.error(f"Failed to convert ObjectId to UUID: {e}")
        return uuid4()


async def fix_tool_ids():
    # Connect to MongoDB
    try:
        await client.admin.command("ping")
        print("Connected to MongoDB")
    except Exception as e:
        print(f"Could not connect to MongoDB: {str(e)}")
        raise

    # Get all tools
    tools_collection = database.get_collection("tools")
    total_tools = await tools_collection.count_documents({})
    print(f"Found {total_tools} tools in the database")

    # Count tools without id
    missing_id_count = await tools_collection.count_documents(
        {"id": {"$exists": False}}
    )
    print(f"Found {missing_id_count} tools without an 'id' field")

    # Find tools with missing 'id' field
    if missing_id_count > 0:
        tools_without_id = await tools_collection.find(
            {"id": {"$exists": False}}
        ).to_list(length=None)

        for tool in tools_without_id:
            if "_id" in tool:
                objectid = tool.get("_id")
                # Convert MongoDB ObjectId to UUID
                derived_uuid = objectid_to_uuid(objectid)
                tool_id = str(derived_uuid)

                # Update the tool with the derived UUID
                try:
                    await tools_collection.update_one(
                        {"_id": objectid}, {"$set": {"id": tool_id}}
                    )
                    print(
                        f"Updated tool '{tool.get('name', 'Unknown')}' with ID: {tool_id}"
                    )
                except Exception as e:
                    print(f"Error updating tool: {e}")

    # Fix null or invalid IDs
    null_id_count = await tools_collection.count_documents({"id": None})
    print(f"Found {null_id_count} tools with null id")

    if null_id_count > 0:
        tools_with_null_id = await tools_collection.find({"id": None}).to_list(
            length=None
        )

        for tool in tools_with_null_id:
            if "_id" in tool:
                objectid = tool.get("_id")
                derived_uuid = objectid_to_uuid(objectid)
                tool_id = str(derived_uuid)

                # Update the tool with the derived UUID
                try:
                    await tools_collection.update_one(
                        {"_id": objectid}, {"$set": {"id": tool_id}}
                    )
                    print(
                        f"Fixed null ID for tool '{tool.get('name', 'Unknown')}' with ID: {tool_id}"
                    )
                except Exception as e:
                    print(f"Error fixing null ID: {e}")

    print("Tool ID fix completed")


if __name__ == "__main__":
    asyncio.run(fix_tool_ids())
