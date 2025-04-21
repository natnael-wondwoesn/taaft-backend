# app/algolia/config.py
"""
Configuration for Algolia search integration
Handles initialization and configuration of Algolia client and indexes
"""
import os
from typing import Dict, List, Optional, Any, Union
from pydantic_settings import BaseSettings
from algoliasearch.search.client import SearchClientSync
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
        self.tools_index = None
        self.glossary_index = None

        if self.app_id and self.api_key:
            try:
                # Create the client using the SearchClientSync constructor
                self.client = SearchClientSync(self.app_id, self.write_api_key)

                # Initialize indexes
                if self.client:
                    # The client doesn't have init_index method directly
                    # We need to create indexes differently
                    self.tools_index = self.tools_index_name
                    self.glossary_index = self.glossary_index_name

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
            response = self.client.set_settings(
                index_name=self.tools_index_name, index_settings=settings
            )
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
            response = self.client.set_settings(
                index_name=self.glossary_index_name, index_settings=settings
            )
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
        Save an object to the specified index

        Args:
            index_name: The name of the index
            obj: The object to save (must include an objectID or it will be auto-generated)
            request_options: Additional request options

        Returns:
            Dict containing the result of the operation
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot save object.")
            return {"status": "error", "message": "Algolia not configured"}

        try:
            response = self.client.save_object(
                index_name=index_name, obj=obj, request_options=request_options
            )
            return response.raw_responses[0]
        except Exception as e:
            logger.error(f"Failed to save object: {str(e)}")
            return {"status": "error", "message": str(e)}

    def save_objects(
        self,
        index_name: str,
        objects: List[Dict[str, Any]],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Save multiple objects to the specified index

        Args:
            index_name: The name of the index
            objects: List of objects to save (each must include an objectID or it will be auto-generated)
            request_options: Additional request options

        Returns:
            Dict containing the result of the operation
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot save objects.")
            return {"status": "error", "message": "Algolia not configured"}

        try:
            response = self.client.save_objects(
                index_name=index_name, objects=objects, request_options=request_options
            )
            return response.raw_responses[0]
        except Exception as e:
            logger.error(f"Failed to save objects: {str(e)}")
            return {"status": "error", "message": str(e)}

    def delete_object(
        self,
        index_name: str,
        object_id: str,
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delete a single object from the specified index

        Args:
            index_name: The name of the index
            object_id: The ID of the object to delete
            request_options: Optional request options

        Returns:
            Dict containing the operation result
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot delete object.")
            return {"status": "error", "message": "Algolia not configured"}

        try:
            # Use the client's delete_object method with the index_name parameter
            response = self.client.delete_object(
                index_name=index_name,
                object_id=object_id,
                request_options=request_options,
            )
            return response.raw_responses[0]
        except Exception as e:
            logger.error(
                f"Failed to delete object {object_id} from index {index_name}: {str(e)}"
            )
            return {"status": "error", "message": str(e)}

    def delete_objects(
        self,
        index_name: str,
        object_ids: List[str],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delete multiple objects from the specified index

        Args:
            index_name: The name of the index
            object_ids: The IDs of the objects to delete
            request_options: Optional request options

        Returns:
            Dict containing the operation result
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot delete objects.")
            return {"status": "error", "message": "Algolia not configured"}

        try:
            # Use the client's delete_objects method with the index_name parameter
            response = self.client.delete_objects(
                index_name=index_name,
                object_ids=object_ids,
                request_options=request_options,
            )
            return response.raw_responses[0]
        except Exception as e:
            logger.error(f"Failed to delete objects from index {index_name}: {str(e)}")
            return {"status": "error", "message": str(e)}

    def partial_update_object(
        self,
        index_name: str,
        partial_object: Dict[str, Any],
        request_options: Optional[Dict[str, Any]] = None,
        create_if_not_exists: bool = True,
    ) -> Dict[str, Any]:
        """
        Update parts of an object in the specified index

        Args:
            index_name: The name of the index
            partial_object: Object containing the fields to update.
                            Must include an objectID field.
            request_options: Additional request options
            create_if_not_exists: Whether to create the object if it doesn't exist

        Returns:
            Dict containing the result of the operation
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot perform partial update.")
            return {"status": "error", "message": "Algolia not configured"}

        if "objectID" not in partial_object:
            logger.error("Object must have an objectID for partial update")
            return {
                "status": "error",
                "message": "Object must have an objectID for partial update",
            }

        try:
            # Use the client's partial_update_object method with the parameters
            options = request_options or {}
            if "createIfNotExists" not in options:
                options["createIfNotExists"] = create_if_not_exists

            response = self.client.partial_update_object(
                index_name=index_name,
                partial_object=partial_object,
                request_options=options,
            )
            return response.raw_responses[0]
        except Exception as e:
            logger.error(f"Failed to partially update object: {str(e)}")
            return {"status": "error", "message": str(e)}

    def partial_update_objects(
        self,
        index_name: str,
        partial_objects: List[Dict[str, Any]],
        request_options: Optional[Dict[str, Any]] = None,
        create_if_not_exists: bool = True,
    ) -> Dict[str, Any]:
        """
        Update parts of multiple objects in the specified index

        Args:
            index_name: The name of the index
            partial_objects: List of objects containing the fields to update.
                           Each object must include an objectID field.
            request_options: Additional request options
            create_if_not_exists: Whether to create objects if they don't exist

        Returns:
            Dict containing the result of the operation
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot perform partial updates.")
            return {"status": "error", "message": "Algolia not configured"}

        # Verify all objects have objectID
        for obj in partial_objects:
            if "objectID" not in obj:
                logger.error("All objects must have an objectID for partial update")
                return {
                    "status": "error",
                    "message": "All objects must have an objectID for partial update",
                }

        try:
            # Use the client's partial_update_objects method with the parameters
            options = request_options or {}
            if "createIfNotExists" not in options:
                options["createIfNotExists"] = create_if_not_exists

            response = self.client.partial_update_objects(
                index_name=index_name,
                partial_objects=partial_objects,
                request_options=options,
            )
            return response.raw_responses[0]
        except Exception as e:
            logger.error(f"Failed to partially update objects: {str(e)}")
            return {"status": "error", "message": str(e)}

    def clear_index(
        self,
        index_name: str,
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Clear all objects from the specified index

        Args:
            index_name: The name of the index
            request_options: Optional request options

        Returns:
            Dict containing the operation result
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot clear index.")
            return {"status": "error", "message": "Algolia not configured"}

        try:
            # Use the client's clear_objects method with the index_name parameter
            response = self.client.clear_objects(
                index_name=index_name, request_options=request_options
            )
            return response.raw_responses[0]
        except Exception as e:
            logger.error(f"Failed to clear index {index_name}: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_index_settings(self, index_name: str) -> Dict[str, Any]:
        """
        Get the settings for the specified index

        Args:
            index_name: The name of the index

        Returns:
            Dict containing the index settings
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot get index settings.")
            return {}

        try:
            # Use the client's get_settings method with the index_name parameter
            response = self.client.get_settings(index_name=index_name)
            return response.body
        except Exception as e:
            logger.error(f"Failed to get settings for index {index_name}: {str(e)}")
            return {}

    def wait_for_task(
        self, index_name: str, task_id: int, timeout_ms: int = 5000
    ) -> Dict[str, Any]:
        """
        Wait for a task to complete on the specified index

        Args:
            index_name: The name of the index
            task_id: The task ID to wait for
            timeout_ms: The timeout in milliseconds (default: 5000)

        Returns:
            Dict containing the task status
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot wait for task.")
            return {"status": "error", "message": "Algolia not configured"}

        try:
            # Use the client's wait_for_task method with the index_name parameter
            response = self.client.wait_for_task(
                index_name=index_name,
                task_id=task_id,
                request_options={"timeoutMs": timeout_ms},
            )
            return response.body
        except Exception as e:
            logger.error(
                f"Failed to wait for task {task_id} on index {index_name}: {str(e)}"
            )
            return {"status": "error", "message": str(e)}

    def search(
        self,
        index_name: str,
        query: str,
        search_params: Optional[Dict[str, Any]] = None,
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Search for objects in the specified index

        Args:
            index_name: The name of the index
            query: The search query string
            search_params: Additional search parameters (filters, pagination, etc.)
            request_options: Additional request options

        Returns:
            Dict containing search results or error information
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot perform search.")
            return {"status": "error", "message": "Algolia not configured"}

        try:
            response = self.client.search(
                index_name=index_name,
                query=query,
                search_params=search_params,
                request_options=request_options,
            )
            return {"status": "success", "results": response}
        except Exception as e:
            logger.error(f"Failed to search objects: {str(e)}")
            return {"status": "error", "message": str(e)}

    def multi_search(self, queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Perform multiple searches with one API call

        Args:
            queries: List of search queries. Each query should be a dict with:
                - indexName: The index name to search in
                - query: The search query
                - Optional params like hitsPerPage, filters, etc.

        Returns:
            Dict containing the search results
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Search functionality is limited.")
            return {"results": [{"hits": []} for _ in queries]}

        try:
            # Format the requests for the multi_search method
            search_params = {"requests": queries}

            # Execute the search
            response = self.client.search(search_params)
            return {"results": response.results}
        except Exception as e:
            logger.error(f"Multi-search failed: {str(e)}")
            return {"results": [{"hits": []} for _ in queries]}

    def update_object(
        self,
        index_name: str,
        obj: Dict[str, Any],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update an object in the specified index (replaces the entire object)

        Args:
            index_name: The name of the index
            obj: The object to update (must include an objectID)
            request_options: Additional request options

        Returns:
            Dict containing the result of the operation
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot update object.")
            return {"status": "error", "message": "Algolia not configured"}

        if "objectID" not in obj:
            logger.error("objectID is required for update_object")
            return {"status": "error", "message": "objectID is required"}

        try:
            response = self.client.replace_all_objects(
                index_name=index_name, objects=[obj], request_options=request_options
            )
            return response.raw_responses[0]
        except Exception as e:
            logger.error(f"Failed to update object: {str(e)}")
            return {"status": "error", "message": str(e)}

    def update_objects(
        self,
        index_name: str,
        objects: List[Dict[str, Any]],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update multiple objects in the specified index (replaces entire objects)

        Args:
            index_name: The name of the index
            objects: List of objects to update (each must include an objectID)
            request_options: Additional request options

        Returns:
            Dict containing the result of the operation
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot update objects.")
            return {"status": "error", "message": "Algolia not configured"}

        # Check if all objects have objectID
        missing_ids = [i for i, obj in enumerate(objects) if "objectID" not in obj]
        if missing_ids:
            logger.error(f"Objects at indices {missing_ids} are missing objectID")
            return {
                "status": "error",
                "message": f"Objects at indices {missing_ids} are missing objectID",
            }

        try:
            response = self.client.replace_all_objects(
                index_name=index_name, objects=objects, request_options=request_options
            )
            return response.raw_responses[0]
        except Exception as e:
            logger.error(f"Failed to update objects: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_object(
        self,
        index_name: str,
        object_id: str,
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get an object from the specified index by its ID

        Args:
            index_name: The name of the index
            object_id: The ID of the object to retrieve
            request_options: Additional request options

        Returns:
            Dict containing the object or error information
        """
        if not self.is_configured():
            logger.warning("Algolia not configured. Cannot get object.")
            return {"status": "error", "message": "Algolia not configured"}

        try:
            response = self.client.get_objects(
                index_name=index_name,
                object_ids=[object_id],
                request_options=request_options,
            )
            if (
                response
                and response.get("results")
                and len(response.get("results", [])) > 0
            ):
                return {"status": "success", "object": response["results"][0]}
            return {"status": "error", "message": "Object not found"}
        except Exception as e:
            logger.error(f"Failed to get object: {str(e)}")
            return {"status": "error", "message": str(e)}


# Create singleton instance
algolia_config = AlgoliaConfig()
