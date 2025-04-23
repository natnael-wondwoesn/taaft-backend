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

            # Filter by first letter if provided
            if filter_params.first_letter:
                # Case-insensitive regex to match terms starting with the given letter
                query["name"] = {
                    "$regex": f"^{filter_params.first_letter}",
                    "$options": "i",
                }

        # Execute query with pagination
        cursor = glossary_terms.find(query).skip(skip).limit(limit)

        # Apply sorting
        cursor = cursor.sort(sort_by, sort_order)

        # Convert cursor to list
        results = await cursor.to_list(length=limit)

        # Add first_letter field to each result
        for result in results:
            if "name" in result and result["name"]:
                # Extract first letter and convert to uppercase
                result["first_letter"] = result["name"][0].upper()

        return results

    async def get_term_by_id(self, term_id: str) -> Optional[Dict[str, Any]]:
        """Get a glossary term by ID."""
        if not ObjectId.is_valid(term_id):
            return None

        term = await glossary_terms.find_one({"_id": ObjectId(term_id)})

        # Add first_letter field if term exists
        if term and "name" in term and term["name"]:
            term["first_letter"] = term["name"][0].upper()

        return term

    async def get_term_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a glossary term by name."""
        term = await glossary_terms.find_one({"name": name})

        # Add first_letter field if term exists
        if term and "name" in term and term["name"]:
            term["first_letter"] = term["name"][0].upper()

        return term

    async def create_term(self, term_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new glossary term."""
        # Add first_letter field if not present
        if (
            "name" in term_data
            and term_data["name"]
            and "first_letter" not in term_data
        ):
            term_data["first_letter"] = term_data["name"][0].upper()

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

        # Update first_letter if name is being updated
        if "name" in clean_update and clean_update["name"]:
            clean_update["first_letter"] = clean_update["name"][0].upper()

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

            # Filter by first letter if provided
            if filter_params.first_letter:
                # Case-insensitive regex to match terms starting with the given letter
                query["name"] = {
                    "$regex": f"^{filter_params.first_letter}",
                    "$options": "i",
                }

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

    async def get_available_letters(self) -> List[str]:
        """Get all available first letters from the glossary terms."""
        pipeline = [
            {"$project": {"first_letter": {"$toUpper": {"$substr": ["$name", 0, 1]}}}},
            {"$group": {"_id": "$first_letter"}},
            {"$sort": {"_id": 1}},
        ]

        cursor = glossary_terms.aggregate(pipeline)
        results = await cursor.to_list(length=None)

        # Extract letters from results
        letters = [doc["_id"] for doc in results]
        return letters

    async def get_terms_grouped_by_letter(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all terms grouped by their first letter."""
        # Get all terms sorted by name
        all_terms = await self.list_terms(
            limit=1000,  # Set a high limit to get all terms
            sort_by="name",
            sort_order=ASCENDING,
        )

        # Group terms by first letter
        grouped_terms = {}
        for term in all_terms:
            if "name" in term and term["name"]:
                first_letter = term["name"][0].upper()
                term["first_letter"] = first_letter  # Ensure first_letter is set

                if first_letter not in grouped_terms:
                    grouped_terms[first_letter] = []
                grouped_terms[first_letter].append(term)

        return grouped_terms


async def get_glossary_db() -> GlossaryDB:
    """Get a GlossaryDB instance."""
    return GlossaryDB()
