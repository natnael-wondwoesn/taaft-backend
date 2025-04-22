# app/terms/database.py
"""
Database operations for terms feature
Handles storing and retrieving term definitions
"""
from typing import Dict, List, Optional, Any
from bson import ObjectId
import datetime
import asyncio
from ..database import database
from ..logger import logger


class TermsDB:
    """Database operations for terms feature"""

    def __init__(self):
        """Initialize the terms database connection"""
        self.db = database
        self.terms_collection = self.db.terms
        self.popular_collection = self.db.popular_terms

    async def get_term_definition(self, term_id: str) -> Optional[Dict[str, Any]]:
        """Get a term definition by ID"""
        if not ObjectId.is_valid(term_id):
            return None

        term = await self.terms_collection.find_one({"_id": ObjectId(term_id)})
        return term

    async def get_term_by_exact_match(self, term_text: str) -> Optional[Dict[str, Any]]:
        """Get a term definition by exact term match"""
        # Case-insensitive search for the exact term
        term = await self.terms_collection.find_one(
            {"term": {"$regex": f"^{term_text}$", "$options": "i"}}
        )
        return term

    async def create_term_definition(self, term_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new term definition"""
        # Add timestamps
        now = datetime.datetime.utcnow()
        term_data["timestamp"] = now

        # Insert into database
        result = await self.terms_collection.insert_one(term_data)
        term_data["_id"] = result.inserted_id

        # Update popular terms
        await self._update_popular_term(term_data["term"])

        return term_data

    async def get_user_term_history(
        self, user_id: str, limit: int = 20, skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get term definition history for a user"""
        cursor = (
            self.terms_collection.find({"user_id": user_id})
            .sort("timestamp", -1)  # Most recent first
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def get_term_history(
        self, limit: int = 20, skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all term definition history"""
        cursor = (
            self.terms_collection.find({})
            .sort("timestamp", -1)  # Most recent first
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def get_popular_terms(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most popular terms"""
        cursor = self.popular_collection.find({}).sort("count", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def _update_popular_term(self, term_text: str) -> None:
        """Update the popular terms collection when a term is requested"""
        # Case insensitive search
        popular_term = await self.popular_collection.find_one(
            {"term": {"$regex": f"^{term_text}$", "$options": "i"}}
        )

        if popular_term:
            # Update existing popular term
            await self.popular_collection.update_one(
                {"_id": popular_term["_id"]},
                {
                    "$inc": {"count": 1},
                    "$set": {"last_requested": datetime.datetime.utcnow()},
                },
            )
        else:
            # Create new popular term entry
            await self.popular_collection.insert_one(
                {
                    "term": term_text,
                    "count": 1,
                    "last_requested": datetime.datetime.utcnow(),
                }
            )


# Dependency to get the terms database connection
async def get_terms_db():
    """Get a database connection for terms"""
    return TermsDB()
