#!/usr/bin/env python3
"""
Script to calculate and save tool counts for all job impacts in the database.
This script is meant to be run as a batch job to pre-calculate tool counts
and save them to the database for efficient retrieval.
"""

import os
import sys
import asyncio
from datetime import datetime
import logging
import ssl
from typing import List, Dict, Any, Optional, Set, Tuple

# Add the parent directory to sys.path to be able to import app modules
# When run in the container, we're in the /app directory
# When run locally, we need to add the parent directory
script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(script_dir, "../..")):
    sys.path.append(os.path.abspath(os.path.join(script_dir, "../..")))

try:
    from app.models.job_impact import JobImpactInDB
    from app.models.job_impact_tool_count import JobImpactToolCountInDB  
    from app.database import database
    from app.services.job_impacts_service import (
        save_job_impact_tool_count,
        get_job_impact_tool_count
    )
    from motor.motor_asyncio import AsyncIOMotorCollection
except ImportError:
    print("Failed to import modules with standard paths, trying container paths...")
    # Try importing with container paths
    from models.job_impact import JobImpactInDB
    from models.job_impact_tool_count import JobImpactToolCountInDB  
    from database import database
    from services.job_impacts_service import (
        save_job_impact_tool_count,
        get_job_impact_tool_count
    )
    from motor.motor_asyncio import AsyncIOMotorCollection

# Configure logging
log_file = os.path.join(os.path.dirname(__file__), "job_impact_tool_counts.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Default minimum tool count to prevent zero results
DEFAULT_MIN_TOOL_COUNT = 5

async def get_all_job_impacts() -> List[JobImpactInDB]:
    """
    Get all job impacts from the database.
    """
    logger.info("Getting all job impacts from database")
    cursor = database[JobImpactInDB.collection_name].find({})
    results = await cursor.to_list(length=None)  # Get all results
    
    job_impacts = []
    for doc in results:
        try:
            job_impact = JobImpactInDB(**doc)
            job_impacts.append(job_impact)
        except Exception as e:
            logger.error(f"Error processing job impact {doc.get('_id')}: {str(e)}")
    
    logger.info(f"Found {len(job_impacts)} job impacts")
    return job_impacts

async def get_task_tools_count(task_name: str, tools_collection: AsyncIOMotorCollection) -> int:
    """
    Get the count of tools associated with a task directly from the database.
    More efficient than making HTTP requests.
    
    Args:
        task_name: The name of the task
        tools_collection: The MongoDB collection containing the tools
        
    Returns:
        int: The number of tools for the task
    """
    count = await tools_collection.count_documents({"related_tasks": {"$elemMatch": {"name": task_name}}})
    logger.debug(f"Found {count} tools for task: {task_name}")
    return count

async def get_tools_collection() -> AsyncIOMotorCollection:
    """
    Get the tools collection from the database.
    """
    return database["tools"]

async def calculate_job_impact_tool_count_efficient(
    job_impact: JobImpactInDB,
    tools_collection: AsyncIOMotorCollection
) -> Tuple[int, Dict[str, int]]:
    """
    Calculate the total tool count for a job impact more efficiently
    by directly querying the database.
    
    Args:
        job_impact: The job impact to calculate the tool count for
        tools_collection: The MongoDB collection containing the tools
        
    Returns:
        Tuple[int, Dict[str, int]]: Total tool count and count by task
    """
    logger.info(f"Calculating tool count for job impact: {job_impact.job_title}")
    
    if not job_impact.tasks:
        logger.warning(f"No tasks found for job impact: {job_impact.job_title}")
        return DEFAULT_MIN_TOOL_COUNT, {"default": DEFAULT_MIN_TOOL_COUNT}
    
    # Get unique task names to prevent duplicate counting
    tasks = set(task.name for task in job_impact.tasks if task.name)
    
    if not tasks:
        logger.warning(f"No task names found for job impact: {job_impact.job_title}")
        return DEFAULT_MIN_TOOL_COUNT, {"default": DEFAULT_MIN_TOOL_COUNT}
    
    logger.debug(f"Processing {len(tasks)} unique tasks for {job_impact.job_title}")
    
    # Get task counts in parallel
    tasks_count = {}
    counts = await asyncio.gather(*[
        get_task_tools_count(task_name, tools_collection) 
        for task_name in tasks
    ])
    
    # Map tasks to their counts
    for task_name, count in zip(tasks, counts):
        tasks_count[task_name] = count
    
    # Calculate total, handle cases with no tools
    total_count = sum(tasks_count.values())
    
    # If total count is zero, use default minimum
    if total_count == 0:
        logger.warning(f"No tools found for any tasks in {job_impact.job_title}, using default minimum")
        total_count = DEFAULT_MIN_TOOL_COUNT
        tasks_count = {"default": DEFAULT_MIN_TOOL_COUNT}
    
    logger.info(f"Calculated total tool count for {job_impact.job_title}: {total_count}")
    return total_count, tasks_count

async def process_job_impact(
    job_impact: JobImpactInDB, 
    tools_collection: AsyncIOMotorCollection,
    force_update: bool = False
) -> Dict[str, Any]:
    """
    Process a single job impact: calculate its tool count and save to database.
    Returns statistics about the processing.
    """
    job_title = job_impact.job_title
    
    # Check if tool count already exists
    existing_count = await get_job_impact_tool_count(job_title)
    
    if existing_count and not force_update:
        logger.info(f"Tool count for '{job_title}' already exists: {existing_count.total_tool_count}")
        return {
            "job_title": job_title,
            "tool_count": existing_count.total_tool_count,
            "status": "skipped",
            "reason": "already exists"
        }
    
    try:
        # Calculate tool count efficiently
        tool_count, task_counts = await calculate_job_impact_tool_count_efficient(
            job_impact, tools_collection
        )
        
        # Save to database with task counts
        try:
            await save_job_impact_tool_count(job_title, tool_count)
            
            # Store task counts in a separate collection
            await database["job_impact_task_counts"].update_one(
                {"job_impact_name": job_title},
                {"$set": {
                    "job_impact_name": job_title,
                    "task_counts": task_counts,
                    "updated_at": datetime.utcnow()
                }},
                upsert=True
            )
            logger.info(f"Saved task counts for {job_title} ({len(task_counts)} tasks)")
        except Exception as e:
            logger.error(f"Error saving task counts for {job_title}: {str(e)}")
        
        return {
            "job_title": job_title,
            "tool_count": tool_count,
            "task_counts": task_counts,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error processing job impact '{job_title}': {str(e)}")
        return {
            "job_title": job_title,
            "status": "error",
            "error": str(e)
        }

async def main():
    """
    Main function to calculate and save tool counts for all job impacts.
    """
    start_time = datetime.now()
    logger.info(f"Starting job impact tool count calculation at {start_time}")
    
    global DEFAULT_MIN_TOOL_COUNT
    
    # Get configuration from environment or use defaults
    force_update = os.environ.get("FORCE_UPDATE", "false").lower() == "true"
    min_tool_count = int(os.environ.get("MIN_TOOL_COUNT", str(DEFAULT_MIN_TOOL_COUNT)))
    batch_size = int(os.environ.get("BATCH_SIZE", "50"))
    
    logger.info(f"Force update: {force_update}")
    logger.info(f"Minimum tool count: {min_tool_count}")
    logger.info(f"Batch size: {batch_size}")
    
    # Adjust default minimum tool count if specified
    DEFAULT_MIN_TOOL_COUNT = min_tool_count
    
    # Get all job impacts
    job_impacts = await get_all_job_impacts()
    
    # Get tools collection for direct access
    tools_collection = await get_tools_collection()
    
    # Process job impacts in batches
    results = []
    total_job_impacts = len(job_impacts)
    
    # Process in batches to avoid overwhelming the system
    for i in range(0, total_job_impacts, batch_size):
        batch = job_impacts[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total_job_impacts + batch_size - 1) // batch_size
        
        logger.info(f"Processing batch {batch_num}/{total_batches} with {len(batch)} job impacts")
        
        # Process this batch concurrently
        batch_results = await asyncio.gather(*[
            process_job_impact(job_impact, tools_collection, force_update)
            for job_impact in batch
        ])
        
        results.extend(batch_results)
        
        logger.info(f"Completed batch {batch_num}/{total_batches}")
        
        # Brief pause between batches to avoid overwhelming the database
        if batch_num < total_batches:
            await asyncio.sleep(1.0)
    
    # Log statistics
    success_count = sum(1 for r in results if r.get("status") == "success")
    error_count = sum(1 for r in results if r.get("status") == "error")
    skipped_count = sum(1 for r in results if r.get("status") == "skipped")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info(f"Finished job impact tool count calculation at {end_time}")
    logger.info(f"Duration: {duration:.2f} seconds")
    logger.info(f"Total job impacts: {len(job_impacts)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Errors: {error_count}")
    logger.info(f"Skipped: {skipped_count}")
    
    # Return exit code based on success
    return 0 if error_count == 0 else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)