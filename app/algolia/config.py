# app/algolia/config.py
"""
Configuration for Algolia search integration
Handles initialization and configuration of Algolia client and indexes
"""
import os
from typing import Dict, List, Optional, Any, Union
from pydantic_settings import BaseSettings
from algoliasearch.search.client import SearchClientSync as SearchClient
from ..logger import logger


class AlgoliaSettings(BaseSettings):
    """Settings for Algolia search"""

    app_id: str
    api_key: str
    search_only_api_key: str
    write_api_key: str
    tools_index_name: str = "taaft_tools"
    glossary_index_name: str = "taaft_glossary"

    model_config = {
        "env_prefix": "ALGOLIA_",
        "env_file": ".env",
        "extra": "ignore",  # Ignore extra fields that aren't part of the model
    }


# Load settings from environment variables
try:
    settings = AlgoliaSettings()
    logger.info(f"Algolia configuration loaded. App ID: {settings.app_id}")
except Exception as e:
    logger.error(f"Failed to load Algolia settings: {str(e)}")
    # Create empty settings for development or when Algolia is not configured
    settings = AlgoliaSettings(
        app_id="",
        api_key="",
        search_only_api_key="",
        write_api_key="",
        tools_index_name="taaft_tools",
        glossary_index_name="taaft_glossary",
    )


class AlgoliaConfig:
    """Configuration for Algolia search"""

    # Singleton instance
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AlgoliaConfig, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize Algolia client and indexes"""
        self.app_id = settings.app_id
        self.api_key = settings.api_key
        self.search_only_api_key = settings.search_only_api_key
        self.write_api_key = settings.write_api_key
        self.tools_index_name = settings.tools_index_name
        self.glossary_index_name = settings.glossary_index_name

        # Initialize client only if credentials are provided
        self.client = None

        if self.app_id and self.api_key:
            try:
                # Create the client using the SearchClient constructor with v4 syntax
                self.client = SearchClient(self.app_id, self.write_api_key)
                logger.info("Algolia client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Algolia client: {str(e)}")
                self.client = None
        else:
            logger.warning(
                "Algolia credentials not provided. Search functionality will be limited."
            )

    def is_configured(self) -> bool:
        """Check if Algolia is properly configured"""
        return self.client is not None

    def get_search_only_api_key(self) -> str:
        """Get the search-only API key for frontend use"""
        return self.search_only_api_key

    def configure_tools_index(self):
        """Configure the tools index with proper settings"""
        if not self.is_configured():
            logger.warning(
                "Algolia not configured. Skipping tools index configuration."
            )
            return

        try:
            # Configure searchable attributes using the updated API structure
            settings = {
                "searchableAttributes": [
                    "name",
                    "description",
                    "long_description",
                    "features",
                    "use_cases",
                    "categories.name",
                ],
                # Configure custom ranking
                "customRanking": [
                    "desc(trending_score)",
                    "desc(ratings.average)",
                    "desc(is_featured)",
                    "desc(updated_at)",
                ],
                # Configure facets for filtering
                "attributesForFaceting": [
                    "categories.name",
                    "categories.id",
                    "pricing.type",
                    "is_featured",
                    "is_sponsored",
                    "searchable(features)",
                ],
                # Configure highlighting
                "attributesToHighlight": ["name", "description", "features"],
                # Configure snippeting
                "attributesToSnippet": ["long_description:50", "description:30"],
                # Configure pagination
                "hitsPerPage": 20,
                # Additional settings
                "typoTolerance": True,
                "distinct": True,
                "enablePersonalization": True,
                "queryLanguages": ["en"],
                "removeWordsIfNoResults": "allOptional",
            }

            # Fix: Use the correct format for set_settings
            response = self.client.set_settings(self.tools_index_name, settings)
            logger.info("Algolia tools index configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure Algolia tools index: {str(e)}")

    def configure_glossary_index(self):
        """Configure the glossary index with proper settings"""
        if not self.is_configured():
            logger.warning(
                "Algolia not configured. Skipping glossary index configuration."
            )
            return

        try:
            # Configure searchable attributes using the updated API structure
            settings = {
                "searchableAttributes": ["term", "definition", "related_terms"],
                # Configure custom ranking
                "customRanking": ["desc(is_featured)", "desc(updated_at)"],
                # Configure facets
                "attributesForFaceting": ["letter_group", "categories"],
                # Configure highlighting
                "attributesToHighlight": ["term", "definition"],
                # Configure snippeting
                "attributesToSnippet": ["definition:50"],
                # Configure pagination
                "hitsPerPage": 50,
                # Additional settings
                "typoTolerance": True,
                "distinct": True,
                "queryLanguages": ["en"],
            }

            # Fix: Use the correct format for set_settings
            response = self.client.set_settings(self.glossary_index_name, settings)
            logger.info("Algolia glossary index configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure Algolia glossary index: {str(e)}")

    def save_object(
        self,
        index_name: str,
        obj: Dict[str, Any],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Save an object to an Algolia index

        Args:
            index_name: Name of the index
            obj: Object to save
            request_options: Optional request options

        Returns:
            Response from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping save_object.")
            return {"error": "Algolia not configured"}

        try:
            # Add wait_for_task to request options if it doesn't exist
            if request_options is None:
                request_options = {}
            if "wait_for_task" not in request_options:
                request_options["wait_for_task"] = True

            # Save object to Algolia
            response = self.client.save_objects(index_name, [obj], request_options)
            return response
        except Exception as e:
            logger.error(f"Error saving object to Algolia: {str(e)}")
            return {"error": str(e)}

    def save_objects(
        self,
        index_name: str,
        objects: List[Dict[str, Any]],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Save multiple objects to an Algolia index

        Args:
            index_name: Name of the index
            objects: Objects to save
            request_options: Optional request options

        Returns:
            Response from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping save_objects.")
            return {"error": "Algolia not configured"}

        try:
            # Add wait_for_task to request options if it doesn't exist
            if request_options is None:
                request_options = {}
            if "wait_for_task" not in request_options:
                request_options["wait_for_task"] = True

            # Save objects to Algolia
            response = self.client.save_objects(index_name, objects, request_options)
            return response
        except Exception as e:
            logger.error(f"Error saving objects to Algolia: {str(e)}")
            return {"error": str(e)}

    def delete_object(
        self,
        index_name: str,
        object_id: str,
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delete an object from an Algolia index

        Args:
            index_name: Name of the index
            object_id: ID of the object to delete
            request_options: Optional request options

        Returns:
            Response from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping delete_object.")
            return {"error": "Algolia not configured"}

        try:
            # Add wait_for_task to request options if it doesn't exist
            if request_options is None:
                request_options = {}
            if "wait_for_task" not in request_options:
                request_options["wait_for_task"] = True

            # Delete object from Algolia
            response = self.client.delete_object(index_name, object_id, request_options)
            return response
        except Exception as e:
            logger.error(f"Error deleting object from Algolia: {str(e)}")
            return {"error": str(e)}

    def delete_objects(
        self,
        index_name: str,
        object_ids: List[str],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delete multiple objects from an Algolia index

        Args:
            index_name: Name of the index
            object_ids: IDs of the objects to delete
            request_options: Optional request options

        Returns:
            Response from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping delete_objects.")
            return {"error": "Algolia not configured"}

        try:
            # Add wait_for_task to request options if it doesn't exist
            if request_options is None:
                request_options = {}
            if "wait_for_task" not in request_options:
                request_options["wait_for_task"] = True

            # Delete objects from Algolia
            response = self.client.delete_objects(
                index_name, object_ids, request_options
            )
            return response
        except Exception as e:
            logger.error(f"Error deleting objects from Algolia: {str(e)}")
            return {"error": str(e)}

    def partial_update_object(
        self,
        index_name: str,
        partial_object: Dict[str, Any],
        request_options: Optional[Dict[str, Any]] = None,
        create_if_not_exists: bool = True,
    ) -> Dict[str, Any]:
        """
        Partially update an object in an Algolia index

        Args:
            index_name: Name of the index
            partial_object: Object with partial updates (must include objectID)
            request_options: Optional request options
            create_if_not_exists: Whether to create the object if it doesn't exist

        Returns:
            Response from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping partial_update_object.")
            return {"error": "Algolia not configured"}

        try:
            # Verify objectID is present
            if "objectID" not in partial_object:
                return {"error": "objectID is required for partial updates"}

            # Add wait_for_task to request options if it doesn't exist
            if request_options is None:
                request_options = {}
            if "wait_for_task" not in request_options:
                request_options["wait_for_task"] = True

            # Create or update options
            if create_if_not_exists:
                request_options["create_if_not_exists"] = True

            # Partially update object in Algolia
            response = self.client.partial_update_objects(
                index_name, [partial_object], request_options
            )
            return response
        except Exception as e:
            logger.error(f"Error partially updating object in Algolia: {str(e)}")
            return {"error": str(e)}

    def partial_update_objects(
        self,
        index_name: str,
        partial_objects: List[Dict[str, Any]],
        request_options: Optional[Dict[str, Any]] = None,
        create_if_not_exists: bool = True,
    ) -> Dict[str, Any]:
        """
        Partially update multiple objects in an Algolia index

        Args:
            index_name: Name of the index
            partial_objects: Objects with partial updates (must include objectID)
            request_options: Optional request options
            create_if_not_exists: Whether to create objects if they don't exist

        Returns:
            Response from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping partial_update_objects.")
            return {"error": "Algolia not configured"}

        try:
            # Verify objectID is present in all objects
            for obj in partial_objects:
                if "objectID" not in obj:
                    return {"error": "objectID is required for all partial updates"}

            # Add wait_for_task to request options if it doesn't exist
            if request_options is None:
                request_options = {}
            if "wait_for_task" not in request_options:
                request_options["wait_for_task"] = True

            # Create or update options
            if create_if_not_exists:
                request_options["create_if_not_exists"] = True

            # Partially update objects in Algolia
            response = self.client.partial_update_objects(
                index_name, partial_objects, request_options
            )
            return response
        except Exception as e:
            logger.error(f"Error partially updating objects in Algolia: {str(e)}")
            return {"error": str(e)}

    def clear_index(
        self,
        index_name: str,
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Clear all objects from an Algolia index

        Args:
            index_name: Name of the index
            request_options: Optional request options

        Returns:
            Response from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping clear_index.")
            return {"error": "Algolia not configured"}

        try:
            # Add wait_for_task to request options if it doesn't exist
            if request_options is None:
                request_options = {}
            if "wait_for_task" not in request_options:
                request_options["wait_for_task"] = True

            # Clear index in Algolia
            response = self.client.clear_objects(index_name, request_options)
            return response
        except Exception as e:
            logger.error(f"Error clearing Algolia index: {str(e)}")
            return {"error": str(e)}

    def get_index_settings(self, index_name: str) -> Dict[str, Any]:
        """
        Get settings for an Algolia index

        Args:
            index_name: Name of the index

        Returns:
            Settings for the index
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping get_settings.")
            return {"error": "Algolia not configured"}

        try:
            # Get index settings from Algolia
            response = self.client.get_settings(index_name)
            return response
        except Exception as e:
            logger.error(f"Error getting Algolia index settings: {str(e)}")
            return {"error": str(e)}

    def wait_for_task(
        self, index_name: str, task_id: int, timeout_ms: int = 5000
    ) -> Dict[str, Any]:
        """
        Wait for a task to complete in Algolia

        Args:
            index_name: Name of the index
            task_id: ID of the task to wait for
            timeout_ms: Timeout in milliseconds

        Returns:
            Response from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping wait_for_task.")
            return {"error": "Algolia not configured"}

        try:
            # Wait for task to complete in Algolia
            response = self.client.wait_task(index_name, task_id, timeout_ms)
            return response
        except Exception as e:
            logger.error(f"Error waiting for Algolia task: {str(e)}")
            return {"error": str(e)}

    def search(
        self,
        index_name: str,
        query: str,
        search_params: Optional[Dict[str, Any]] = None,
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Search for objects in an Algolia index

        Args:
            index_name: Name of the index
            query: Search query
            search_params: Optional search parameters
            request_options: Optional request options

        Returns:
            Search results from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping search.")
            return {
                "hits": [],
                "nbHits": 0,
                "page": 0,
                "nbPages": 0,
                "hitsPerPage": 0,
                "processingTimeMS": 0,
                "query": query,
                "params": search_params or {},
                "error": "Algolia not configured",
            }

        try:
            # Prepare search parameters
            params = {"query": query}
            if search_params:
                params.update(search_params)

            # Search in Algolia
            response = self.client.search_single_index(
                index_name, params, request_options
            )
            return response
        except Exception as e:
            logger.error(f"Error searching in Algolia: {str(e)}")
            return {
                "hits": [],
                "nbHits": 0,
                "page": 0,
                "nbPages": 0,
                "hitsPerPage": 0,
                "processingTimeMS": 0,
                "query": query,
                "params": search_params or {},
                "error": str(e),
            }

    def multi_search(self, queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute multiple searches in parallel

        Args:
            queries: List of search queries

        Returns:
            Search results from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping multi_search.")
            return {"results": [], "error": "Algolia not configured"}

        try:
            # Execute multi-search in Algolia
            response = self.client.multiple_queries(queries)
            return response
        except Exception as e:
            logger.error(f"Error executing multi-search in Algolia: {str(e)}")
            return {"results": [], "error": str(e)}

    def update_object(
        self,
        index_name: str,
        obj: Dict[str, Any],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update an object in an Algolia index (complete replacement)

        Args:
            index_name: Name of the index
            obj: Object to update (must include objectID)
            request_options: Optional request options

        Returns:
            Response from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping update_object.")
            return {"error": "Algolia not configured"}

        try:
            # Verify objectID is present
            if "objectID" not in obj:
                return {"error": "objectID is required for updates"}

            # Add wait_for_task to request options if it doesn't exist
            if request_options is None:
                request_options = {}
            if "wait_for_task" not in request_options:
                request_options["wait_for_task"] = True

            # Update object in Algolia
            response = self.client.save_objects(index_name, [obj], request_options)
            return response
        except Exception as e:
            logger.error(f"Error updating object in Algolia: {str(e)}")
            return {"error": str(e)}

    def update_objects(
        self,
        index_name: str,
        objects: List[Dict[str, Any]],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update multiple objects in an Algolia index (complete replacement)

        Args:
            index_name: Name of the index
            objects: Objects to update (must include objectID)
            request_options: Optional request options

        Returns:
            Response from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping update_objects.")
            return {"error": "Algolia not configured"}

        try:
            # Verify objectID is present in all objects
            for obj in objects:
                if "objectID" not in obj:
                    return {"error": "objectID is required for all updates"}

            # Add wait_for_task to request options if it doesn't exist
            if request_options is None:
                request_options = {}
            if "wait_for_task" not in request_options:
                request_options["wait_for_task"] = True

            # Update objects in Algolia
            response = self.client.save_objects(index_name, objects, request_options)
            return response
        except Exception as e:
            logger.error(f"Error updating objects in Algolia: {str(e)}")
            return {"error": str(e)}

    def get_object(
        self,
        index_name: str,
        object_id: str,
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get an object from an Algolia index

        Args:
            index_name: Name of the index
            object_id: ID of the object to get
            request_options: Optional request options

        Returns:
            Object from Algolia
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Skipping get_object.")
            return {"error": "Algolia not configured"}

        try:
            # Get object from Algolia
            response = self.client.get_object(index_name, object_id, request_options)
            return response
        except Exception as e:
            logger.error(f"Error getting object from Algolia: {str(e)}")
            return {"error": str(e)}


# Create a singleton instance of AlgoliaConfig
algolia_config = AlgoliaConfig()
