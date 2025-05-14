from fastapi import APIRouter, Depends, HTTPException, status, Body, BackgroundTasks
from typing import List, Dict, Any, Optional
from ..auth.dependencies import get_admin_user
from ..models.user import UserInDB
from ..database import database
from ..logger import logger
import datetime
from bson import ObjectId

router = APIRouter(prefix="/admin", tags=["admin"])

# ... existing code ...


@router.post("/migrate-tools-to-algolia", status_code=status.HTTP_202_ACCEPTED)
async def migrate_tools_to_algolia(
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_admin_user),
):
    """
    Migrate tools from MongoDB to Algolia index.
    This endpoint is only accessible to admin users.
    The migration is executed as a background task.
    """
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
        "timestamp": datetime.datetime.utcnow(),
    }
