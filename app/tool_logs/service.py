from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pymongo import ASCENDING
from bson import ObjectId
from uuid import UUID

from ..database.database import database
from .models import ToolClickLog, ToolClickLogCreate, ToolClickSummary
from ..logger import logger


class ToolClickLogService:
    """Service for managing tool click logs in the database."""
    
    @classmethod
    async def log_tool_click(cls, log_data: ToolClickLogCreate, user_id: Optional[str] = None) -> ToolClickLog:
        """
        Record a new tool click log in the database.
        
        Args:
            log_data: The tool click data to log
            user_id: Optional user ID who clicked the tool
            
        Returns:
            The created log entry
        """
        # Create a new log document
        log_dict = log_data.model_dump()
        
        # Add user_id if provided
        if user_id:
            log_dict["user_id"] = user_id
            
        # Insert into database
        result = await database.tool_clicks.insert_one(log_dict)
        
        # Return the created log
        created_log = ToolClickLog(
            _id=result.inserted_id,
            **log_dict
        )
        
        return created_log
    
    @classmethod
    async def get_daily_summary(cls, date: datetime) -> ToolClickSummary:
        """
        Get a summary of tool clicks for a specific date.
        
        Args:
            date: The date to get summary for
            
        Returns:
            Summary of tool clicks for the date
        """
        # Calculate start and end of the day
        start_date = datetime(date.year, date.month, date.day, 0, 0, 0)
        end_date = start_date + timedelta(days=1)
        
        # Get all clicks for the day
        pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": start_date,
                        "$lt": end_date
                    }
                }
            },
            {
                "$group": {
                    "_id": "$tool_id",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        result = await database.tool_clicks.aggregate(pipeline).to_list(length=1000)
        
        # Calculate total clicks
        total_clicks = sum(item["count"] for item in result)
        
        # Build clicks by tool dictionary
        clicks_by_tool = {item["_id"]: item["count"] for item in result}
        
        # Create and return summary
        summary = ToolClickSummary(
            date=start_date.strftime("%Y-%m-%d"),
            total_clicks=total_clicks,
            clicks_by_tool=clicks_by_tool
        )
        
        return summary
    
    @classmethod
    async def get_date_range_summary(cls, start_date: datetime, end_date: datetime) -> List[ToolClickSummary]:
        """
        Get daily summaries for a range of dates.
        
        Args:
            start_date: The start date for the range
            end_date: The end date for the range
            
        Returns:
            List of daily summaries
        """
        # Normalize dates to start and end of days
        start = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
        end = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)
        
        # Generate list of dates in the range
        summaries = []
        current_date = start
        
        while current_date <= end:
            summary = await cls.get_daily_summary(current_date)
            summaries.append(summary)
            current_date += timedelta(days=1)
            
        return summaries


# Create a singleton instance
tool_click_log_service = ToolClickLogService()