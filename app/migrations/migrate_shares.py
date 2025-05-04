import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.database.database import database, client, shares, tools
from app.logger import logger


async def migrate_shares_to_tool_unique_id():
    """
    Migrate shares collection from using tool_id to tool_unique_id.
    """
    try:
        await client.admin.command("ping")
        logger.info("Connected to MongoDB for shares migration")
    except Exception as e:
        logger.error(f"Could not connect to MongoDB: {str(e)}")
        raise

    # Check if shares collection exists
    collections = await database.list_collection_names()
    if "shares" not in collections:
        logger.info("Shares collection doesn't exist, nothing to migrate")
        return

    # Get all shares that have tool_id but no tool_unique_id
    shares_to_migrate = []
    async for share in shares.find(
        {"tool_id": {"$exists": True}, "tool_unique_id": {"$exists": False}}
    ):
        shares_to_migrate.append(share)

    logger.info(f"Found {len(shares_to_migrate)} shares to migrate")

    # Migrate each share
    migrated_count = 0
    failed_count = 0

    for share in shares_to_migrate:
        try:
            # Find the tool by its id
            tool = await tools.find_one({"id": share["tool_id"]})
            if not tool:
                logger.warning(
                    f"Could not find tool with ID {share['tool_id']} for share {share['_id']}"
                )
                failed_count += 1
                continue

            # Update the share with tool_unique_id
            update_result = await shares.update_one(
                {"_id": share["_id"]},
                {
                    "$set": {"tool_unique_id": tool["unique_id"]},
                    "$unset": {"tool_id": ""},
                },
            )

            if update_result.modified_count > 0:
                migrated_count += 1
            else:
                logger.warning(f"Failed to update share {share['_id']}")
                failed_count += 1
        except Exception as e:
            logger.error(f"Error migrating share {share['_id']}: {str(e)}")
            failed_count += 1

    logger.info(
        f"Migration complete: {migrated_count} shares migrated, {failed_count} failed"
    )

    # Update database indexes
    try:
        # Remove old tool_id index if it exists
        indexes = await shares.index_information()
        if "tool_id_1" in indexes:
            await shares.drop_index("tool_id_1")
            logger.info("Dropped old tool_id index")

        # Create new tool_unique_id index if it doesn't exist
        if "tool_unique_id_1" not in indexes:
            await shares.create_index("tool_unique_id")
            logger.info("Created new tool_unique_id index")
    except Exception as e:
        logger.error(f"Error updating indexes: {str(e)}")


if __name__ == "__main__":
    asyncio.run(migrate_shares_to_tool_unique_id())
