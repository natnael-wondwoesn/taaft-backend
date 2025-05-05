from typing import List, Dict, Any, Optional, Tuple
from bson import ObjectId
from ..database.database import blog_articles, glossary_terms
from ..logger import logger
from pymongo import ASCENDING, DESCENDING


class LinkingDB:
    """Database operations for bidirectional linking between glossary terms and blog articles."""

    _cache = {}
    _cache_enabled = False

    @classmethod
    def enable_cache(cls):
        """Enable caching for improved performance."""
        cls._cache_enabled = True
        logger.info("Bidirectional linking cache enabled")

    @classmethod
    def disable_cache(cls):
        """Disable caching."""
        cls._cache_enabled = False
        cls._cache = {}
        logger.info("Bidirectional linking cache disabled and cleared")

    @classmethod
    def clear_cache(cls):
        """Clear the cache."""
        cls._cache = {}
        logger.info("Bidirectional linking cache cleared")

    async def get_term_with_articles(
        self, term_id: str, article_limit: int = 10
    ) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Get a glossary term and its related articles.

        Args:
            term_id: ID of the glossary term
            article_limit: Maximum number of articles to return

        Returns:
            Tuple of (term, articles) or None if term doesn't exist
        """
        # Check cache first if enabled
        cache_key = f"term_articles:{term_id}:{article_limit}"
        if self._cache_enabled and cache_key in self._cache:
            logger.debug(f"Cache hit for {cache_key}")
            return self._cache[cache_key]

        # Check if the term exists
        if not ObjectId.is_valid(term_id):
            return None

        term = await glossary_terms.find_one({"_id": ObjectId(term_id)})
        if not term:
            return None

        # Find articles that reference this term
        articles_cursor = blog_articles.find(
            {"related_glossary_terms": str(term_id)}
        ).limit(article_limit)

        articles = await articles_cursor.to_list(length=article_limit)

        result = (term, articles)

        # Cache the result if caching is enabled
        if self._cache_enabled:
            self._cache[cache_key] = result

        return result

    async def get_all_terms_summary(
        self, include_article_counts: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all glossary terms with summary information.

        Args:
            include_article_counts: Whether to include article counts for each term

        Returns:
            List of term summary dictionaries
        """
        # Check cache first if enabled
        cache_key = f"all_terms_summary:{include_article_counts}"
        if self._cache_enabled and cache_key in self._cache:
            logger.debug(f"Cache hit for {cache_key}")
            return self._cache[cache_key]

        # Get all terms
        terms_cursor = glossary_terms.find(
            {},
            projection={
                "_id": 1,
                "name": 1,
                "slug": 1,
                "short_definition": 1,
            },
        ).sort("name", ASCENDING)

        terms = await terms_cursor.to_list(length=None)

        # Format terms and add article counts if requested
        result = []
        for term in terms:
            term_summary = {
                "id": str(term["_id"]),
                "name": term["name"],
                "slug": term.get("slug", ""),
                "short_definition": term.get("short_definition", ""),
            }

            if include_article_counts:
                # Count articles that reference this term
                article_count = await blog_articles.count_documents(
                    {"related_glossary_terms": str(term["_id"])}
                )
                term_summary["article_count"] = article_count

            result.append(term_summary)

        # Cache the result if caching is enabled
        if self._cache_enabled:
            self._cache[cache_key] = result

        return result

    async def generate_static_mapping(self) -> Dict[str, Any]:
        """
        Generate a static mapping of terms to articles and articles to terms.
        This can be used for static generation or caching on the frontend.

        Returns:
            Dictionary with terms_to_articles and articles_to_terms mappings
        """
        # Check cache first if enabled
        cache_key = "static_mapping"
        if self._cache_enabled and cache_key in self._cache:
            logger.debug(f"Cache hit for {cache_key}")
            return self._cache[cache_key]

        # Get all terms with minimal info
        terms_cursor = glossary_terms.find(
            {},
            projection={
                "_id": 1,
                "name": 1,
                "slug": 1,
                "short_definition": 1,
            },
        )

        terms = await terms_cursor.to_list(length=None)

        # Get all articles with minimal info
        articles_cursor = blog_articles.find(
            {},
            projection={
                "_id": 1,
                "title": 1,
                "url": 1,
                "body": 1,
                "images": 1,
                "related_glossary_terms": 1,
            },
        )

        articles = await articles_cursor.to_list(length=None)

        # Create the mappings
        terms_to_articles = {}
        articles_to_terms = {}

        # Build terms_to_articles mapping
        for term in terms:
            term_id = str(term["_id"])
            terms_to_articles[term_id] = {
                "term": {
                    "id": term_id,
                    "name": term["name"],
                    "slug": term.get("slug", ""),
                    "short_definition": term.get("short_definition", ""),
                },
                "article_ids": [],
            }

        # Build articles_to_terms mapping
        for article in articles:
            article_id = str(article["_id"])

            # Get related term IDs from article
            related_term_ids = article.get("related_glossary_terms", [])

            # Add article to terms_to_articles mapping
            for term_id in related_term_ids:
                if term_id in terms_to_articles:
                    terms_to_articles[term_id]["article_ids"].append(article_id)

            # Create a preview of the body text
            body_preview = (
                article.get("body", "")[:150] + "..." if article.get("body") else None
            )

            # Create articles_to_terms mapping
            articles_to_terms[article_id] = {
                "article": {
                    "id": article_id,
                    "title": article["title"],
                    "url": article.get("url", ""),
                    "body_preview": body_preview,
                    "images": article.get("images", []),
                },
                "term_ids": related_term_ids,
            }

        result = {
            "terms_to_articles": terms_to_articles,
            "articles_to_terms": articles_to_terms,
        }

        # Cache the result if caching is enabled
        if self._cache_enabled:
            self._cache[cache_key] = result

        return result


async def get_linking_db() -> LinkingDB:
    """Get a LinkingDB instance."""
    return LinkingDB()
