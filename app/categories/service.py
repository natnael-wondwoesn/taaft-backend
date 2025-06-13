# app/categories/service.py
"""
Service for managing tool categories
"""
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorCollection
import os
import json
import re

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
        self.categories_collection = None
        self.svg_dir = "static/category-icons"

        # Ensure SVG directory exists
        os.makedirs(self.svg_dir, exist_ok=True)

    async def _save_svg_file(self, category_id: str, svg_content: str) -> str:
        """
        Save SVG content to a file and return the relative path

        Args:
            category_id: The category ID to use as the filename
            svg_content: The SVG content to save

        Returns:
            The relative path to the saved SVG file
        """
        try:
            # Create a safe filename from the category ID
            filename = f"{category_id}.svg"
            filepath = os.path.join(self.svg_dir, filename)

            # Save the SVG content to the file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(svg_content)

            # Return the relative path that can be used in URLs
            return f"/static/category-icons/{filename}"
        except Exception as e:
            logger.error(f"Error saving SVG file for category {category_id}: {str(e)}")
            return None

    async def _get_svg_path(
        self, category_id: str, svg_content: Optional[str]
    ) -> Optional[str]:
        """
        Get the path to an SVG file, creating it if necessary

        Args:
            category_id: The category ID
            svg_content: The SVG content to save if the file doesn't exist

        Returns:
            The relative path to the SVG file, or None if no SVG is available
        """
        if not svg_content:
            return None

        filename = f"{category_id}.svg"
        filepath = os.path.join(self.svg_dir, filename)

        # If the file doesn't exist and we have SVG content, save it
        if not os.path.exists(filepath) and svg_content:
            return await self._save_svg_file(category_id, svg_content)

        # If the file exists, return its path
        if os.path.exists(filepath):
            return f"/static/category-icons/{filename}"

        return None

    async def _get_tools_collection(self) -> AsyncIOMotorCollection:
        """Get the tools collection"""
        if self.tools_collection is None:
            self.tools_collection = database.client.get_database(
                "taaft_db"
            ).get_collection("tools")
        return self.tools_collection

    async def _get_categories_collection(self) -> AsyncIOMotorCollection:
        """Get the categories collection"""
        if self.categories_collection is None:
            # Get database connection
            db = database.client.get_database("taaft_db")

            # Check if categories collection exists, create it if not
            collections = await db.list_collection_names()
            if "categories" not in collections:
                await db.create_collection("categories")
                logger.info("Created categories collection")

            self.categories_collection = db.get_collection("categories")
        return self.categories_collection

    async def get_all_categories(self) -> List[CategoryResponse]:
        """
        Get all available categories of tools

        Returns:
            List of CategoryResponse objects with id, name, slug, and count
        """
        try:
            # Get categories collection
            categories_collection = await self._get_categories_collection()
            categories_list = await categories_collection.find().to_list(length=100)
            
            # Get tools collection for accurate counts
            tools_collection = await self._get_tools_collection()

            # If we have categories in the dedicated collection, return those
            if categories_list:
                logger.info(
                    f"Found {len(categories_list)} categories in categories collection"
                )
                
                # Create a list to store categories with accurate counts
                categories_with_counts = []
                
                for cat in categories_list:
                    # Use the count stored in the database rather than calculating it dynamically
                    # This ensures consistency between the stored count and the API response
                    if "count" in cat:
                        count = cat["count"]
                    else:
                        # Fallback to counting if the count field is missing
                        # Use $or to avoid double counting the same tool
                        pipeline = [
                            {
                                "$match": {
                                    "$or": [
                                        {"categories.id": cat["id"]},  # Array-based categories
                                        {"category": cat["name"]}      # String-based category
                                    ]
                                }
                            },
                            # Group to get distinct tools
                            {
                                "$group": {
                                    "_id": "$_id"  # Group by tool ID to count distinct tools
                                }
                            },
                            # Count the results
                            {
                                "$count": "count"
                            }
                        ]
                        
                        count_results = await tools_collection.aggregate(pipeline).to_list(length=1)
                        count = count_results[0]["count"] if count_results else 0
                    
                    categories_with_counts.append(
                        CategoryResponse(
                            id=cat["id"],
                            name=cat["name"],
                            slug=cat["slug"],
                            count=count,  # Use database count or accurate count from aggregate query
                            svg=await self._get_svg_path(cat["id"], cat.get("svg")),
                        )
                    )
                
                return categories_with_counts

            # Otherwise, fall back to extracting from tools collection
            logger.warning(
                "No categories found in categories collection, checking tools collection. "
                "Attempting to derive categories from 'tools.category' string field."
            )
            tools_collection = await self._get_tools_collection()
            
            # Pipeline to get distinct, non-empty, string category names from tools.category
            pipeline = [
                {"$match": {"category": {"$exists": True, "$type": "string", "$ne": ""}}},
                {"$group": {"_id": "$category"}}, # Group by the category string
                {"$project": {"name": "$_id", "_id": 0}} # Project to 'name'
            ]
            # The result of distinct_category_name_docs will be like [{'name': 'Category A'}, {'name': 'Category B'}]
            distinct_category_name_docs = await tools_collection.aggregate(pipeline).to_list(None)
            
            categories = [] # Initialize list for categories derived from tools or defaults

            if distinct_category_name_docs:
                logger.info(f"Found {len(distinct_category_name_docs)} distinct category names in tools collection.")
                for doc in distinct_category_name_docs:
                    cat_name_str = doc["name"]
                    
                    # Count tools for this specific category string
                    count = await tools_collection.count_documents({"category": cat_name_str})

                    # Generate id and slug from name string (consistent with update_or_create_category)
                    generated_slug = cat_name_str.lower().replace(" ", "-")
                    # Basic sanitization for slug to be used as ID:
                    generated_id = re.sub(r'[^\w-]', '', generated_slug) # Keep alphanumeric and hyphens
                    generated_id = re.sub(r'-+', '-', generated_id).strip('-')
                    if not generated_id : generated_id = "unknown-" + str(len(categories)) # very basic fallback for empty id

                    categories.append(
                        CategoryResponse(
                            id=generated_id, 
                            name=cat_name_str,
                            slug=generated_id, # Slug is same as generated ID
                            count=count,
                            # No direct SVG content from tool.category string, _get_svg_path will handle
                            svg=await self._get_svg_path(generated_id, None), 
                        )
                    )
            else:
                logger.info("No valid category strings found in tools collection to derive categories from.")
                # categories list remains empty, will proceed to default categories if this path is taken.

            # If no categories were found in either dedicated collection or derived from tools, use defaults
            if not categories: # This checks if the list is still empty after attempting to derive from tools
                logger.warning("No categories found in database (neither dedicated collection nor derived from tools), using defaults")
                for category in self.default_categories:
                    categories.append(
                        CategoryResponse(
                            id=category["id"],
                            name=category["name"],
                            slug=category["slug"],
                            count=0,
                            svg=None,
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
                    id="marketing",
                    name="Marketing",
                    slug="marketing",
                    count=0,
                    svg=None,
                ),
                CategoryResponse(
                    id="e-commerce",
                    name="E-Commerce",
                    slug="e-commerce",
                    count=0,
                    svg=None,
                ),
                CategoryResponse(
                    id="analytics",
                    name="Analytics",
                    slug="analytics",
                    count=0,
                    svg=None,
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
            # First try to get from categories collection
            categories_collection = await self._get_categories_collection()
            category = await categories_collection.find_one({"id": category_id})

            if category:
                # Use the count stored in the database rather than calculating it dynamically
                if "count" in category:
                    count = category["count"]
                else:
                    # Fallback to counting if the count field is missing
                    # Get tools collection for accurate count
                    tools_collection = await self._get_tools_collection()
                    
                    # Use aggregation to avoid double counting
                    pipeline = [
                        {
                            "$match": {
                                "$or": [
                                    {"categories.id": category_id},  # Array-based categories
                                    {"category": category["name"]}   # String-based category
                                ]
                            }
                        },
                        # Group to get distinct tools
                        {
                            "$group": {
                                "_id": "$_id"  # Group by tool ID to count distinct tools
                            }
                        },
                        # Count the results
                        {
                            "$count": "count"
                        }
                    ]
                    
                    count_results = await tools_collection.aggregate(pipeline).to_list(length=1)
                    count = count_results[0]["count"] if count_results else 0
                
                return CategoryResponse(
                    id=category["id"],
                    name=category["name"],
                    slug=category["slug"],
                    count=count,  # Use database count or accurate count from aggregate query
                    svg=await self._get_svg_path(category["id"], category.get("svg")),
                )

            # If not found, fall back to getting from all categories
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
            # First try to get from categories collection
            categories_collection = await self._get_categories_collection()
            category = await categories_collection.find_one({"slug": slug})

            if category:
                # Use the count stored in the database rather than calculating it dynamically
                if "count" in category:
                    count = category["count"]
                else:
                    # Fallback to counting if the count field is missing
                    # Get tools collection for accurate count
                    tools_collection = await self._get_tools_collection()
                    
                    # Use aggregation to avoid double counting
                    pipeline = [
                        {
                            "$match": {
                                "$or": [
                                    {"categories.id": category["id"]},  # Array-based categories
                                    {"category": category["name"]}      # String-based category
                                ]
                            }
                        },
                        # Group to get distinct tools
                        {
                            "$group": {
                                "_id": "$_id"  # Group by tool ID to count distinct tools
                            }
                        },
                        # Count the results
                        {
                            "$count": "count"
                        }
                    ]
                    
                    count_results = await tools_collection.aggregate(pipeline).to_list(length=1)
                    count = count_results[0]["count"] if count_results else 0
                
                return CategoryResponse(
                    id=category["id"],
                    name=category["name"],
                    slug=category["slug"],
                    count=count,  # Use database count or accurate count from aggregate query
                    svg=await self._get_svg_path(category["id"], category.get("svg")),
                )

            # If not found, fall back to getting from all categories
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

    async def update_or_create_category(
        self, category_data: Dict[str, Any]
    ) -> Optional[CategoryResponse]:
        """
        Update an existing category or create a new one if it doesn't exist.
        Increments the count for the category.

        Args:
            category_data: Dictionary containing id, name, and optionally slug

        Returns:
            CategoryResponse object for the updated or created category
        """
        try:
            if (
                not category_data
                or "id" not in category_data
                or "name" not in category_data
            ):
                logger.error("Invalid category data: missing required fields")
                return None

            # Generate slug if not provided
            if "slug" not in category_data:
                category_data["slug"] = category_data["name"].lower().replace(" ", "-")

            # Get categories collection
            categories_collection = await self._get_categories_collection()

            # Check if category already exists
            existing_category = await categories_collection.find_one(
                {"id": category_data["id"]}
            )

            if existing_category:
                # Update existing category
                count = existing_category.get("count", 0) + 1
                await categories_collection.update_one(
                    {"id": category_data["id"]},
                    {
                        "$set": {
                            "name": category_data["name"],
                            "slug": category_data["slug"],
                            "count": count,
                        }
                    },
                )
                logger.info(
                    f"Updated category {category_data['id']} with count {count}"
                )
            else:
                # Create new category with count 1
                new_category = {
                    "id": category_data["id"],
                    "name": category_data["name"],
                    "slug": category_data["slug"],
                    "count": 1,
                }
                await categories_collection.insert_one(new_category)
                logger.info(f"Created new category {category_data['id']}")

            # Return the updated or created category
            return CategoryResponse(
                id=category_data["id"],
                name=category_data["name"],
                slug=category_data["slug"],
                count=(
                    1
                    if not existing_category
                    else existing_category.get("count", 0) + 1
                ),
                svg=category_data.get("svg"),
            )

        except Exception as e:
            logger.error(f"Error updating or creating category: {str(e)}")
            return None

    async def get_category_by_name(self, name: str) -> Optional[CategoryResponse]:
        """
        Get a category by its name (case-insensitive)

        Args:
            name: Name of the category to fetch

        Returns:
            CategoryResponse object if found, None otherwise
        """
        try:
            categories_collection = await self._get_categories_collection()
            # Try case-insensitive match in the collection
            category = await categories_collection.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}})
            if category:
                # Use the count stored in the database rather than calculating it dynamically
                if "count" in category:
                    count = category["count"]
                else:
                    # Fallback to counting if the count field is missing
                    # Get tools collection for accurate count
                    tools_collection = await self._get_tools_collection()
                    
                    # Use aggregation to avoid double counting
                    pipeline = [
                        {
                            "$match": {
                                "$or": [
                                    {"categories.id": category["id"]},  # Array-based categories
                                    {"category": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}  # String-based category (case-insensitive)
                                ]
                            }
                        },
                        # Group to get distinct tools
                        {
                            "$group": {
                                "_id": "$_id"  # Group by tool ID to count distinct tools
                            }
                        },
                        # Count the results
                        {
                            "$count": "count"
                        }
                    ]
                    
                    count_results = await tools_collection.aggregate(pipeline).to_list(length=1)
                    count = count_results[0]["count"] if count_results else 0
                
                return CategoryResponse(
                    id=category["id"],
                    name=category["name"],
                    slug=category["slug"],
                    count=count,  # Use database count or accurate count from aggregate query
                    svg=await self._get_svg_path(category["id"], category.get("svg")),
                )
            # Fallback: search in all categories (in-memory)
            categories = await self.get_all_categories()
            for category in categories:
                if category.name.lower() == name.lower():
                    return category
            return None
        except Exception as e:
            logger.error(f"Error getting category by name: {str(e)}")
            return None


# Create singleton instance
categories_service = CategoriesService()
