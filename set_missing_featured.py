import asyncio
from app.database.database import tools


async def set_missing_featured_fields():
    """
    Set is_featured=False for all tools that don't have the field defined.
    This is a one-time maintenance task to ensure data consistency.
    """
    missing_count = await tools.count_documents({"is_featured": {"$exists": False}})
    print(f"Found {missing_count} tools without is_featured field")

    if missing_count > 0:
        result = await tools.update_many(
            {"is_featured": {"$exists": False}}, {"$set": {"is_featured": False}}
        )
        print(f"Updated {result.modified_count} tools to set is_featured=False")

    # Verify results
    featured = await tools.count_documents({"is_featured": True})
    unfeatured = await tools.count_documents({"is_featured": False})
    missing = await tools.count_documents({"is_featured": {"$exists": False}})

    print(f"\nAfter update:")
    print(f"Featured tools: {featured}")
    print(f"Unfeatured tools: {unfeatured}")
    print(f"Tools without is_featured field: {missing}")


if __name__ == "__main__":
    asyncio.run(set_missing_featured_fields())
