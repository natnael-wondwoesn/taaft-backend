from fastapi import APIRouter, HTTPException, Query, Path, Depends
from typing import List, Union, Optional
import uuid  # Keep for type hint in id_or_slug, though actual ID is ObjectId
from slugify import slugify
from datetime import datetime
from bson import ObjectId
import re  # For case-insensitive search regex

from app.models.job_impact import JobImpact, JobImpactCreate, JobImpactInDB, PyObjectId
from app.database import database  # Import the database instance

router = APIRouter(
    prefix="/api/jobs",
    tags=["Job Impacts"],
)

COLLECTION_NAME = "tools_Job_impacts"


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

    # Convert Pydantic model to dict for MongoDB insertion
    job_doc = job_impact_data.dict(by_alias=True)
    job_doc["slug"] = slug
    job_doc["created_at"] = now
    job_doc["updated_at"] = now

    result = await database[COLLECTION_NAME].insert_one(job_doc)
    created_job = await database[COLLECTION_NAME].find_one({"_id": result.inserted_id})
    if created_job:
        return JobImpactInDB(**created_job)
    raise HTTPException(
        status_code=500, detail="Failed to create job impact record after insert."
    )


async def get_job_impact_by_id_from_db(job_id: PyObjectId) -> Optional[JobImpactInDB]:
    job = await database[COLLECTION_NAME].find_one({"_id": job_id})
    if job:
        return JobImpactInDB(**job)
    return None


async def get_job_impact_by_slug_from_db(slug: str) -> Optional[JobImpactInDB]:
    job = await database[COLLECTION_NAME].find_one({"slug": slug})
    if job:
        return JobImpactInDB(**job)
    return None


async def get_all_job_impacts_from_db(
    skip: int = 0, limit: int = 20
) -> List[JobImpactInDB]:
    jobs_cursor = database[COLLECTION_NAME].find().skip(skip).limit(limit)
    jobs_list = await jobs_cursor.to_list(length=limit)
    return [JobImpactInDB(**job) for job in jobs_list]


async def search_job_impacts_in_db(
    query: str, skip: int = 0, limit: int = 20
) -> List[JobImpactInDB]:
    # Case-insensitive regex search for job_title
    # For more advanced search, consider MongoDB text indexes or a dedicated search engine
    regex_query = re.compile(f".*{re.escape(query)}.*", re.IGNORECASE)
    jobs_cursor = (
        database[COLLECTION_NAME]
        .find({"job_title": regex_query})
        .skip(skip)
        .limit(limit)
    )
    jobs_list = await jobs_cursor.to_list(length=limit)
    return [JobImpactInDB(**job) for job in jobs_list]


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
):
    skip = (page - 1) * limit
    if search:
        jobs = await search_job_impacts_in_db(query=search, skip=skip, limit=limit)
    else:
        jobs = await get_all_job_impacts_from_db(skip=skip, limit=limit)
    return jobs  # List of JobImpactInDB, will be serialized by List[JobImpact]


@router.get("/{id_or_slug}", response_model=JobImpact)
async def get_job_impact_details(
    id_or_slug: Union[PyObjectId, str] = Path(
        ..., description="MongoDB ObjectId or URL-safe slug of the job"
    )
):
    job: Optional[JobImpactInDB] = None
    if ObjectId.is_valid(id_or_slug):
        try:
            # Ensure it's an ObjectId if it's a valid string representation
            obj_id = (
                PyObjectId(id_or_slug) if isinstance(id_or_slug, str) else id_or_slug
            )
            job = await get_job_impact_by_id_from_db(job_id=obj_id)
        except (
            ValueError
        ):  # Handle cases where string is not a valid ObjectId but was attempted
            job = await get_job_impact_by_slug_from_db(slug=str(id_or_slug))
    else:
        job = await get_job_impact_by_slug_from_db(slug=str(id_or_slug))

    if not job:
        raise HTTPException(status_code=404, detail="Job impact analysis not found")
    return job  # Will be serialized by JobImpact model


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
