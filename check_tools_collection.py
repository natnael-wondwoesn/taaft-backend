import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.database.database import database, client
from app.logger import logger


async def check_tools_collection():
    # Connect to MongoDB
    try:
        await client.admin.command("ping")
        print("Connected to MongoDB")
    except Exception as e:
        print(f"Could not connect to MongoDB: {str(e)}")
        raise

    # Check if tools collection exists
    collections = await database.list_collection_names()
    if "tools" in collections:
        print("✓ Tools collection exists")
    else:
        print("❌ Tools collection doesn't exist")
        return

    # Get collection info
    collection_info = await database.command(
        "listCollections", filter={"name": "tools"}
    )
    print(f"Collection info: {collection_info}")

    # Get indexes
    indexes = await database.tools.index_information()
    print("\nIndexes in tools collection:")
    for idx_name, idx_info in indexes.items():
        print(f"  - {idx_name}: {idx_info}")

    # Count documents
    doc_count = await database.tools.count_documents({})
    print(f"\nNumber of documents in tools collection: {doc_count}")


async def main():
    try:
        await check_tools_collection()
    finally:
        # Close database connections
        client.close()
        print("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
