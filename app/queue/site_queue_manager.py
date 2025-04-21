"""
Site Queue Manager
This module manages sites in a prioritized queue
"""

import datetime
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from .models import SiteCreate, SiteUpdate, SiteStatus, SitePriority, N8nSiteFormat


class SiteQueueManager:
    def __init__(self, sites_collection):
        self.sites_collection = sites_collection

    async def add_site(self, site: SiteCreate) -> Dict:
        """Add a new site to the queue"""
        # Prepare the site document
        site_dict = site.dict()

        # Convert HttpUrl to string to make it MongoDB compatible
        if "url" in site_dict and hasattr(site_dict["url"], "__str__"):
            site_dict["url"] = str(site_dict["url"])

        site_dict["status"] = SiteStatus.ACTIVE
        site_dict["created_at"] = datetime.datetime.utcnow()
        site_dict["last_updated_at"] = datetime.datetime.utcnow()

        # Insert into database
        result = await self.sites_collection.insert_one(site_dict)

        # Convert _id to string for the response
        created_site = await self.sites_collection.find_one({"_id": result.inserted_id})
        if created_site:
            created_site["_id"] = str(created_site["_id"])
        return created_site

    async def update_site(self, site_id: str, site_update: SiteUpdate) -> Dict:
        """Update an existing site"""
        # Validate that site exists
        site = await self.sites_collection.find_one({"_id": ObjectId(site_id)})
        if not site:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Site with ID {site_id} not found",
            )

        # Prepare update data
        update_data = {
            k: v
            for k, v in site_update.dict(exclude_unset=True).items()
            if v is not None
        }

        # Convert HttpUrl to string to make it MongoDB compatible
        if "url" in update_data and hasattr(update_data["url"], "__str__"):
            update_data["url"] = str(update_data["url"])

        # Add last_updated_at timestamp
        update_data["last_updated_at"] = datetime.datetime.utcnow()

        # Update in database
        await self.sites_collection.update_one(
            {"_id": ObjectId(site_id)}, {"$set": update_data}
        )

        # Return the updated site
        updated_site = await self.sites_collection.find_one({"_id": ObjectId(site_id)})
        if updated_site:
            updated_site["_id"] = str(updated_site["_id"])
        return updated_site

    async def get_sites(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[SiteStatus] = None,
        priority: Optional[SitePriority] = None,
        category: Optional[str] = None,
    ) -> List[Dict]:
        """Get sites with optional filtering"""
        # Prepare filter
        query_filter = {}
        if status:
            query_filter["status"] = status
        if priority:
            query_filter["priority"] = priority
        if category:
            query_filter["category"] = category

        # Query with pagination
        cursor = self.sites_collection.find(query_filter).skip(skip).limit(limit)

        # Sort by priority (high to low) and then by created_at (oldest first)
        priority_order = {
            SitePriority.HIGH: 1,
            SitePriority.MEDIUM: 2,
            SitePriority.LOW: 3,
        }

        cursor = cursor.sort(
            [
                ("priority", ASCENDING),  # This will sort based on enum ordering
                ("created_at", ASCENDING),
            ]
        )

        sites = await cursor.to_list(length=limit)

        # Get total count for the query
        total = await self.sites_collection.count_documents(query_filter)

        # Convert ObjectId to string for the response
        for site in sites:
            site["_id"] = str(site["_id"])

        return {"total": total, "sites": sites}

    async def get_sites_for_n8n(self, limit: int = 100) -> List[Dict]:
        """Get sites formatted for n8n integration with the simple format:
        {
          "_id": { "$oid": "680685e2856a3a9ff097944c" },
          "link": "https://theresanaiforthat.com/*",
          "category_id": "6806415d856a3a9ff0979444"
        }
        """
        # Get active sites
        cursor = self.sites_collection.find({"status": SiteStatus.ACTIVE}).limit(limit)
        sites = await cursor.to_list(length=limit)

        # Format sites for n8n's simple format
        formatted_sites = []
        for site in sites:
            site_id = site.get("_id")
            site_url = site.get("url", "")
            category_id = site.get("category", "")

            if site_id and site_url:
                formatted_sites.append(
                    {
                        "_id": {"$oid": str(site_id)},
                        "link": site_url,
                        "category_id": category_id if category_id else "",
                    }
                )

        return formatted_sites

    async def get_site(self, site_id: str) -> Dict:
        """Get a specific site by ID"""
        site = await self.sites_collection.find_one({"_id": ObjectId(site_id)})
        if not site:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Site with ID {site_id} not found",
            )
        site["_id"] = str(site["_id"])
        return site

    async def delete_site(self, site_id: str) -> bool:
        """Delete a site from the queue"""
        site = await self.sites_collection.find_one({"_id": ObjectId(site_id)})
        if not site:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Site with ID {site_id} not found",
            )

        result = await self.sites_collection.delete_one({"_id": ObjectId(site_id)})
        return result.deleted_count > 0

    async def get_dashboard_stats(self) -> Dict:
        """Get statistics for the dashboard"""
        # Get total counts by status
        pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
        status_counts = await self.sites_collection.aggregate(pipeline).to_list(None)

        # Get counts by priority
        priority_pipeline = [{"$group": {"_id": "$priority", "count": {"$sum": 1}}}]
        priority_counts = await self.sites_collection.aggregate(
            priority_pipeline
        ).to_list(None)

        # Get counts by category
        category_pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
        category_counts = await self.sites_collection.aggregate(
            category_pipeline
        ).to_list(None)

        # Get overall total
        total_sites = await self.sites_collection.count_documents({})

        # Format the response
        status_stats = {item["_id"]: item["count"] for item in status_counts}
        priority_stats = {item["_id"]: item["count"] for item in priority_counts}
        category_stats = {item["_id"]: item["count"] for item in category_counts}

        return {
            "total_sites": total_sites,
            "by_status": status_stats,
            "by_priority": priority_stats,
            "by_category": category_stats,
        }
