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

    # Check for existing slug to avoid duplicates, if necessary
    # existing_job = await database[COLLECTION_NAME].find_one({"slug": slug})
    # if existing_job:
    #     raise HTTPException(status_code=400, detail=f"Job with slug '{slug}' already exists.")

    job_doc = job_impact_data.dict()
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
