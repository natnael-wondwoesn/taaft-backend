# app/dashboard_api.py
"""
Dashboard API for Source Queue Manager
Provides endpoints for retrieving dashboard statistics and summary data
"""
from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorCollection
from typing import Dict, List, Optional
import datetime
from bson import ObjectId
from pymongo import DESCENDING

# Import from source_queue_manager module
from .source_queue_manager import (
    get_sources_collection,
    get_scraping_tasks_collection,
    get_scraping_logs_collection,
    SourceStatus,
    SourceFrequency,
    SourcePriority,
)

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
    responses={404: {"description": "Not found"}},
)


@router.get("/queue-stats")
async def get_queue_stats(
    sources_collection: AsyncIOMotorCollection = Depends(get_sources_collection),
    logs_collection: AsyncIOMotorCollection = Depends(get_scraping_logs_collection),
):
    """
    Get statistics about the current scraping queue
    """
    # Get total counts by status
    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    status_counts = await sources_collection.aggregate(pipeline).to_list(None)

    # Get counts by priority
    priority_pipeline = [{"$group": {"_id": "$priority", "count": {"$sum": 1}}}]
    priority_counts = await sources_collection.aggregate(priority_pipeline).to_list(
        None
    )

    # Get counts by frequency
    frequency_pipeline = [{"$group": {"_id": "$frequency", "count": {"$sum": 1}}}]
    frequency_counts = await sources_collection.aggregate(frequency_pipeline).to_list(
        None
    )

    # Get overall total
    total_sources = await sources_collection.count_documents({})

    # Get sources scheduled in the next 24 hours
    now = datetime.datetime.utcnow()
    next_24h = now + datetime.timedelta(hours=24)
    scheduled_soon = await sources_collection.count_documents(
        {
            "next_scrape_at": {"$gte": now, "$lte": next_24h},
            "status": SourceStatus.ACTIVE,
        }
    )

    # Get sources that are overdue
    overdue = await sources_collection.count_documents(
        {"next_scrape_at": {"$lt": now}, "status": SourceStatus.ACTIVE}
    )

    # Get logs from the last 24 hours
    recent_logs = await logs_collection.count_documents(
        {"completed_at": {"$gte": now - datetime.timedelta(hours=24)}}
    )

    # Format the response
    status_stats = {item["_id"]: item["count"] for item in status_counts}
    priority_stats = {item["_id"]: item["count"] for item in priority_counts}
    frequency_stats = {item["_id"]: item["count"] for item in frequency_counts}

    return {
        "total_sources": total_sources,
        "scheduled_next_24h": scheduled_soon,
        "overdue": overdue,
        "recent_logs": recent_logs,
        "by_status": status_stats,
        "by_priority": priority_stats,
        "by_frequency": frequency_stats,
    }


@router.get("/queue-timeline")
async def get_queue_timeline(
    days: int = Query(7, ge=1, le=30),
    sources_collection: AsyncIOMotorCollection = Depends(get_sources_collection),
    logs_collection: AsyncIOMotorCollection = Depends(get_scraping_logs_collection),
):
    """
    Get a timeline of scheduled scraping tasks
    """
    now = datetime.datetime.utcnow()
    timeline = []

    # Generate timeline for specified number of days
    for day in range(days):
        day_start = now + datetime.timedelta(days=day)
        day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + datetime.timedelta(days=1)

        # Count sources scheduled for this day
        scheduled_count = await sources_collection.count_documents(
            {
                "next_scrape_at": {"$gte": day_start, "$lt": day_end},
                "status": SourceStatus.ACTIVE,
            }
        )

        # Format date as ISO string without time
        date_str = day_start.date().isoformat()

        timeline.append({"date": date_str, "scheduled": scheduled_count})

    return timeline


@router.get("/recent-logs")
async def get_recent_logs(
    limit: int = Query(10, ge=1, le=100),
    logs_collection: AsyncIOMotorCollection = Depends(get_scraping_logs_collection),
):
    """
    Get the most recent scraping logs
    """
    cursor = logs_collection.find().sort("completed_at", DESCENDING).limit(limit)
    logs = await cursor.to_list(length=limit)

    # Convert ObjectId to str for JSON serialization
    for log in logs:
        if "_id" in log:
            log["_id"] = str(log["_id"])
        if "source_id" in log:
            log["source_id"] = str(log["source_id"])

    return logs


@router.get("/upcoming-sources")
async def get_upcoming_sources(
    limit: int = Query(10, ge=1, le=100),
    sources_collection: AsyncIOMotorCollection = Depends(get_sources_collection),
):
    """
    Get the next sources scheduled for scraping
    """
    now = datetime.datetime.utcnow()
    cursor = (
        sources_collection.find(
            {"next_scrape_at": {"$gte": now}, "status": SourceStatus.ACTIVE}
        )
        .sort("next_scrape_at", 1)
        .limit(limit)
    )

    sources = await cursor.to_list(length=limit)

    # Convert ObjectId to str for JSON serialization
    for source in sources:
        if "_id" in source:
            source["_id"] = str(source["_id"])

    return sources


@router.get("/summary-by-category")
async def get_summary_by_category(
    sources_collection: AsyncIOMotorCollection = Depends(get_sources_collection),
):
    """
    Get a summary of sources grouped by category
    """
    pipeline = [
        {
            "$group": {
                "_id": "$category",
                "count": {"$sum": 1},
                "active": {
                    "$sum": {"$cond": [{"$eq": ["$status", SourceStatus.ACTIVE]}, 1, 0]}
                },
                "error": {
                    "$sum": {"$cond": [{"$eq": ["$status", SourceStatus.ERROR]}, 1, 0]}
                },
            }
        },
        {"$sort": {"count": -1}},
    ]

    categories = await sources_collection.aggregate(pipeline).to_list(None)

    # Handle null category
    for cat in categories:
        if cat["_id"] is None:
            cat["_id"] = "Uncategorized"

    return categories


@router.get("/error-sources")
async def get_error_sources(
    limit: int = Query(10, ge=1, le=100),
    sources_collection: AsyncIOMotorCollection = Depends(get_sources_collection),
):
    """
    Get sources that are in error state
    """
    cursor = (
        sources_collection.find({"status": SourceStatus.ERROR})
        .sort("updated_at", DESCENDING)
        .limit(limit)
    )

    sources = await cursor.to_list(length=limit)

    # Convert ObjectId to str for JSON serialization
    for source in sources:
        if "_id" in source:
            source["_id"] = str(source["_id"])

    return sources
