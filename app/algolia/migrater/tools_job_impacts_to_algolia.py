#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MongoDB Tools Job Impacts to Algolia Migration Script

This script is used to:
1. Connect to Algolia using the Algolia Python API and validate the connection
2. Connect to the MongoDB instance and retrieve tools_job_impacts collection data
3. Prepare the Algolia index with appropriate configuration
4. Load the tools job impacts dataset into Algolia and replace the existing index

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
algolia_index_name = os.getenv(
    "ALGOLIA_TOOLS_JOB_IMPACTS_INDEX", "tools_job_impacts_index"
)

# MongoDB connection parameters
mongodb_url = os.getenv("MONGODB_URL")
mongodb_db = os.getenv("MONGODB_DB", "taaft_db")
mongodb_collection = "tools_job_impacts"


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
    record = {"object_id": "test", "name": "test_job_impact"}

    # Save it to the index
    client.save_objects(index_name, [record])

    # Search the index for 'test_job_impact'
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


# Connect to MongoDB and get the tools_job_impacts collection
def get_mongodb_job_impacts():
    """Connect to MongoDB and retrieve tools_job_impacts collection data"""
    try:
        # Create MongoDB client
        mongo_client = MongoClient(mongodb_url)

        # Get database instance
        mongo_database = mongo_client[mongodb_db]

        # List all collections to debug
        collection_names = mongo_database.list_collection_names()
        logger.info(f"Available collections in database: {collection_names}")

        # Get collection instance - ensure it's using the right name
        collection_name = "tools_job_impacts"
        if collection_name not in collection_names:
            # Try alternative collection names that might contain job impacts
            possible_alternatives = [
                name
                for name in collection_names
                if "job" in name.lower() or "impact" in name.lower()
            ]
            if possible_alternatives:
                collection_name = possible_alternatives[0]
                logger.warning(
                    f"Collection 'tools_job_impacts' not found, using '{collection_name}' instead"
                )
            else:
                logger.error(
                    f"Could not find tools_job_impacts collection or any alternatives"
                )
                raise ValueError("tools_job_impacts collection not found in database")

        mongo_collection = mongo_database[collection_name]

        # Retrieve all job impacts from collection with debug count
        count = mongo_collection.count_documents({})
        logger.info(f"Found {count} documents in the {collection_name} collection")

        if count == 0:
            # Try to retrieve at least one document to see structure
            sample_doc = mongo_collection.find_one({})
            if sample_doc:
                logger.info(f"Sample document structure: {list(sample_doc.keys())}")
            else:
                logger.warning("Collection exists but is empty")

        # Retrieve all job impacts from collection
        job_impacts_cursor = mongo_collection.find({})
        job_impacts = list(job_impacts_cursor)

        if not job_impacts:
            logger.warning(
                "No job impacts found in MongoDB. The collection may be empty."
            )
            # Return empty list so the rest of the process can continue
            return []

        logger.info(f"Retrieved {len(job_impacts)} job impacts from MongoDB")
        return job_impacts
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {str(e)}")
        # Print full exception details for debugging
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


def prepare_algolia_object(mongo_job_impact):
    """Transform MongoDB job impact object to Algolia-friendly format"""
    # Create an instance of the Algolia object
    algolia_job_impact = {}

    # Use unique_id or _id as Algolia objectID
    algolia_job_impact["objectID"] = str(
        mongo_job_impact.get("id") or mongo_job_impact.get("_id")
    )

    # Copy all fields from the original document
    for key, value in mongo_job_impact.items():
        # Skip _id as we've already handled it
        if key == "_id":
            continue

        # Convert datetime objects to ISO format strings
        if isinstance(value, datetime):
            algolia_job_impact[key] = value.isoformat()
        else:
            algolia_job_impact[key] = value

    # Add special field for filtering by task names
    if "tasks" in mongo_job_impact and mongo_job_impact["tasks"]:
        # Extract task names for faceting
        task_names = [
            task.get("name") for task in mongo_job_impact["tasks"] if task.get("name")
        ]
        if task_names:
            algolia_job_impact["task_names"] = task_names

        # Extract tool names for faceting
        tool_names = []
        for task in mongo_job_impact["tasks"]:
            if "tools" in task and task["tools"]:
                for tool in task["tools"]:
                    if tool.get("tool_name"):
                        tool_names.append(tool.get("tool_name"))
        if tool_names:
            algolia_job_impact["tool_names"] = tool_names

    # Process AI impact score for sorting
    if "ai_impact_score" in mongo_job_impact:
        score = mongo_job_impact["ai_impact_score"]
        if isinstance(score, str) and "%" in score:
            # Convert percentage string to numeric value for sorting
            try:
                algolia_job_impact["numeric_impact_score"] = float(
                    score.replace("%", "")
                )
            except ValueError:
                # Keep original if conversion fails
                pass

    # Process keywords if they exist
    if "keywords" in mongo_job_impact and mongo_job_impact["keywords"]:
        algolia_job_impact["keywords"] = mongo_job_impact["keywords"]
    else:
        # Generate keywords from job_title, job_category, and industry
        keywords = []

        # Add job_title as keyword if available
        if "job_title" in mongo_job_impact and mongo_job_impact["job_title"]:
            job_title = mongo_job_impact["job_title"]
            if isinstance(job_title, str):
                keywords.extend(job_title.lower().split())

        # Add job_category as keyword if available
        if "job_category" in mongo_job_impact and mongo_job_impact["job_category"]:
            job_category = mongo_job_impact["job_category"]
            if isinstance(job_category, str):
                keywords.append(job_category.lower())

        # Add industry as keyword if available
        if "industry" in mongo_job_impact and mongo_job_impact["industry"]:
            industry = mongo_job_impact["industry"]
            if isinstance(industry, str):
                keywords.append(industry.lower())

        # Add task names as keywords
        if "tasks" in mongo_job_impact and mongo_job_impact["tasks"]:
            for task in mongo_job_impact["tasks"]:
                if task.get("name"):
                    task_name = task["name"].lower()
                    keywords.append(task_name)

        # Remove duplicates and assign to algolia_job_impact
        if keywords:
            algolia_job_impact["keywords"] = list(set(keywords))

    return algolia_job_impact


def configure_algolia_index(client, index_name):
    """Configure Algolia index settings for optimal job impact searching"""
    client.set_settings(
        index_name,
        {
            "searchableAttributes": [
                "job_title",
                "description",
                "ai_impact_summary",
                "detailed_analysis",
                "job_category",
                "tasks.name",
                "tasks.tools.tool_name",
                "keywords",
            ],
            "attributesForFaceting": [
                "searchable(job_title)",
                "searchable(job_category)",
                "searchable(task_names)",
                "searchable(tool_names)",
                "numeric_impact_score",
                "ai_impact_score",
            ],
            "attributesToRetrieve": [
                "objectID",
                "job_title",
                "description",
                "ai_impact_score",
                "ai_impact_summary",
                "detailed_analysis",
                "job_category",
                "tasks",
                "task_names",
                "tool_names",
                "keywords",
                "created_at",
                "updated_at",
                "detail_page_link",
            ],
            "attributesToHighlight": [
                "job_title",
                "description",
                "ai_impact_summary",
                "job_category",
                "tasks.name",
                "tasks.tools.tool_name",
            ],
            "ranking": [
                "words",
                "typo",
                "filters",
                "proximity",
                "attribute",
                "exact",
                "custom",
            ],
            "customRanking": [
                "desc(numeric_impact_score)",
                "desc(created_at)",
            ],
            "ignorePlurals": True,
            "advancedSyntax": True,
            "typoTolerance": True,
            "distinct": True,
            "attributeForDistinct": "job_title",
            "minWordSizefor1Typo": 4,
            "minWordSizefor2Typos": 8,
            "allowTyposOnNumericTokens": False,
            "numericAttributesForFiltering": ["numeric_impact_score"],
            "unretrievableAttributes": [],
            "disableTypoToleranceOnAttributes": [],
            "paginationLimitedTo": 1000,
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

        # Step 2: Retrieve job impacts from MongoDB
        logger.info("Retrieving job impacts from MongoDB...")
        mongodb_job_impacts = get_mongodb_job_impacts()

        if not mongodb_job_impacts:
            logger.warning(
                "No job impact data found in MongoDB. Migration will create an empty index."
            )
            # Continue with empty data - it will just create an empty index

        # Step 3: Configure Algolia index
        logger.info("Configuring Algolia index...")
        configure_algolia_index(algolia_client, algolia_index_name)

        # Step 4: Prepare and upload job impacts to Algolia
        logger.info("Preparing job impacts for Algolia...")
        algolia_objects = list(map(prepare_algolia_object, mongodb_job_impacts))

        logger.info(f"Uploading {len(algolia_objects)} job impacts to Algolia...")
        # Clear the index first to remove any outdated objects
        algolia_client.clear_objects(algolia_index_name)

        # Only proceed with upload if we have objects
        if algolia_objects:
            # Split into batches of 1000 records to avoid size limits
            batch_size = 1000
            for i in range(0, len(algolia_objects), batch_size):
                batch = algolia_objects[i : i + batch_size]
                logger.info(
                    f"Uploading batch {i//batch_size + 1} of {(len(algolia_objects) + batch_size - 1) // batch_size}..."
                )
                algolia_client.save_objects(algolia_index_name, batch)
        else:
            logger.info("No objects to upload. Created an empty index.")

        logger.info("Migration completed successfully!")
        return {"status": "success", "message": "Migration completed successfully"}

    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        # Print full exception details for debugging
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return {"status": "error", "message": f"Migration failed: {str(e)}"}


if __name__ == "__main__":
    main()
