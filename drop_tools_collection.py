import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.database.database import database, client
from app.logger import logger
from app.database.setup import setup_database


async def drop_tools_collection():
    # Connect to MongoDB
    try:
        await client.admin.command("ping")
        logger.info("Connected to MongoDB for collection reset")
    except Exception as e:
        logger.error(f"Could not connect to MongoDB: {str(e)}")
        raise

    # Check if tools collection exists
    collections = await database.list_collection_names()
    if "tools" in collections:
        # Drop the tools collection
        await database.tools.drop()
        logger.info("Dropped tools collection successfully")
    else:
        logger.info("Tools collection doesn't exist, nothing to drop")

    # Now let's recreate the tools collection with proper schema
    await database.create_collection("tools")
    logger.info("Created tools collection")

    # Create indexes for tools collection
    await database.tools.create_index("id", unique=True)
    await database.tools.create_index("unique_id", unique=True)
    await database.tools.create_index("name")
    await database.tools.create_index("created_at")
    await database.tools.create_index("category")
    await database.tools.create_index("is_featured")
    await database.tools.create_index([("name", "text"), ("description", "text")])

    logger.info("Created indexes for tools collection")
    logger.info("Tools collection reset completed successfully")


async def main():
    try:
        await drop_tools_collection()
    finally:
        # Close database connections
        client.close()
        logger.info("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
