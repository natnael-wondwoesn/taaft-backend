# app/algolia/indexer.py
"""
Indexing service for Algolia search
Handles synchronization between MongoDB and Algolia indexes
"""
from typing import Dict, List, Optional, Any, Union
import datetime
import asyncio
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.errors import PyMongoError

from .config import algolia_config
from .models import AlgoliaToolRecord
from ..logger import logger


class AlgoliaIndexer:
    """Service for indexing data in Algolia"""

    def __init__(self):
        """Initialize the indexer with Algolia config"""
        self.config = algolia_config

    async def index_tools(
        self, tools_collection: AsyncIOMotorCollection, batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Index all tools from MongoDB to Algolia

        Args:
            tools_collection: MongoDB collection containing tools
            batch_size: Number of tools to index in each batch

        Returns:
            Dictionary with indexing statistics
        """
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Skipping tool indexing.")
            return {
                "success": False,
                "message": "Algolia not configured",
                "indexed": 0,
                "errors": 0,
            }

        stats = {
            "success": True,
            "started_at": datetime.datetime.utcnow(),
            "indexed": 0,
            "errors": 0,
            "batches": 0,
        }

        try:
            # Get total count for progress tracking
            total_count = await tools_collection.count_documents({})
            logger.info(f"Starting indexing of {total_count} tools to Algolia")

            # Process tools in batches
            skip = 0
            while True:
                # Get batch of tools
                cursor = tools_collection.find({}).skip(skip).limit(batch_size)
                tools = await cursor.to_list(length=batch_size)

                if not tools:
                    break  # No more tools to process

                # Convert tools to Algolia records
                algolia_records = []
                for tool in tools:
                    try:
                        # Convert MongoDB _id to Algolia objectID
                        tool["objectID"] = str(tool.pop("_id"))

                        # Convert MongoDB categories to Algolia format if needed
                        if "categories" in tool and tool["categories"]:
                            # If categories are stored as ObjectIds, fetch category data
                            if isinstance(tool["categories"][0], ObjectId):
                                category_ids = tool["categories"]
                                # Placeholder for category data (in a real implementation, you'd fetch from DB)
                                tool["categories"] = [
                                    {
                                        "id": str(cat_id),
                                        "name": "Category placeholder",
                                        "slug": "category-placeholder",
                                    }
                                    for cat_id in category_ids
                                ]

                        # Simplify datetime objects for JSON serialization
                        if "created_at" in tool and isinstance(
                            tool["created_at"], datetime.datetime
                        ):
                            tool["created_at"] = tool["created_at"].isoformat()
                        if "updated_at" in tool and isinstance(
                            tool["updated_at"], datetime.datetime
                        ):
                            tool["updated_at"] = tool["updated_at"].isoformat()

                        algolia_records.append(tool)
                    except Exception as e:
                        logger.error(f"Error processing tool for Algolia: {str(e)}")
                        stats["errors"] += 1

                # Send batch to Algolia
                if algolia_records:
                    try:
                        # Use v4 client syntax to save objects
                        result = self.config.client.save_objects(
                            self.config.tools_index_name,
                            algolia_records,
                            {"wait_for_task": True},
                        )
                        stats["indexed"] += len(algolia_records)
                        stats["batches"] += 1
                        logger.info(
                            f"Indexed batch of {len(algolia_records)} tools to Algolia. "
                            + f"Progress: {stats['indexed']}/{total_count}"
                        )
                    except Exception as e:
                        logger.error(f"Error indexing batch to Algolia: {str(e)}")
                        stats["errors"] += len(algolia_records)

                # Move to next batch
                skip += batch_size

            # Complete the indexing stats
            stats["completed_at"] = datetime.datetime.utcnow()
            stats["duration_seconds"] = (
                stats["completed_at"] - stats["started_at"]
            ).total_seconds()
            logger.info(
                f"Completed indexing {stats['indexed']} tools to Algolia in {stats['duration_seconds']} seconds"
            )

            return stats

        except Exception as e:
            logger.error(f"Error during Algolia indexing: {str(e)}")
            stats["success"] = False
            stats["message"] = str(e)
            return stats

    async def index_tool(self, tool: Dict[str, Any]) -> bool:
        """
        Index a single tool in Algolia

        Args:
            tool: Tool document from MongoDB

        Returns:
            Boolean indicating success
        """
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Skipping tool indexing.")
            return False

        try:
            # Create a copy of the tool to avoid modifying the original
            tool_copy = tool.copy()

            # Convert MongoDB _id to Algolia objectID
            tool_copy["objectID"] = str(tool_copy.pop("_id"))

            # Convert MongoDB categories to Algolia format if needed
            if "categories" in tool_copy and tool_copy["categories"]:
                # If categories are stored as ObjectIds, fetch category data
                if isinstance(tool_copy["categories"][0], ObjectId):
                    category_ids = tool_copy["categories"]
                    # Placeholder for category data (in a real implementation, you'd fetch from DB)
                    tool_copy["categories"] = [
                        {
                            "id": str(cat_id),
                            "name": "Category placeholder",
                            "slug": "category-placeholder",
                        }
                        for cat_id in category_ids
                    ]

            # Simplify datetime objects for JSON serialization
            if "created_at" in tool_copy and isinstance(
                tool_copy["created_at"], datetime.datetime
            ):
                tool_copy["created_at"] = tool_copy["created_at"].isoformat()
            if "updated_at" in tool_copy and isinstance(
                tool_copy["updated_at"], datetime.datetime
            ):
                tool_copy["updated_at"] = tool_copy["updated_at"].isoformat()

            # Save to Algolia using v4 client syntax
            self.config.client.save_objects(
                self.config.tools_index_name, [tool_copy], {"wait_for_task": True}
            )
            logger.info(f"Indexed tool {tool_copy['objectID']} to Algolia")
            return True

        except Exception as e:
            logger.error(f"Error indexing tool to Algolia: {str(e)}")
            return False

    async def delete_tool(self, tool_id: Union[str, ObjectId]) -> bool:
        """
        Delete a tool from Algolia

        Args:
            tool_id: MongoDB _id of the tool to delete

        Returns:
            Boolean indicating success
        """
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Skipping tool deletion.")
            return False

        try:
            # Convert ObjectId to string if needed
            object_id = str(tool_id)

            # Delete from Algolia using v4 client syntax
            self.config.client.delete_object(
                self.config.tools_index_name, object_id, {"wait_for_task": True}
            )
            logger.info(f"Deleted tool {object_id} from Algolia")
            return True

        except Exception as e:
            logger.error(f"Error deleting tool from Algolia: {str(e)}")
            return False

    async def index_glossary_terms(
        self, glossary_collection: AsyncIOMotorCollection, batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Index all glossary terms from MongoDB to Algolia

        Args:
            glossary_collection: MongoDB collection containing glossary terms
            batch_size: Number of terms to index in each batch

        Returns:
            Dictionary with indexing statistics
        """
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Skipping glossary indexing.")
            return {
                "success": False,
                "message": "Algolia not configured",
                "indexed": 0,
                "errors": 0,
            }

        stats = {
            "success": True,
            "started_at": datetime.datetime.utcnow(),
            "indexed": 0,
            "errors": 0,
            "batches": 0,
        }

        try:
            # Get total count for progress tracking
            total_count = await glossary_collection.count_documents({})
            logger.info(f"Starting indexing of {total_count} glossary terms to Algolia")

            # Process terms in batches
            skip = 0
            while True:
                # Get batch of terms
                cursor = glossary_collection.find({}).skip(skip).limit(batch_size)
                terms = await cursor.to_list(length=batch_size)

                if not terms:
                    break  # No more terms to process

                # Convert terms to Algolia records
                algolia_records = []
                for term in terms:
                    try:
                        # Convert MongoDB _id to Algolia objectID
                        term["objectID"] = str(term.pop("_id"))

                        # Add letter group for alphabetical grouping if not present
                        if "term" in term and "letter_group" not in term:
                            first_letter = (
                                term["term"][0].upper() if term["term"] else "#"
                            )
                            term["letter_group"] = (
                                first_letter if first_letter.isalpha() else "#"
                            )

                        # Simplify datetime objects for JSON serialization
                        if "created_at" in term and isinstance(
                            term["created_at"], datetime.datetime
                        ):
                            term["created_at"] = term["created_at"].isoformat()
                        if "updated_at" in term and isinstance(
                            term["updated_at"], datetime.datetime
                        ):
                            term["updated_at"] = term["updated_at"].isoformat()

                        algolia_records.append(term)
                    except Exception as e:
                        logger.error(
                            f"Error processing glossary term for Algolia: {str(e)}"
                        )
                        stats["errors"] += 1

                # Send batch to Algolia
                if algolia_records:
                    try:
                        # Use v4 client syntax to save objects
                        result = self.config.client.save_objects(
                            self.config.glossary_index_name,
                            algolia_records,
                            {"wait_for_task": True},
                        )
                        stats["indexed"] += len(algolia_records)
                        stats["batches"] += 1
                        logger.info(
                            f"Indexed batch of {len(algolia_records)} glossary terms to Algolia. "
                            + f"Progress: {stats['indexed']}/{total_count}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error indexing glossary batch to Algolia: {str(e)}"
                        )
                        stats["errors"] += len(algolia_records)

                # Move to next batch
                skip += batch_size

            # Complete the indexing stats
            stats["completed_at"] = datetime.datetime.utcnow()
            stats["duration_seconds"] = (
                stats["completed_at"] - stats["started_at"]
            ).total_seconds()
            logger.info(
                f"Completed indexing {stats['indexed']} glossary terms to Algolia in {stats['duration_seconds']} seconds"
            )

            return stats

        except Exception as e:
            logger.error(f"Error during glossary indexing: {str(e)}")
            stats["success"] = False
            stats["message"] = str(e)
            return stats

    async def index_glossary_term(self, term: Dict[str, Any]) -> bool:
        """
        Index a single glossary term in Algolia

        Args:
            term: Glossary term document from MongoDB

        Returns:
            Boolean indicating success
        """
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Skipping glossary term indexing.")
            return False

        try:
            # Create a copy of the term to avoid modifying the original
            term_copy = term.copy()

            # Convert MongoDB _id to Algolia objectID
            term_copy["objectID"] = str(term_copy.pop("_id"))

            # Add letter group for alphabetical grouping if not present
            if "term" in term_copy and "letter_group" not in term_copy:
                first_letter = (
                    term_copy["term"][0].upper() if term_copy["term"] else "#"
                )
                term_copy["letter_group"] = (
                    first_letter if first_letter.isalpha() else "#"
                )

            # Simplify datetime objects for JSON serialization
            if "created_at" in term_copy and isinstance(
                term_copy["created_at"], datetime.datetime
            ):
                term_copy["created_at"] = term_copy["created_at"].isoformat()
            if "updated_at" in term_copy and isinstance(
                term_copy["updated_at"], datetime.datetime
            ):
                term_copy["updated_at"] = term_copy["updated_at"].isoformat()

            # Save to Algolia using v4 client syntax
            self.config.client.save_objects(
                self.config.glossary_index_name, [term_copy], {"wait_for_task": True}
            )
            logger.info(f"Indexed glossary term {term_copy['objectID']} to Algolia")
            return True

        except Exception as e:
            logger.error(f"Error indexing glossary term to Algolia: {str(e)}")
            return False

    async def delete_glossary_term(self, term_id: Union[str, ObjectId]) -> bool:
        """
        Delete a glossary term from Algolia

        Args:
            term_id: MongoDB _id of the term to delete

        Returns:
            Boolean indicating success
        """
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Skipping glossary term deletion.")
            return False

        try:
            # Convert ObjectId to string if needed
            object_id = str(term_id)

            # Delete from Algolia using v4 client syntax
            self.config.client.delete_object(
                self.config.glossary_index_name, object_id, {"wait_for_task": True}
            )
            logger.info(f"Deleted glossary term {object_id} from Algolia")
            return True

        except Exception as e:
            logger.error(f"Error deleting glossary term from Algolia: {str(e)}")
            return False


# Create a singleton instance of AlgoliaIndexer
algolia_indexer = AlgoliaIndexer()
