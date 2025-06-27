"""
API Router for Site Queue
Provides endpoints for managing a prioritized queue of sites
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status, Body
from motor.motor_asyncio import AsyncIOMotorCollection
from typing import Dict, List, Optional
import datetime
from bson import ObjectId

from .models import (
    Site,
    SiteCreate,
    SiteUpdate,
    SiteResponse,
    SiteStatus,
    SitePriority,
    N8nSiteFormat,
)
from .database import get_sites_collection
from .site_queue_manager import SiteQueueManager

router = APIRouter(
    prefix="/sites",
    tags=["Sites Queue"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=Site, status_code=status.HTTP_201_CREATED)
async def create_site(
    site: SiteCreate,
    sites_collection: AsyncIOMotorCollection = Depends(get_sites_collection),
):
    """
    Create a new site in the queue
    """
    manager = SiteQueueManager(sites_collection)
    return await manager.add_site(site)


@router.get("/", response_model=SiteResponse)
async def get_sites(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[SiteStatus] = None,
    priority: Optional[SitePriority] = None,
    category: Optional[str] = None,
    sites_collection: AsyncIOMotorCollection = Depends(get_sites_collection),
):
    """
    Get all sites in the queue with optional filtering
    """
    manager = SiteQueueManager(sites_collection)
    return await manager.get_sites(
        skip=skip, limit=limit, status=status, priority=priority, category=category
    )


@router.get("/n8n", response_model=List[Dict])
async def get_sites_for_n8n(
    limit: int = Query(100, ge=1, le=1000),
    sites_collection: AsyncIOMotorCollection = Depends(get_sites_collection),
):
    """
    Get sites in n8n-compatible format:
    {
      "_id": { "$oid": "680685e2856a3a9ff097944c" },
      "link": "https://theresanaiforthat.com/*",
      "category_id": "6806415d856a3a9ff0979444"
    }

    This simple format contains only the essential fields needed for n8n integration.
    """
    manager = SiteQueueManager(sites_collection)
    return await manager.get_sites_for_n8n(limit=limit)


@router.get("/{site_id}", response_model=Site)
async def get_site(
    site_id: str,
    sites_collection: AsyncIOMotorCollection = Depends(get_sites_collection),
):
    """
    Get a specific site by ID
    """
    manager = SiteQueueManager(sites_collection)
    return await manager.get_site(site_id)


@router.put("/{site_id}", response_model=Site)
async def update_site(
    site_id: str,
    site_update: SiteUpdate,
    sites_collection: AsyncIOMotorCollection = Depends(get_sites_collection),
):
    """
    Update a site in the queue
    """
    manager = SiteQueueManager(sites_collection)
    return await manager.update_site(site_id, site_update)


@router.delete("/{site_id}", status_code=status.HTTP_200_OK)
async def delete_site(
    site_id: str,
    sites_collection: AsyncIOMotorCollection = Depends(get_sites_collection),
):
    """
    Delete a site from the queue
    """
    manager = SiteQueueManager(sites_collection)

    # First get the site to include details in success message
    site = await manager.get_site(site_id)
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site with ID {site_id} not found",
        )

    # Attempt to delete the site
    success = await manager.delete_site(site_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete site with ID {site_id}",
        )

    # Return success message with site details
    site_name = site.get("url", "unknown")
    return {
        "status": "success",
        "message": f"Site '{site_name}' successfully removed from queue",
        "site_id": site_id,
    }
