# app/categories/service.py
"""
Service for managing tool categories
"""
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorCollection

from .models import Category, CategoryResponse
from ..logger import logger
from ..database import database


class CategoriesService:
    """Service for fetching and managing tool categories"""

    def __init__(self):
        # Default categories that will be returned if no categories are found in the database
        self.default_categories = [
            {"id": "marketing", "name": "Marketing", "slug": "marketing"},
            {"id": "e-commerce", "name": "E-Commerce", "slug": "e-commerce"},
            {"id": "analytics", "name": "Analytics", "slug": "analytics"},
            {"id": "content", "name": "Content Creation", "slug": "content-creation"},
            {"id": "design", "name": "Design", "slug": "design"},
            {"id": "productivity", "name": "Productivity", "slug": "productivity"},
            {
                "id": "code",
                "name": "Software Development",
                "slug": "software-development",
            },
            {"id": "chat", "name": "Chat & Conversation", "slug": "chat-conversation"},
            {"id": "research", "name": "Research", "slug": "research"},
            {"id": "data", "name": "Data Analysis", "slug": "data-analysis"},
        ]
        self.tools_collection = None

    async def _get_tools_collection(self) -> AsyncIOMotorCollection:
        """Get the tools collection"""
        if not self.tools_collection:
            self.tools_collection = database.client.get_database(
                "taaft_db"
            ).get_collection("tools")
        return self.tools_collection

    async def get_all_categories(self) -> List[CategoryResponse]:
        """
        Get all available categories of tools

        Returns:
            List of CategoryResponse objects with id, name, slug, and count
        """
        try:
            # Get tools collection
            tools_collection = await self._get_tools_collection()

            # Get distinct categories from database
            db_categories = await tools_collection.distinct("categories")

            # Process database categories
            categories = []

            for category in db_categories:
                if (
                    isinstance(category, dict)
                    and "name" in category
                    and "id" in category
                ):
                    # Get count of tools in this category using aggregation
                    count = await tools_collection.count_documents(
                        {"categories.id": category["id"]}
                    )

                    # Create category response
                    cat_name = category["name"]
                    categories.append(
                        CategoryResponse(
                            id=category["id"],
                            name=cat_name,
                            slug=category.get(
                                "slug", cat_name.lower().replace(" ", "-")
                            ),
                            count=count,
                        )
                    )

            # If no categories were found in the database, use the defaults
            if not categories:
                logger.warning("No categories found in database, using defaults")
                for category in self.default_categories:
                    categories.append(
                        CategoryResponse(
                            id=category["id"],
                            name=category["name"],
                            slug=category["slug"],
                            count=0,
                        )
                    )

            # Sort categories by count (descending)
            categories.sort(key=lambda x: x.count, reverse=True)

            return categories

        except Exception as e:
            logger.error(f"Error getting categories: {str(e)}")
            # Return default categories in case of error
            return [
                CategoryResponse(
                    id="marketing", name="Marketing", slug="marketing", count=0
                ),
                CategoryResponse(
                    id="e-commerce", name="E-Commerce", slug="e-commerce", count=0
                ),
                CategoryResponse(
                    id="analytics", name="Analytics", slug="analytics", count=0
                ),
            ]

    async def get_category_by_id(self, category_id: str) -> Optional[CategoryResponse]:
        """
        Get a category by its ID

        Args:
            category_id: ID of the category to fetch

        Returns:
            CategoryResponse object if found, None otherwise
        """
        try:
            # Get all categories
            categories = await self.get_all_categories()

            # Find the category with the matching ID
            for category in categories:
                if category.id == category_id:
                    return category

            # If not found, return None
            return None

        except Exception as e:
            logger.error(f"Error getting category by ID: {str(e)}")
            return None

    async def get_category_by_slug(self, slug: str) -> Optional[CategoryResponse]:
        """
        Get a category by its slug

        Args:
            slug: Slug of the category to fetch

        Returns:
            CategoryResponse object if found, None otherwise
        """
        try:
            # Get all categories
            categories = await self.get_all_categories()

            # Find the category with the matching slug
            for category in categories:
                if category.slug == slug:
                    return category

            # If not found, return None
            return None

        except Exception as e:
            logger.error(f"Error getting category by slug: {str(e)}")
            return None


# Create singleton instance
categories_service = CategoriesService()
