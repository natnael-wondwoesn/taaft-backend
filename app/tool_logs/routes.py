from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path, Request
from typing import List, Optional
from datetime import datetime, date
from uuid import UUID

from .models import ToolClickLog, ToolClickLogCreate, ToolClickSummary
from .service import tool_click_log_service
from ..auth.dependencies import get_current_active_user, get_admin_user
from ..models.user import UserResponse
from ..logger import logger

router = APIRouter(
    prefix="/api/tool-logs",
    tags=["Tool Logs"],
    responses={404: {"description": "Not found"}},
)

# Public router without authentication requirement
public_router = APIRouter(
    prefix="/public/tool-logs",
    tags=["Public Tool Logs"],
    responses={404: {"description": "Not found"}},
)


@router.post("/click", response_model=ToolClickLog, status_code=201)
async def log_tool_click(
    log_data: ToolClickLogCreate,
    current_user: Optional[UserResponse] = Depends(get_current_active_user),
):
    """
    Record a tool click event.
    
    This endpoint logs when a user clicks the "Try Tool" button.
    """
    user_id = str(current_user.id) if current_user else None
    
    try:
        log = await tool_click_log_service.log_tool_click(log_data, user_id)
        return log
    except Exception as e:
        logger.error(f"Error logging tool click: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to log tool click: {str(e)}"
        )


@public_router.post("/click", response_model=ToolClickLog, status_code=201)
async def public_log_tool_click(
    log_data: ToolClickLogCreate,
    request: Request,
):
    """
    Public endpoint to record a tool click event without authentication.
    
    This endpoint logs when a user clicks the "Try Tool" button and does not require authentication.
    """
    try:
        log = await tool_click_log_service.log_tool_click(log_data)
        return log
    except Exception as e:
        logger.error(f"Error logging public tool click: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to log tool click: {str(e)}"
        )


@router.get("/summary/daily/{date}", response_model=ToolClickSummary)
async def get_daily_summary(
    date: date = Path(..., description="Date to get summary for (YYYY-MM-DD)"),
    current_user: UserResponse = Depends(get_admin_user),
):
    """
    Get a summary of tool clicks for a specific date.
    
    Admin only endpoint.
    """
    try:
        # Convert date to datetime
        target_date = datetime.combine(date, datetime.min.time())
        summary = await tool_click_log_service.get_daily_summary(target_date)
        return summary
    except Exception as e:
        logger.error(f"Error getting daily summary: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get daily summary: {str(e)}"
        )


@router.get("/summary/range", response_model=List[ToolClickSummary])
async def get_date_range_summary(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    current_user: UserResponse = Depends(get_admin_user),
):
    """
    Get daily summaries for a range of dates.
    
    Admin only endpoint.
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date must be before end date"
        )
    
    try:
        # Convert dates to datetime
        start = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.min.time())
        
        summaries = await tool_click_log_service.get_date_range_summary(start, end)
        return summaries
    except Exception as e:
        logger.error(f"Error getting date range summary: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get date range summary: {str(e)}"
        )