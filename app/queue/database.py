"""
Database integration for Site Queue
Provides connection to MongoDB collections used by the site queue manager
"""

from ..database import database


class SiteQueueDB:
    """
    Database interface for the Site Queue Manager
    Provides access to the MongoDB collections needed for site management
    """

    @classmethod
    def get_sites_collection(cls):
        """Get the sites collection"""
        return database.sites


# Create dependency functions for FastAPI
async def get_sites_collection():
    """Dependency for the sites collection"""
    return SiteQueueDB.get_sites_collection()
