# app/source_queue_db.py
"""
Database integration for Source Queue Manager
Provides connection to MongoDB collections used by the source queue manager
"""
from .database import database


class SourceQueueDB:
    """
    Database interface for the Source Queue Manager
    Provides access to the MongoDB collections needed for scraping management
    """

    @classmethod
    def get_sources_collection(cls):
        """Get the sources collection"""
        return database.sources

    @classmethod
    def get_scraping_tasks_collection(cls):
        """Get the scraping tasks collection"""
        return database.scraping_tasks

    @classmethod
    def get_scraping_logs_collection(cls):
        """Get the scraping logs collection"""
        return database.scraping_logs


# Create dependency functions for FastAPI
async def get_sources_collection():
    """Dependency for the sources collection"""
    return SourceQueueDB.get_sources_collection()


async def get_scraping_tasks_collection():
    """Dependency for the scraping tasks collection"""
    return SourceQueueDB.get_scraping_tasks_collection()


async def get_scraping_logs_collection():
    """Dependency for the scraping logs collection"""
    return SourceQueueDB.get_scraping_logs_collection()
