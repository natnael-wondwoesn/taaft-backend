from typing import List, Dict, Any, Optional
from ..database.database import blog_articles, glossary_terms
from ..logger import logger
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING


class BlogDB:
    """Database operations for blog articles."""

    async def get_article_by_id(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Get a blog article by ID."""
        if not ObjectId.is_valid(article_id):
            return None

        article = await blog_articles.find_one({"_id": ObjectId(article_id)})
        return article

    async def get_article_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get a blog article by URL."""
        article = await blog_articles.find_one({"url": url})
        return article

    async def list_articles(
        self,
        skip: int = 0,
        limit: int = 20,
        sort_by: str = "_id",  # Default sort by _id since there's no published_date
        sort_order: int = DESCENDING,
    ) -> List[Dict[str, Any]]:
        """List blog articles with pagination and sorting."""
        cursor = blog_articles.find().skip(skip).limit(limit)

        # Apply sorting
        cursor = cursor.sort(sort_by, sort_order)

        # Convert cursor to list
        results = await cursor.to_list(length=limit)
        return results

    async def get_articles_by_glossary_term(
        self,
        term_id: str,
        skip: int = 0,
        limit: int = 10,
        sort_by: str = "_id",  # Default sort by _id
        sort_order: int = DESCENDING,
    ) -> List[Dict[str, Any]]:
        """Get blog articles related to a specific glossary term."""
        if not ObjectId.is_valid(term_id):
            return []

        # Find articles that have this term ID in their related_glossary_terms
        query = {"related_glossary_terms": str(term_id)}

        cursor = blog_articles.find(query).skip(skip).limit(limit)

        # Apply sorting
        cursor = cursor.sort(sort_by, sort_order)

        # Convert cursor to list
        results = await cursor.to_list(length=limit)
        return results

    async def create_article(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new blog article."""
        result = await blog_articles.insert_one(article_data)

        # Fetch the created document
        created_article = await self.get_article_by_id(str(result.inserted_id))
        return created_article

    async def update_article(
        self, article_id: str, update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update an existing blog article."""
        if not ObjectId.is_valid(article_id):
            return None

        # Remove None values from update data
        clean_update = {k: v for k, v in update_data.items() if v is not None}

        if not clean_update:
            # No valid update fields, just return the current document
            return await self.get_article_by_id(article_id)

        # Update the document
        result = await blog_articles.update_one(
            {"_id": ObjectId(article_id)}, {"$set": clean_update}
        )

        if result.modified_count == 0:
            # Document wasn't found or no changes were made
            return None

        # Return the updated document
        return await self.get_article_by_id(article_id)

    async def delete_article(self, article_id: str) -> bool:
        """Delete a blog article."""
        if not ObjectId.is_valid(article_id):
            return False

        result = await blog_articles.delete_one({"_id": ObjectId(article_id)})
        return result.deleted_count > 0

    async def get_glossary_terms_for_article(
        self, article_id: str
    ) -> List[Dict[str, Any]]:
        """Get related glossary terms for a specific blog article."""
        if not ObjectId.is_valid(article_id):
            return []

        # Get the article
        article = await self.get_article_by_id(article_id)
        if not article or "related_glossary_terms" not in article:
            return []

        # Get the related glossary terms
        term_ids = article["related_glossary_terms"]
        if not term_ids:
            return []

        # Convert string IDs to ObjectIds
        object_ids = [
            ObjectId(term_id) for term_id in term_ids if ObjectId.is_valid(term_id)
        ]
        if not object_ids:
            return []

        # Find the glossary terms
        cursor = glossary_terms.find({"_id": {"$in": object_ids}})
        terms = await cursor.to_list(length=len(object_ids))
        return terms

    async def count_articles(self, filter_query: Dict[str, Any] = None) -> int:
        """Count blog articles with optional filtering."""
        query = filter_query or {}
        count = await blog_articles.count_documents(query)
        return count

    async def update_article_glossary_terms(
        self, article_id: str, term_ids: List[str]
    ) -> bool:
        """
        Update the related glossary terms for an article.

        Args:
            article_id: ID of the article to update
            term_ids: List of glossary term IDs to associate with the article

        Returns:
            True if successful, False otherwise
        """
        if not ObjectId.is_valid(article_id):
            return False

        # Validate the term IDs exist
        valid_term_ids = []
        for term_id in term_ids:
            if ObjectId.is_valid(term_id):
                term = await glossary_terms.find_one({"_id": ObjectId(term_id)})
                if term:
                    valid_term_ids.append(str(term_id))

        # Update the article
        result = await blog_articles.update_one(
            {"_id": ObjectId(article_id)},
            {"$set": {"related_glossary_terms": valid_term_ids}},
        )

        return result.modified_count > 0


async def get_blog_db() -> BlogDB:
    """Get a BlogDB instance."""
    return BlogDB()
