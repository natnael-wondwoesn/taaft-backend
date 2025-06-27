from fastapi import APIRouter, HTTPException, Query, Path, Depends, Request, Response
from typing import List, Union, Optional, Dict, Any
import uuid  # Keep for type hint in id_or_slug, though actual ID is ObjectId
from slugify import slugify
from datetime import datetime
from bson import ObjectId
import re  # For case-insensitive search regex
import httpx
import urllib.parse

from app.models.job_impact import (
    JobImpact,
    JobImpactCreate,
    JobImpactInDB,
    PyObjectId,
    preprocess_job_data,
)
from app.models.job_impact_tool_count import JobImpactToolCountInDB
from app.database import database  # Import the database instance
from app.services.job_impacts_service import (
    calculate_and_save_job_impact_tool_count, 
    get_job_impact_tool_count
)
from app.logger import logger

router = APIRouter(
    prefix="/jobs",
    tags=["Job Impacts"],
)

COLLECTION_NAME = JobImpactInDB.collection_name


# Helper to generate slug (can be moved to a utility module)
def generate_slug(title: str) -> str:
    return slugify(title)


# --- Database Operations ---


async def create_job_impact_in_db(job_impact_data: JobImpactCreate) -> JobImpactInDB:
    slug = generate_slug(job_impact_data.job_title)
    now = datetime.utcnow()

    # Check for existing slug to avoid duplicates
    existing_job = await database[COLLECTION_NAME].find_one({"slug": slug})
    if existing_job:
        # Append a short suffix to make the slug unique
        suffix = str(uuid.uuid4())[:6]
        slug = f"{slug}-{suffix}"

    # Create a new JobImpactInDB instance
    job_impact = JobImpactInDB(
        **job_impact_data.model_dump(), slug=slug, created_at=now, updated_at=now
    )

    # Save to database using the model's save method
    success = await job_impact.save(database)
    if success:
        return job_impact

    raise HTTPException(
        status_code=500, detail="Failed to create job impact record after insert."
    )


async def get_job_impact_by_id_from_db(job_id: PyObjectId) -> Optional[JobImpactInDB]:
    # Using the model's get_by_id class method
    return await JobImpactInDB.get_by_id(database, job_id)


async def get_job_impact_by_slug_from_db(slug: str) -> Optional[JobImpactInDB]:
    # Using the model's get_by_slug class method
    return await JobImpactInDB.get_by_slug(database, slug)


async def get_all_job_impacts_from_db(
    skip: int = 0, limit: int = 20
) -> List[JobImpactInDB]:
    # Using the model's get_all class method
    return await JobImpactInDB.get_all(database, skip=skip, limit=limit)


async def search_job_impacts_in_db(
    query: str, skip: int = 0, limit: int = 20
) -> List[JobImpactInDB]:
    # Using the model's search class method
    return await JobImpactInDB.search(database, query=query, skip=skip, limit=limit)


async def get_job_impact_by_title(job_title: str) -> Optional[JobImpactInDB]:
    """Get a job impact by exact job title"""
    result = await database[JobImpactInDB.collection_name].find_one({"job_title": job_title})
    if result:
        return JobImpactInDB(**result)
    return None


# --- API Endpoints ---


@router.post("/", response_model=JobImpact, status_code=201)
async def create_job_impact(job_impact_data: JobImpactCreate):
    """
    Create a new job impact analysis record.
    The slug will be automatically generated from the job_title.
    `created_at` and `updated_at` timestamps are set automatically.
    """
    db_job_impact = await create_job_impact_in_db(job_impact_data)
    return db_job_impact  # Will be serialized by JobImpact model


@router.get("/", response_model=List[JobImpact])
async def list_job_impacts(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search query for job titles"),
    sort_by: str = Query("job_title", description="Field to sort by"),
    sort_order: int = Query(
        1, ge=-1, le=1, description="Sort order: 1 for ascending, -1 for descending"
    ),
):
    skip = (page - 1) * limit
    if search:
        jobs = await search_job_impacts_in_db(query=search, skip=skip, limit=limit)
    else:
        jobs = await JobImpactInDB.get_all(
            database, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order
        )
    return jobs  # List of JobImpactInDB, will be serialized by List[JobImpact]


@router.get("/by-title")
async def get_job_impact_by_job_title(
    request: Request,
    job_title: str = Query(..., description="Exact job title to look up")
):
    """
    Get a job impact by its exact job title.
    This endpoint performs an exact match on the job title.
    The response includes the job impact data and the total tool count from the database.
    """
    logger.info(f"Getting job impact by title: {job_title}")
    
    job = await get_job_impact_by_title(job_title)
    if not job:
        logger.warning(f"Job impact not found: {job_title}")
        raise HTTPException(status_code=404, detail="Job impact analysis not found")
    
    # Get the tool count from the database
    tool_count = await get_job_impact_tool_count(job_title)
    
    # If tool count not found, return 0
    total_tool_count = 0
    if tool_count:
        total_tool_count = tool_count.total_tool_count
        logger.info(f"Retrieved tool count for {job_title}: {total_tool_count}")
    else:
        # No tool count found - this shouldn't happen if the script has been run
        logger.warning(f"No tool count found for job impact: {job_title}")
        
        # Get base URL from request
        base_url = str(request.base_url).rstrip('/')
        # If using http, switch to https
        if base_url.startswith('http:'):
            base_url = 'https:' + base_url[5:]
        
        # Get the result using the service function that will calculate and save
        result, from_cache = await calculate_and_save_job_impact_tool_count(job_title, base_url)
        return result
    
    # Create response with both job impact data and tool count
    job_dict = job.model_dump()
    response_data = {
        "job_impact": job_dict,
        "total_tool_count": total_tool_count
    }
    
    return response_data


@router.get("/by-title/{job_title}/with-tool-count")
async def get_job_impact_details_with_tool_count(
    request: Request,
    response: Response,
    job_title: str = Path(
        ..., description="Job title to get details and tool count for"
    )
):
    """
    Get job impact details by job title with tool counts.
    This endpoint retrieves both the job impact details and the pre-calculated tool count.
    """
    logger.info(f"Getting job impact details with tool count: {job_title}")
    
    base_url = str(request.base_url).rstrip('/')
    result, from_cache = await calculate_and_save_job_impact_tool_count(job_title, base_url)
    
    # Add header flag indicating data source
    response.headers["X-Data-Source"] = "database-cache" if from_cache else "newly-calculated"
    
    return result


@router.get("/tool-counts/{job_title}", response_model=JobImpactToolCountInDB)
async def get_job_impact_tool_count_endpoint(
    job_title: str = Path(..., description="Job title to get tool count for")
):
    """
    Get the total tool count for a specific job impact by job title.
    This endpoint retrieves the pre-calculated tool count from the database.
    """
    logger.info(f"Getting tool count for job impact: {job_title}")
    
    tool_count = await get_job_impact_tool_count(job_title)
    if not tool_count:
        logger.warning(f"Tool count not found for job: {job_title}")
        raise HTTPException(status_code=404, detail="Tool count not found for this job")
    
    logger.info(f"Retrieved tool count for {job_title}: {tool_count.total_tool_count}")
    return tool_count


@router.get("/tool-counts", response_model=List[JobImpactToolCountInDB])
async def list_job_impact_tool_counts(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("total_tool_count", description="Field to sort by"),
    sort_order: int = Query(
        -1, ge=-1, le=1, description="Sort order: 1 for ascending, -1 for descending"
    ),
):
    """
    Get a list of all job impact tool counts with pagination.
    Default sorting is by total_tool_count in descending order.
    """
    skip = (page - 1) * limit
    tool_counts = await JobImpactToolCountInDB.get_all(
        database, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order
    )
    return tool_counts


@router.put("/{id}", response_model=JobImpact)
async def update_job_impact(id: PyObjectId, job_update: JobImpactCreate):
    """
    Update an existing job impact record by ID.
    """
    # First get the existing job
    existing_job = await JobImpactInDB.get_by_id(database, id)
    if not existing_job:
        raise HTTPException(status_code=404, detail="Job impact analysis not found")

    # Update fields from the request
    for field, value in job_update.model_dump(
        exclude={"id", "created_at", "updated_at"}
    ).items():
        setattr(existing_job, field, value)

    # Save changes
    success = await existing_job.save(database)
    if not success:
        raise HTTPException(
            status_code=500, detail="Failed to update job impact record"
        )

    return existing_job


@router.delete("/{id}", status_code=204)
async def delete_job_impact(id: PyObjectId):
    """
    Delete a job impact record by ID.
    """
    # Check if job exists first
    existing_job = await JobImpactInDB.get_by_id(database, id)
    if not existing_job:
        raise HTTPException(status_code=404, detail="Job impact analysis not found")

    # Delete the job
    result = await database[COLLECTION_NAME].delete_one({"_id": id})
    if result.deleted_count != 1:
        raise HTTPException(
            status_code=500, detail="Failed to delete job impact record"
        )

    # No content returned for successful delete
    return None


@router.post("/admin/generate-slugs", status_code=200)
async def generate_missing_slugs():
    """
    Admin utility endpoint to generate and save slugs for all job entries that have null slugs.
    Returns the count of updated records.
    """
    # Find all jobs without slugs
    cursor = database[COLLECTION_NAME].find({"slug": None})
    jobs_without_slugs = await cursor.to_list(length=1000)

    update_count = 0
    slug_collisions = 0

    # Generate and update slugs
    for job in jobs_without_slugs:
        if not job.get("job_title"):
            continue  # Skip if no job_title to generate slug from

        slug = generate_slug(job["job_title"])

        # Check for duplicate slugs
        existing_with_slug = await database[COLLECTION_NAME].find_one(
            {"slug": slug, "_id": {"$ne": job["_id"]}}
        )
        if existing_with_slug:
            # If collision, append object id suffix
            suffix = str(job["_id"])[-6:]  # Use last 6 chars of ObjectId
            slug = f"{slug}-{suffix}"
            slug_collisions += 1

        # Update the record
        result = await database[COLLECTION_NAME].update_one(
            {"_id": job["_id"]},
            {"$set": {"slug": slug, "updated_at": datetime.utcnow()}},
        )

        if result.modified_count > 0:
            update_count += 1

    return {
        "message": f"Successfully updated {update_count} job records with missing slugs",
        "updated_count": update_count,
        "slug_collisions": slug_collisions,
        "total_processed": len(jobs_without_slugs),
    }
