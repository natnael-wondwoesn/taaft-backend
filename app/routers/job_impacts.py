from fastapi import APIRouter, HTTPException, Query, Path, Depends
from typing import List, Union, Optional
import uuid  # Keep for type hint in id_or_slug, though actual ID is ObjectId
from slugify import slugify
from datetime import datetime
from bson import ObjectId
import re  # For case-insensitive search regex

from app.models.job_impact import (
    JobImpact,
    JobImpactCreate,
    JobImpactInDB,
    PyObjectId,
    preprocess_job_data,
)
from app.database import database  # Import the database instance

router = APIRouter(
    prefix="/api/jobs",
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


@router.get("/{id_or_slug}", response_model=JobImpact)
async def get_job_impact_details(
    id_or_slug: Union[PyObjectId, str] = Path(
        ..., description="MongoDB ObjectId or URL-safe slug of the job"
    )
):
    job: Optional[JobImpactInDB] = None
    if ObjectId.is_valid(id_or_slug):
        # Use the id-based lookup
        job = await JobImpactInDB.get_by_id(database, id_or_slug)

        if not job:
            # Fallback to slug-based lookup
            job = await JobImpactInDB.get_by_slug(database, str(id_or_slug))
    else:
        # Use slug-based lookup
        job = await JobImpactInDB.get_by_slug(database, str(id_or_slug))

    if not job:
        raise HTTPException(status_code=404, detail="Job impact analysis not found")
    return job  # Will be serialized by JobImpact model


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
