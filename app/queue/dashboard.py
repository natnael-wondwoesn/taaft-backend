"""
Dashboard API for Site Queue
Provides endpoints for retrieving dashboard statistics and summary data for the site queue
"""

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorCollection
from typing import Dict, List, Optional
import datetime
from bson import ObjectId
from pymongo import DESCENDING

from .models import Site, SiteStatus, SitePriority
from .database import get_sites_collection
from .site_queue_manager import SiteQueueManager

router = APIRouter(
    prefix="/api/sites/dashboard",
    tags=["Sites Dashboard"],
    responses={404: {"description": "Not found"}},
)


@router.get("/stats")
async def get_queue_stats(
    sites_collection: AsyncIOMotorCollection = Depends(get_sites_collection),
):
    """
    Get statistics about the current site queue
    """
    manager = SiteQueueManager(sites_collection)
    return await manager.get_dashboard_stats()


@router.get("/by-priority")
async def get_sites_by_priority(
    limit: int = Query(10, ge=1, le=100),
    sites_collection: AsyncIOMotorCollection = Depends(get_sites_collection),
):
    """
    Get sites grouped by priority
    """
    # Create a dictionary to hold sites by priority
    result = {"high": [], "medium": [], "low": []}

    # Get sites for each priority level
    for priority in SitePriority:
        cursor = (
            sites_collection.find({"priority": priority, "status": SiteStatus.ACTIVE})
            .sort("created_at", 1)
            .limit(limit)
        )

        sites = await cursor.to_list(length=limit)

        # Convert ObjectId to str for JSON serialization
        for site in sites:
            if "_id" in site:
                site["_id"] = str(site["_id"])

        result[priority.lower()] = sites

    return result


@router.get("/by-category")
async def get_sites_by_category(
    sites_collection: AsyncIOMotorCollection = Depends(get_sites_collection),
):
    """
    Get a summary of sites grouped by category
    """
    pipeline = [
        {
            "$group": {
                "_id": "$category",
                "count": {"$sum": 1},
                "active": {
                    "$sum": {"$cond": [{"$eq": ["$status", SiteStatus.ACTIVE]}, 1, 0]}
                },
                "paused": {
                    "$sum": {"$cond": [{"$eq": ["$status", SiteStatus.PAUSED]}, 1, 0]}
                },
            }
        },
        {"$sort": {"count": -1}},
    ]

    categories = await sites_collection.aggregate(pipeline).to_list(None)

    # Handle null category
    for cat in categories:
        if cat["_id"] is None:
            cat["_id"] = "Uncategorized"

    return {"categories": categories}


@router.get("/recent")
async def get_recent_sites(
    limit: int = Query(10, ge=1, le=100),
    sites_collection: AsyncIOMotorCollection = Depends(get_sites_collection),
):
    """
    Get the most recently added sites
    """
    cursor = sites_collection.find({}).sort("created_at", DESCENDING).limit(limit)

    sites = await cursor.to_list(length=limit)

    # Convert ObjectId to str for JSON serialization
    for site in sites:
        if "_id" in site:
            site["_id"] = str(site["_id"])

    return {"recent_sites": sites}
