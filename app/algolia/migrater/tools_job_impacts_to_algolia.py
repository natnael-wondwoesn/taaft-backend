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
import argparse
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
mongodb_collection = "tools_Job_impacts"

# Function to parse command-line arguments
def parse_args(args_list=None):
    parser = argparse.ArgumentParser(description="Migrate job impacts from MongoDB to Algolia")
    parser.add_argument("--fix-record", type=str, help="Fix a specific record by ID")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--check-size", action="store_true", help="Check record sizes without uploading")
    return parser.parse_args(args_list)

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
        collection_name = "tools_Job_impacts"
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

    # Ensure the record size is within Algolia's limits (10KB)
    # Truncate large text fields if necessary
    import json
    
    # First attempt: Check if the record is already within size limits
    record_size = len(json.dumps(algolia_job_impact).encode('utf-8'))
    
    # If the record is too large, start truncating fields
    if record_size > 9500:  # Leave some buffer
        logger.warning(f"Record {algolia_job_impact['objectID']} is too large ({record_size} bytes). Truncating fields...")
        
        # Fields to truncate (in order of priority, least important first)
        fields_to_truncate = [
            # Long text fields that are less critical
            "detailed_analysis", 
            "ai_impact_summary", 
            "description",
            # Task details can be large
            "tasks"
        ]
        
        for field in fields_to_truncate:
            if field in algolia_job_impact:
                if field == "tasks" and algolia_job_impact.get(field):
                    # For tasks, keep only essential task information
                    simplified_tasks = []
                    for task in algolia_job_impact[field]:
                        simplified_task = {
                            "name": task.get("name", ""),
                            "impact": task.get("impact", "")
                        }
                        # Keep tool names but simplify tool objects
                        if "tools" in task and task["tools"]:
                            simplified_task["tools"] = [
                                {"tool_name": tool.get("tool_name", "")} 
                                for tool in task["tools"] if tool.get("tool_name")
                            ]
                        simplified_tasks.append(simplified_task)
                    algolia_job_impact[field] = simplified_tasks
                elif isinstance(algolia_job_impact[field], str):
                    # Truncate text fields
                    if len(algolia_job_impact[field]) > 1000:
                        algolia_job_impact[field] = algolia_job_impact[field][:1000] + "..."
                
                # Check if we're now under the limit
                record_size = len(json.dumps(algolia_job_impact).encode('utf-8'))
                if record_size <= 9500:
                    break
        
        # If still too large, remove non-essential fields
        if record_size > 9500:
            non_essential_fields = [
                "ai_generated_text", 
                "raw_data",
                "full_analysis", 
                "source_data",
                "gpt_response"
            ]
            
            for field in non_essential_fields:
                if field in algolia_job_impact:
                    del algolia_job_impact[field]
                    # Check if we're now under the limit
                    record_size = len(json.dumps(algolia_job_impact).encode('utf-8'))
                    if record_size <= 9500:
                        break
        
        # Final check - if still too large, keep only the most essential fields
        if record_size > 9500:
            logger.warning(f"Record {algolia_job_impact['objectID']} is still too large after truncation. Keeping only essential fields.")
            essential_fields = [
                "objectID", "job_title", "job_category", "industry",
                "ai_impact_score", "numeric_impact_score", "task_names", "tool_names",
                "keywords", "created_at", "updated_at"
            ]
            
            # Create a new record with only essential fields
            essential_record = {}
            for field in essential_fields:
                if field in algolia_job_impact:
                    essential_record[field] = algolia_job_impact[field]
            
            # Replace the record with the essential-only version
            algolia_job_impact = essential_record

    return algolia_job_impact


def configure_algolia_index(client, index_name):
    """Configure Algolia index settings for optimal job impact searching"""
    client.set_settings(
        index_name,
        {
            "searchableAttributes": [
                "job_title",
            ],
            "attributesForFaceting": [
                "searchable(job_title)",
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


def fix_record_by_id(mongo_collection, record_id):
    """
    Retrieve and fix a specific record by ID
    """
    from bson.objectid import ObjectId
    
    try:
        # Try to convert the string ID to ObjectId
        obj_id = None
        try:
            obj_id = ObjectId(record_id)
        except Exception:
            # If conversion fails, use the string ID as is
            pass
            
        # Try to find the record by ID
        record = None
        if obj_id:
            record = mongo_collection.find_one({"_id": obj_id})
        
        # If not found with ObjectId, try with string ID
        if not record:
            record = mongo_collection.find_one({"_id": record_id})
            
        if not record:
            logger.error(f"Record with ID {record_id} not found")
            return False
            
        # Prepare the record for Algolia
        algolia_record = prepare_algolia_object(record)
        
        # Get the size of the record
        import json
        record_size = len(json.dumps(algolia_record).encode('utf-8'))
        logger.info(f"Record {record_id} size: {record_size} bytes")
        
        if record_size > 10000:
            logger.warning(f"Record {record_id} is too large ({record_size} bytes)")
            logger.info("Fields and their sizes:")
            
            # Print fields and their sizes
            for key, value in algolia_record.items():
                field_size = len(json.dumps(value).encode('utf-8'))
                logger.info(f"  {key}: {field_size} bytes")
                
            # The prepare_algolia_object function should have already fixed the size issue
            algolia_client = get_algolia_client()
            
            # Upload the fixed record
            try:
                algolia_client.save_objects(algolia_index_name, [algolia_record])
                logger.info(f"Successfully uploaded fixed record {record_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to upload fixed record {record_id}: {str(e)}")
                return False
        else:
            logger.info(f"Record {record_id} is within size limits")
            algolia_client = get_algolia_client()
            
            # Upload the record
            try:
                algolia_client.save_objects(algolia_index_name, [algolia_record])
                logger.info(f"Successfully uploaded record {record_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to upload record {record_id}: {str(e)}")
                return False
    except Exception as e:
        logger.error(f"Error fixing record {record_id}: {str(e)}")
        return False


def check_record_sizes(mongodb_job_impacts):
    """Check the size of each record and report any that exceed Algolia's limit"""
    import json
    
    logger.info("Checking record sizes...")
    oversized_records = []
    
    for job_impact in mongodb_job_impacts:
        # Prepare the record for Algolia
        algolia_record = prepare_algolia_object(job_impact)
        
        # Get the size of the record
        record_size = len(json.dumps(algolia_record).encode('utf-8'))
        
        # If the record is too large, add it to the list
        if record_size > 10000:
            record_id = str(job_impact.get("_id"))
            oversized_records.append({
                "id": record_id,
                "size": record_size,
                "job_title": job_impact.get("job_title", "Unknown")
            })
            
    # Report the results
    if oversized_records:
        logger.warning(f"Found {len(oversized_records)} oversized records:")
        for record in oversized_records:
            logger.warning(f"  {record['id']}: {record['size']} bytes - {record['job_title']}")
    else:
        logger.info("All records are within Algolia's size limits")
        
    return oversized_records
        

def main(cli_args=None):
    """Main function to orchestrate the migration process"""
    args = parse_args(cli_args)
    
    try:
        # Get MongoDB connection for specific record fix if needed
        if args.fix_record or args.check_size:
            # Create MongoDB client
            mongo_client = MongoClient(mongodb_url)
            mongo_database = mongo_client[mongodb_db]
            mongo_collection = mongo_database[mongodb_collection]
            
            # If fixing a specific record
            if args.fix_record:
                logger.info(f"Fixing record with ID {args.fix_record}...")
                success = fix_record_by_id(mongo_collection, args.fix_record)
                return {
                    "status": "success" if success else "error",
                    "message": f"Record fix {'succeeded' if success else 'failed'}"
                }
                
            # If checking record sizes
            if args.check_size:
                mongodb_job_impacts = get_mongodb_job_impacts()
                oversized_records = check_record_sizes(mongodb_job_impacts)
                return {
                    "status": "success",
                    "message": f"Found {len(oversized_records)} oversized records" if oversized_records else "All records are within size limits",
                    "oversized_count": len(oversized_records)
                }
        
        # Regular migration process
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
            # Use a smaller batch size to avoid size limit issues
            batch_size = 50  # Reduced from 1000
            failed_records = []
            success_count = 0
            
            for i in range(0, len(algolia_objects), batch_size):
                batch = algolia_objects[i : i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(algolia_objects) + batch_size - 1) // batch_size
                
                logger.info(f"Uploading batch {batch_num} of {total_batches}...")
                
                try:
                    algolia_client.save_objects(algolia_index_name, batch)
                    success_count += len(batch)
                    logger.info(f"Successfully uploaded batch {batch_num} ({len(batch)} records)")
                except Exception as e:
                    logger.error(f"Error uploading batch {batch_num}: {str(e)}")
                    
                    # If batch fails, try uploading records individually
                    if len(batch) > 1:
                        logger.info("Attempting to upload records individually...")
                        for record in batch:
                            try:
                                algolia_client.save_objects(algolia_index_name, [record])
                                success_count += 1
                            except Exception as individual_error:
                                logger.error(f"Failed to upload record {record.get('objectID')}: {str(individual_error)}")
                                failed_records.append({
                                    "objectID": record.get("objectID"),
                                    "error": str(individual_error)
                                })
            
            # Report results
            if failed_records:
                logger.warning(f"Migration completed with {len(failed_records)} failed records out of {len(algolia_objects)}")
                logger.warning(f"Failed record IDs: {', '.join([r['objectID'] for r in failed_records[:10]])}")
                if len(failed_records) > 10:
                    logger.warning(f"... and {len(failed_records) - 10} more")
            else:
                logger.info(f"All {success_count} records successfully uploaded to Algolia")
        else:
            logger.info("No objects to upload. Created an empty index.")

        logger.info("Migration completed!")
        return {
            "status": "success", 
            "message": "Migration completed successfully",
            "total_records": len(algolia_objects) if algolia_objects else 0,
            "successful_records": success_count if algolia_objects else 0,
            "failed_records": len(failed_records) if algolia_objects else 0
        }

    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        # Print full exception details for debugging
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return {"status": "error", "message": f"Migration failed: {str(e)}"}


if __name__ == "__main__":
    main()
