# app/algolia/config.py
"""
Configuration for Algolia search integration
Handles initialization and configuration of Algolia client and indexes
"""
import os
from typing import Dict, List, Optional
from pydantic_settings import BaseSettings
from algoliasearch.search.client import SearchClient
from ..logger import logger


class AlgoliaSettings(BaseSettings):
    """Settings for Algolia search"""

    app_id: str
    api_key: str
    search_only_api_key: str
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
        self.tools_index_name = settings.tools_index_name
        self.glossary_index_name = settings.glossary_index_name

        # Initialize client only if credentials are provided
        self.client = None
        self.tools_index = None
        self.glossary_index = None

        if self.app_id and self.api_key:
            try:
                self.client = SearchClient.create(self.app_id, self.api_key)
                self.tools_index = self.client.init_index(self.tools_index_name)
                self.glossary_index = self.client.init_index(self.glossary_index_name)
                logger.info("Algolia client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Algolia client: {str(e)}")
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
            # Configure searchable attributes
            self.tools_index.set_settings(
                {
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
            # Configure searchable attributes
            self.glossary_index.set_settings(
                {
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
            )
            logger.info("Algolia glossary index configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure Algolia glossary index: {str(e)}")


# Create singleton instance
algolia_config = AlgoliaConfig()
