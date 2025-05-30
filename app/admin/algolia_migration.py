from fastapi import APIRouter, Depends, status, BackgroundTasks, HTTPException
from typing import Dict, Any
from datetime import datetime
import os
from pydantic import BaseModel

from ..auth.dependencies import get_admin_user
from ..models.user import UserInDB
from ..logger import logger


class MigrationResponse(BaseModel):
    """Response model for migration endpoints."""
    status: str
    message: str
    initiated_by: str
    timestamp: datetime


router = APIRouter(tags=["admin"])


@router.post("/migrate-tools-to-algolia", response_model=MigrationResponse, status_code=status.HTTP_202_ACCEPTED)
async def migrate_tools_to_algolia(
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_admin_user),
):
    """
    Migrate tools from MongoDB to Algolia index.
    This endpoint is only accessible to admin users.
    The migration is executed as a background task.
    """
    # Check for required environment variables before starting
    required_vars = ["ALGOLIA_APP_ID", "ALGOLIA_ADMIN_KEY", "MONGODB_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Migration cannot start: Missing environment variables: {', '.join(missing_vars)}. Please configure these in your environment.",
        )

    # Import the migration function
    from app.algolia.migrater.tools_to_algolia import main as run_migration

    # Add migration task to background tasks
    background_tasks.add_task(run_migration)

    # Log the migration request
    logger.info(f"Tools to Algolia migration started by admin: {current_user.email}")

    return {
        "status": "accepted",
        "message": "Migration process started in the background",
        "initiated_by": current_user.email,
        "timestamp": datetime.utcnow(),
    }


@router.post("/migrate-job-impacts-to-algolia", response_model=MigrationResponse, status_code=status.HTTP_202_ACCEPTED)
async def migrate_job_impacts_to_algolia(
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_admin_user),
):
    """
    Migrate job impacts from MongoDB to Algolia index.
    This endpoint is only accessible to admin users.
    The migration is executed as a background task.
    """
    # Check for required environment variables before starting
    required_vars = ["ALGOLIA_APP_ID", "ALGOLIA_ADMIN_KEY", "MONGODB_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Migration cannot start: Missing environment variables: {', '.join(missing_vars)}. Please configure these in your environment.",
        )

    # Import the migration function
    from app.algolia.migrater.tools_job_impacts_to_algolia import main as run_migration

    # Add migration task to background tasks
    background_tasks.add_task(run_migration)

    # Log the migration request
    logger.info(f"Job impacts to Algolia migration started by admin: {current_user.email}")

    return {
        "status": "accepted",
        "message": "Job impacts migration process started in the background",
        "initiated_by": current_user.email,
        "timestamp": datetime.utcnow(),
    }
