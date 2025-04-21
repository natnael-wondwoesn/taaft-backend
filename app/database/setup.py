from .database import database, client
from ..logger import logger
from ..models.user import ServiceTier, UserInDB
from ..auth.utils import get_password_hash
import datetime
import os
from dotenv import load_dotenv

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

    # Initialize other collections as needed
    if "sources" not in collections:
        await database.create_collection("sources")
        logger.info("Created sources collection")

        # Create indexes for sources collection
        await database.sources.create_index("next_scrape_at")
        await database.sources.create_index("status")
        await database.sources.create_index([("priority", 1), ("next_scrape_at", 1)])

    if "scraping_logs" not in collections:
        await database.create_collection("scraping_logs")
        logger.info("Created scraping_logs collection")

        # Create index for scraping_logs
        await database.scraping_logs.create_index("completed_at")

    if "scraping_tasks" not in collections:
        await database.create_collection("scraping_tasks")
        logger.info("Created scraping_tasks collection")

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
        await database.tools.create_index("id", unique=True)
        await database.tools.create_index("unique_id", unique=True)
        await database.tools.create_index("name")
        await database.tools.create_index("created_at")
        await database.tools.create_index([("name", "text"), ("description", "text")])

    logger.info("Database setup completed successfully")


async def cleanup_database():
    """Close database connections."""
    client.close()
    logger.info("Database connections closed")
