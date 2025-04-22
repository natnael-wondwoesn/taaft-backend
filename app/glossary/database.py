from ..database.database import glossary_terms
from ..models.glossary import GlossaryTerm, GlossaryTermUpdate, GlossaryTermFilter
from ..logger import logger
from bson import ObjectId
from typing import List, Dict, Any, Optional
import asyncio
from pymongo import ASCENDING, DESCENDING, TEXT


class GlossaryDB:
    """Database operations for glossary terms."""

    async def list_terms(
        self,
        filter_params: Optional[GlossaryTermFilter] = None,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "name",
        sort_order: int = ASCENDING,
    ) -> List[Dict[str, Any]]:
        """List glossary terms with filtering, pagination and sorting."""
        # Build filter query
        query = {}

        if filter_params:
            if filter_params.category:
                query["categories"] = filter_params.category

            # Text search if search term provided
            if filter_params.search:
                # Use text index for search
                query["$text"] = {"$search": filter_params.search}

        # Execute query with pagination
        cursor = glossary_terms.find(query).skip(skip).limit(limit)

        # Apply sorting
        cursor = cursor.sort(sort_by, sort_order)

        # Convert cursor to list
        results = await cursor.to_list(length=limit)
        return results

    async def get_term_by_id(self, term_id: str) -> Optional[Dict[str, Any]]:
        """Get a glossary term by ID."""
        if not ObjectId.is_valid(term_id):
            return None

        term = await glossary_terms.find_one({"_id": ObjectId(term_id)})
        return term

    async def get_term_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a glossary term by name."""
        term = await glossary_terms.find_one({"name": name})
        return term

    async def create_term(self, term_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new glossary term."""
        result = await glossary_terms.insert_one(term_data)

        # Fetch the created document
        created_term = await self.get_term_by_id(str(result.inserted_id))
        return created_term

    async def update_term(
        self, term_id: str, update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update an existing glossary term."""
        if not ObjectId.is_valid(term_id):
            return None

        # Remove None values from update data
        clean_update = {k: v for k, v in update_data.items() if v is not None}

        if not clean_update:
            # No valid update fields, just return the current document
            return await self.get_term_by_id(term_id)

        # Update the document
        result = await glossary_terms.update_one(
            {"_id": ObjectId(term_id)}, {"$set": clean_update}
        )

        if result.modified_count == 0:
            # Document wasn't found or no changes were made
            return None

        # Return the updated document
        return await self.get_term_by_id(term_id)

    async def delete_term(self, term_id: str) -> bool:
        """Delete a glossary term."""
        if not ObjectId.is_valid(term_id):
            return False

        result = await glossary_terms.delete_one({"_id": ObjectId(term_id)})
        return result.deleted_count > 0

    async def count_terms(
        self, filter_params: Optional[GlossaryTermFilter] = None
    ) -> int:
        """Count glossary terms with optional filtering."""
        query = {}

        if filter_params:
            if filter_params.category:
                query["categories"] = filter_params.category

            if filter_params.search:
                query["$text"] = {"$search": filter_params.search}

        count = await glossary_terms.count_documents(query)
        return count

    async def get_categories(self) -> List[str]:
        """Get all unique categories across all terms."""
        pipeline = [
            {"$unwind": "$categories"},
            {"$group": {"_id": "$categories"}},
            {"$sort": {"_id": 1}},
        ]

        cursor = glossary_terms.aggregate(pipeline)
        results = await cursor.to_list(length=None)

        # Extract category names from results
        categories = [doc["_id"] for doc in results]
        return categories


async def get_glossary_db() -> GlossaryDB:
    """Get a GlossaryDB instance."""
    return GlossaryDB()
