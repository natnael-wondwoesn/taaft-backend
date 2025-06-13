from fastapi import HTTPException
from typing import Optional, Dict, Any, List, Tuple
import httpx
import urllib.parse
import asyncio
from ..models.job_impact import JobImpactInDB
from ..models.job_impact_tool_count import JobImpactToolCountInDB
from ..database import database
from .redis_cache import redis_cache, redis_client, REDIS_CACHE_ENABLED
from ..logger import logger

async def get_job_impact_by_title(job_title: str) -> Optional[JobImpactInDB]:
    """Get a job impact by exact job title"""
    result = await database[JobImpactInDB.collection_name].find_one({"job_title": job_title})
    if result:
        return JobImpactInDB(**result)
    return None

async def fetch_task_tools(client: httpx.AsyncClient, task_name: str, base_url: str) -> int:
    """
    Fetch tools for a specific task and return the count
    
    Args:
        client: HTTP client to use for the request
        task_name: Name of the task to fetch tools for
        base_url: Base URL for the API
        
    Returns:
        Number of tools for the task
    """
    try:
        encoded_task_name = urllib.parse.quote(task_name)
        request_url = f"{base_url}/api/search/task-tools/{encoded_task_name}"
        
        response = await client.get(request_url, timeout=10.0)
        
        if response.status_code == 200:
            task_tools_data = response.json()
            if "tools" in task_tools_data and isinstance(task_tools_data["tools"], list):
                return len(task_tools_data["tools"])
            elif isinstance(task_tools_data, list):
                return len(task_tools_data)
            elif "total" in task_tools_data:
                return task_tools_data["total"]
        return 0
    except Exception as e:
        logger.error(f"Error fetching tools for task {task_name}: {str(e)}")
        return 0

async def calculate_job_impact_tool_count(job_title: str, base_url: str) -> int:
    """
    Calculate the total tool count for a given job impact without saving it.
    This is used by the batch script to calculate all job impact tool counts.
    
    Returns:
        int: Total tool count for the job impact
    """
    logger.info(f"Calculating tool count for job impact: {job_title}")
    
    # Get the job impact details by job title
    job = await get_job_impact_by_title(job_title)
    if not job:
        logger.error(f"Job impact not found: {job_title}")
        return 0

    # If using http, switch to https
    if base_url.startswith('http:'):
        base_url = 'https:' + base_url[5:]
        
    logger.debug(f"Using base URL: {base_url}")

    # Calculate the total tool count for all tasks in the job
    total_tool_count = 0
    async with httpx.AsyncClient(follow_redirects=True) as client:
        fetch_tasks = []
        for task in job.tasks:
            if task.name:
                fetch_tasks.append(fetch_task_tools(client, task.name, base_url))
        
        if fetch_tasks:
            logger.debug(f"Fetching tool counts for {len(fetch_tasks)} tasks in job: {job_title}")
            tool_counts = await asyncio.gather(*fetch_tasks)
            total_tool_count = sum(tool_counts)
            logger.info(f"Calculated total tool count for {job_title}: {total_tool_count}")
        else:
            logger.warning(f"No tasks found for job impact: {job_title}")

    return total_tool_count

async def save_job_impact_tool_count(job_title: str, tool_count: int) -> JobImpactToolCountInDB:
    """
    Save the tool count for a job impact in the database.
    
    Args:
        job_title: Title of the job impact
        tool_count: Total tool count to save
        
    Returns:
        JobImpactToolCountInDB: The saved tool count record
    """
    logger.info(f"Saving tool count for job impact: {job_title} (count: {tool_count})")
    
    # Create or update the tool count record
    tool_count_record = JobImpactToolCountInDB(
        job_impact_name=job_title,
        total_tool_count=tool_count
    )
    
    # Save to database
    save_success = await tool_count_record.save(database)
    if save_success:
        logger.info(f"Successfully saved tool count for {job_title}")
    else:
        logger.warning(f"Failed to save tool count for {job_title}")
    
    return tool_count_record

async def get_job_impact_tool_count(job_title: str) -> Optional[JobImpactToolCountInDB]:
    """
    Get the tool count for a job impact from the database.
    
    Args:
        job_title: Title of the job impact
        
    Returns:
        Optional[JobImpactToolCountInDB]: The tool count record if found
    """
    logger.debug(f"Getting tool count for job impact: {job_title}")
    return await JobImpactToolCountInDB.get_by_job_name(database, job_title)

async def calculate_and_save_job_impact_tool_count(job_title: str, base_url: str) -> Tuple[Dict[str, Any], bool]:
    """
    Calculate the total tool count for a given job impact and save it in its own collection.
    The collection will contain the job_impact_name and the tool count.
    Returns a dictionary with the job_impact_name and total_tool_count, and a flag indicating if it was from cache.
    """
    # Get the job impact details by job title
    job = await get_job_impact_by_title(job_title)
    if not job:
        raise HTTPException(status_code=404, detail="Job impact analysis not found")
    
    # First check if we already have the tool count in the database
    from_cache = False
    tool_count_record = await get_job_impact_tool_count(job_title)
    
    if tool_count_record:
        logger.info(f"Found existing tool count for {job_title}: {tool_count_record.total_tool_count}")
        from_cache = True
        total_tool_count = tool_count_record.total_tool_count
    else:
        # Calculate the tool count
        logger.info(f"No existing tool count found for {job_title}, calculating now")
        total_tool_count = await calculate_job_impact_tool_count(job_title, base_url)
        
        # Save the result in its own collection
        await save_job_impact_tool_count(job_title, total_tool_count)

    # Return the result with cache flag
    return {
        "job_impact": job.model_dump(),
        "total_tool_count": total_tool_count
    }, from_cache