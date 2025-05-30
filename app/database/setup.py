from motor.motor_asyncio import AsyncIOMotorClient
from .database import database, client
from ..logger import logger
from ..models.user import ServiceTier, UserInDB
from ..auth.utils import get_password_hash
import datetime
import os
from dotenv import load_dotenv
from pymongo import ASCENDING, TEXT

load_dotenv()


async def setup_database():
    """Initialize the database structure."""
    # Connect to MongoDB
    try:
        await client.admin.command("ping")
        logger.info("Connected to MongoDB for setup")
    except Exception as e:
        logger.error(f"Could not connect to MongoDB: {str(e)}")
        raise

    # Create collections if they don't exist
    collections = await database.list_collection_names()

    # Initialize user collection
    if "users" not in collections:
        await database.create_collection("users")
        logger.info("Created users collection")

        # Create indexes for users collection
        await database.users.create_index("email", unique=True)
        await database.users.create_index("service_tier")
        await database.users.create_index("created_at")
        await database.users.create_index("is_active")

        # Create admin user if configured
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")

        if admin_email and admin_password:
            logger.info(f"Creating admin user with email {admin_email}")

            # Hash the password
            hashed_password = get_password_hash(admin_password)

            # Create admin user
            admin_user = UserInDB(
                email=admin_email,
                hashed_password=hashed_password,
                full_name="Admin User",
                service_tier=ServiceTier.ENTERPRISE,
                is_active=True,
                is_verified=True,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow(),
                usage={
                    "requests_today": 0,
                    "requests_reset_date": datetime.datetime.utcnow(),
                    "total_requests": 0,
                    "storage_used_bytes": 0,
                },
            )

            # Insert admin user
            await database.users.insert_one(
                admin_user.dict(by_alias=True, exclude={"id"})
            )

            logger.info("Admin user created successfully")

    if "chat_sessions" not in collections:
        await database.create_collection("chat_sessions")
        logger.info("Created chat_sessions collection")

        # Create indexes for chat_sessions
        await database.chat_sessions.create_index("user_id")
        await database.chat_sessions.create_index("created_at")
        await database.chat_sessions.create_index("updated_at")
        await database.chat_sessions.create_index("is_active")

    if "chat_messages" not in collections:
        await database.create_collection("chat_messages")
        logger.info("Created chat_messages collection")

        # Create indexes for chat_messages
        await database.chat_messages.create_index("chat_id")
        await database.chat_messages.create_index("timestamp")
        await database.chat_messages.create_index(
            [("content", "text")]
        )  # Full-text search index

    # Initialize tools collection
    if "tools" not in collections:
        await database.create_collection("tools")
        logger.info("Created tools collection")

        # Create indexes for tools collection
        # await database.tools.create_index("id", unique=True)
        await database.tools.create_index("unique_id", unique=True)
        await database.tools.create_index("name")
        await database.tools.create_index("created_at")
        await database.tools.create_index("category")  # Index for category field
        await database.tools.create_index("is_featured")  # Index for is_featured field
        await database.tools.create_index([("name", "text"), ("description", "text")])
        logger.info("Created indexes for tools collection")

    # Initialize sites collection
    if "sites" not in collections:
        await database.create_collection("sites")
        logger.info("Created sites collection")

        # Create indexes for sites collection
        await database.sites.create_index("status")
        await database.sites.create_index("priority")
        await database.sites.create_index("category")
        await database.sites.create_index("created_at")
        await database.sites.create_index([("priority", 1), ("created_at", 1)])
        await database.sites.create_index([("name", "text"), ("description", "text")])
        logger.info("Created indexes for sites collection")

    # Initialize glossary collection
    if "glossary_terms" not in collections:
        await database.create_collection("glossary_terms")
        logger.info("Created glossary_terms collection")

        # Create indexes for glossary collection
        await database.glossary_terms.create_index("term", unique=True)
        await database.glossary_terms.create_index([("term", "text"), ("definition", "text")])
        logger.info("Created indexes for glossary_terms collection")

    # Initialize categories collection
    if "categories" not in collections:
        await database.create_collection("categories")
        logger.info("Created categories collection")

        # Create indexes for categories collection
        await database.categories.create_index("id", unique=True)
        await database.categories.create_index("slug", unique=True)
        await database.categories.create_index("count")
        await database.categories.create_index([("name", TEXT)])

        # Check if there are already categories in the collection
        categories_count = await database.categories.count_documents({})
        if categories_count == 0:
            # Only seed default categories if none exist
            logger.info("No categories found, seeding default categories")
            default_categories = [
                {
                    "id": "marketing",
                    "name": "Marketing",
                    "slug": "marketing",
                    "count": 0,
                },
                {
                    "id": "e-commerce",
                    "name": "E-Commerce",
                    "slug": "e-commerce",
                    "count": 0,
                },
                {
                    "id": "analytics",
                    "name": "Analytics",
                    "slug": "analytics",
                    "count": 0,
                },
            ]
            for category in default_categories:
                category["created_at"] = datetime.datetime.utcnow()
            await database.categories.insert_many(default_categories)
            logger.info(f"Inserted {len(default_categories)} default categories")
        else:
            logger.info(
                f"Found {categories_count} existing categories, skipping default seeding"
            )

        logger.info("Created indexes for categories collection")

    # Initialize keywords collection
    if "keywords" not in collections:
        await database.create_collection("keywords")
        logger.info("Created keywords collection")

        # Create indexes for keywords collection
        await database.keywords.create_index("keyword", unique=True)
        await database.keywords.create_index("count")
        logger.info("Created indexes for keywords collection")

    # Initialize blogs collection
    if "blogs" not in collections:
        await database.create_collection("blogs")
        logger.info("Created blogs collection")

        # Create indexes for blogs collection
        await database.blogs.create_index("slug", unique=True)
        await database.blogs.create_index("created_at")
        await database.blogs.create_index("updated_at")
        await database.blogs.create_index("published")
        await database.blogs.create_index([("title", "text"), ("content", "text")])
        logger.info("Created indexes for blogs collection")

    # Initialize favorites collection
    if "favorites" not in collections:
        await database.create_collection("favorites")
        logger.info("Created favorites collection")

        # Create indexes for favorites collection
        await database.favorites.create_index("user_id")
        await database.favorites.create_index("tool_id")
        await database.favorites.create_index([("user_id", 1), ("tool_id", 1)], unique=True)
        await database.favorites.create_index("created_at")
        logger.info("Created indexes for favorites collection")

    # Initialize shares collection
    if "shares" not in collections:
        await database.create_collection("shares")
        logger.info("Created shares collection")

        # Create indexes for shares collection
        await database.shares.create_index("user_id")
        await database.shares.create_index("tool_unique_id")
        await database.shares.create_index("share_id", unique=True)
        await database.shares.create_index("created_at")
        logger.info("Created indexes for shares collection")
        
    # Initialize tool_clicks collection
    if "tool_clicks" not in collections:
        await database.create_collection("tool_clicks")
        logger.info("Created tool_clicks collection")
        
        # Create indexes for tool_clicks collection
        await database.tool_clicks.create_index("tool_id")
        await database.tool_clicks.create_index("timestamp")
        await database.tool_clicks.create_index("user_id")
        # Compound index for efficient querying by date ranges
        await database.tool_clicks.create_index([("timestamp", 1), ("tool_id", 1)])
        logger.info("Created indexes for tool_clicks collection")

    logger.info("Database setup completed successfully")


async def cleanup_database():
    """Close database connections."""
    client.close()
    logger.info("Database connections closed")
