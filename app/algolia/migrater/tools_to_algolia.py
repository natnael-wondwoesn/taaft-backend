#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MongoDB Tools to Algolia Migration Script

This script is used to:
1. Connect to Algolia using the Algolia Python API and validate the connection
2. Connect to the MongoDB instance and retrieve tools collection data
3. Prepare the Algolia index with appropriate configuration
4. Load the tools dataset into Algolia and replace the existing index

Prerequisites:
- algoliasearch>=4.0.0
- pymongo
- python-dotenv
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from algoliasearch.search.client import SearchClientSync as SearchClient
from pymongo import MongoClient
from ...logger import logger

# Load environment variables
load_dotenv()

# Define the Algolia connection parameters
algolia_app_id = os.getenv("ALGOLIA_APP_ID")
algolia_admin_key = os.getenv("ALGOLIA_ADMIN_KEY")
algolia_index_name = os.getenv("ALGOLIA_TOOLS_INDEX", "tools_index")

# MongoDB connection parameters
mongodb_url = os.getenv("MONGODB_URL")
mongodb_db = os.getenv("MONGODB_DB", "taaft_db")
mongodb_collection = "tools"


# Initialize Algolia client (only when needed)
def get_algolia_client():
    # Validate required environment variables
    if not all([algolia_app_id, algolia_admin_key, mongodb_url]):
        raise ValueError(
            "Missing required environment variables. Please check your .env file.\n"
            "Required: ALGOLIA_APP_ID, ALGOLIA_ADMIN_KEY, MONGODB_URL"
        )

    # Initialize and return client
    return SearchClient(algolia_app_id, algolia_admin_key)


def test_algolia_index(client, index_name):
    """Test the Algolia index connection and functionality"""
    # Clear the index, in case it contains any records
    client.clear_objects(index_name)

    # Create a sample record
    record = {"object_id": "test", "name": "test_tool"}

    # Save it to the index
    client.save_objects(index_name, [record])

    # Search the index for 'test_tool'
    search_response = client.search_single_index(index_name)

    # Clear all items again to clear our test record
    # client.clear_objects(index_name)

    logger.info(f"search_response: {search_response}")

    # Verify the search response has hits
    # In v4, the response might be an object with attributes instead of a dict
    try:
        # Try accessing as attributes first
        hits = search_response.hits if hasattr(search_response, "hits") else []
        if len(hits) == 1:
            logger.info(f"hits: {hits}")
            logger.info("Algolia index test successful")
            return
    except Exception:
        pass

    try:
        # Try accessing as dictionary
        hits = (
            search_response.get("hits", []) if hasattr(search_response, "get") else []
        )
        if len(hits) == 1 and hits[0].get("object_id"):
            logger.info("Algolia index test successful")
            return
    except Exception:
        pass

    try:
        # Last attempt - treat as dictionary directly
        hits = search_response["hits"] if "hits" in search_response else []
        if len(hits) == 1 and hits[0]["object_id"]:
            logger.info("Algolia index test successful")
            return
    except Exception:
        pass

    # If we got here, none of the methods worked
    raise Exception("Algolia test failed: Unable to access search results correctly")


# Connect to MongoDB and get the tools collection
def get_mongodb_tools():
    """Connect to MongoDB and retrieve tools collection data"""
    try:
        # Create MongoDB client
        mongo_client = MongoClient(mongodb_url)
        # Get database instance
        mongo_database = mongo_client[mongodb_db]
        # Get collection instance
        mongo_collection = mongo_database[mongodb_collection]

        # Retrieve all tools from collection
        tools_cursor = mongo_collection.find({})
        tools = list(tools_cursor)

        logger.info(f"Retrieved {len(tools)} tools from MongoDB")
        return tools
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {str(e)}")
        raise


def prepare_algolia_object(mongo_tool):
    """Transform MongoDB tool object to Algolia-friendly format"""
    # Create an instance of the Algolia object
    algolia_tool = {}

    # Use unique_id or _id as Algolia objectID
    algolia_tool["objectID"] = str(mongo_tool.get("id") or mongo_tool.get("_id"))

    # Include essential tool attributes
    attributes_to_include = [
        "price",
        "name",
        "description",
        "link",
        "unique_id",
        "rating",
        "saved_numbers",
        "category",
        "features",
        "is_featured",
        "keywords",
        "categories",
        "logo_url",
        "user_reviews",
        "feature_list",
        "referral_allow",
        "generated_description",
        "industry",
        "carriers",
    ]

    for attr in attributes_to_include:
        if attr in mongo_tool:
            # Convert datetime objects to ISO format strings
            if isinstance(mongo_tool[attr], datetime):
                algolia_tool[attr] = mongo_tool[attr].isoformat()
            else:
                algolia_tool[attr] = mongo_tool[attr]

    # Add searchable logo URL if available
    if "logo_url" in mongo_tool:
        algolia_tool["logo_url"] = mongo_tool["logo_url"]

    # Process keywords if they exist, otherwise generate them from tags or category
    if "keywords" in mongo_tool and mongo_tool["keywords"]:
        algolia_tool["keywords"] = mongo_tool["keywords"]
    else:
        # Generate keywords from tags, features, and category
        keywords = []

        # Add tags as keywords if available
        if "tags" in mongo_tool and mongo_tool["tags"]:
            keywords.extend(mongo_tool["tags"])

        # Add category as keyword if available
        if "category" in mongo_tool and mongo_tool["category"]:
            category = mongo_tool["category"]
            if isinstance(category, str):
                keywords.append(category)

        # Add features as keywords if available
        if "features" in mongo_tool and mongo_tool["features"]:
            # Extract main keywords from features (first word of each feature)
            for feature in mongo_tool["features"]:
                if isinstance(feature, str):
                    feature_words = feature.split()
                    if feature_words:
                        keywords.append(feature_words[0].lower())

        # Remove duplicates and assign to algolia_tool
        if keywords:
            algolia_tool["keywords"] = list(set(keywords))

    return algolia_tool


def configure_algolia_index(client, index_name):
    """Configure Algolia index settings for optimal tool searching"""
    client.set_settings(
        index_name,
        {
            "searchableAttributes": [
                "name",
                "description",
                "keywords",
                "carriers",
                "industry",
            ],
            "attributesForFaceting": [
                "category",
                "keywords",
                "unique_id",
                "description",
                "name",
                "features_list",
            ],
            "attributesToRetrieve": [
                "name",
                "description",
                "summary",
                "url",
                "logo_url",
                "category",
                "features",
                "pricing_type",
                "pricing_url",
                "is_featured",
                "created_at",
                "updated_at",
                "tags",
                "price",
                "is_featured",
                "rating",
                "saved_numbers",
                "keywords",
                "industry",
                "referral_allow",
                "feature_list",
                "generated_description",
                "user_reviews",
                "categories",
                "logo_url",
                "created_at",
                "updated_at",
                "tags",
                "price",
                "is_featured",
                "rating",
                "saved_numbers",
                "carriers",
            ],
            "ranking": [
                "typo",
                "geo",
                "words",
                "filters",
                "proximity",
                "attribute",
                "exact",
                "custom",
            ],
            "customRanking": ["desc(is_featured)", "desc(updated_at)"],
            "ignorePlurals": True,
            "advancedSyntax": True,
            "typoTolerance": "strict",
        },
    )
    logger.info("Algolia index configured successfully")


def main():
    """Main function to orchestrate the migration process"""
    try:
        # Get the Algolia client (this will validate environment variables)
        algolia_client = get_algolia_client()

        # Step 1: Test Algolia connection
        logger.info("Testing Algolia connection...")
        test_algolia_index(algolia_client, algolia_index_name)

        # Step 2: Retrieve tools from MongoDB
        logger.info("Retrieving tools from MongoDB...")
        mongodb_tools = get_mongodb_tools()

        # Step 3: Configure Algolia index
        logger.info("Configuring Algolia index...")
        configure_algolia_index(algolia_client, algolia_index_name)

        # Step 4: Prepare and upload tools to Algolia
        logger.info("Preparing tools for Algolia...")
        algolia_objects = list(map(prepare_algolia_object, mongodb_tools))

        logger.info(f"Uploading {len(algolia_objects)} tools to Algolia...")
        # Clear the index first to remove any outdated objects
        algolia_client.clear_objects(algolia_index_name)

        # Split into batches of 1000 records to avoid size limits
        batch_size = 1000
        for i in range(0, len(algolia_objects), batch_size):
            batch = algolia_objects[i : i + batch_size]
            logger.info(
                f"Uploading batch {i//batch_size + 1} of {(len(algolia_objects) + batch_size - 1) // batch_size}..."
            )
            algolia_client.save_objects(algolia_index_name, batch)

        logger.info("Migration completed successfully!")
        return {"status": "success", "message": "Migration completed successfully"}

    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        return {"status": "error", "message": f"Migration failed: {str(e)}"}


if __name__ == "__main__":
    main()
