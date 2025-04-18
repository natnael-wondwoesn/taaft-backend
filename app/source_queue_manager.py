# app/source_queue_manager.py
"""
Source Queue Manager for Web Scraping
This module manages the scraping sources queue with priority scheduling based on
update frequency and importance.
"""
import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Annotated
from pydantic import BaseModel, Field, HttpUrl, BeforeValidator
from fastapi import APIRouter, Depends, HTTPException, Query, status
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
import logging

# Import database connections
from .source_queue_db import (
    get_sources_collection,
    get_scraping_tasks_collection,
    get_scraping_logs_collection,
)

# Configure logging
from .logger import logger


# Custom ObjectId field for Pydantic
def validate_object_id(v) -> str:
    if not ObjectId.is_valid(v):
        raise ValueError("Invalid ObjectId")
    return str(v)


PydanticObjectId = Annotated[str, BeforeValidator(validate_object_id)]


# Enums for source management
class SourcePriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SourceFrequency(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class SourceStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"
    PENDING = "pending"


# Models
class SourceBase(BaseModel):
    name: str
    url: HttpUrl
    frequency: SourceFrequency
    priority: SourcePriority
    description: Optional[str] = None
    selectors: Optional[Dict[str, str]] = None
    headers: Optional[Dict[str, str]] = None
    requires_javascript: bool = False
    max_pages: Optional[int] = 1
    category: Optional[str] = None


class SourceCreate(SourceBase):
    pass


class Source(SourceBase):
    id: Optional[str] = Field(default=None, alias="_id")
    last_scraped_at: Optional[datetime.datetime] = None
    next_scrape_at: Optional[datetime.datetime] = None
    status: SourceStatus = SourceStatus.PENDING
    error_message: Optional[str] = None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "name": "Example Source",
                "url": "https://example.com",
                "frequency": "daily",
                "priority": "medium",
                "status": "active",
            }
        }


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    frequency: Optional[SourceFrequency] = None
    priority: Optional[SourcePriority] = None
    description: Optional[str] = None
    selectors: Optional[Dict[str, str]] = None
    headers: Optional[Dict[str, str]] = None
    requires_javascript: Optional[bool] = None
    max_pages: Optional[int] = None
    status: Optional[SourceStatus] = None
    category: Optional[str] = None


class ScrapingTask(BaseModel):
    source_id: str
    scheduled_at: datetime.datetime
    status: SourceStatus = SourceStatus.PENDING
    completed_at: Optional[datetime.datetime] = None
    result: Optional[Dict] = None
    error: Optional[str] = None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "source_id": "507f1f77bcf86cd799439011",
                "scheduled_at": "2023-05-01T12:00:00",
                "status": "pending",
            }
        }


class ScrapingLog(BaseModel):
    source_id: str
    source_name: str
    scheduled_at: datetime.datetime
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    status: SourceStatus
    items_scraped: int = 0
    items_added: int = 0
    items_updated: int = 0
    error_message: Optional[str] = None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "source_id": "507f1f77bcf86cd799439011",
                "source_name": "Example Source",
                "scheduled_at": "2023-05-01T12:00:00",
                "status": "completed",
            }
        }


# Source Queue Manager Service
class SourceQueueManager:
    def __init__(self, sources_collection, tasks_collection, logs_collection):
        self.sources_collection = sources_collection
        self.tasks_collection = tasks_collection
        self.logs_collection = logs_collection

    async def add_source(self, source: SourceCreate) -> Dict:
        """Add a new source to the queue"""
        # Calculate the next_scrape_at based on frequency
        next_scrape_at = self._calculate_next_scrape_time(source.frequency)

        # Prepare the source document
        source_dict = source.dict()
        source_dict["status"] = SourceStatus.ACTIVE
        source_dict["next_scrape_at"] = next_scrape_at
        source_dict["created_at"] = datetime.datetime.utcnow()

        # Insert into database
        result = await self.sources_collection.insert_one(source_dict)

        # Convert _id to string for the response
        created_source = await self.sources_collection.find_one(
            {"_id": result.inserted_id}
        )
        if created_source:
            created_source["_id"] = str(created_source["_id"])
        return created_source

    async def update_source(self, source_id: str, source_update: SourceUpdate) -> Dict:
        """Update an existing source"""
        # Validate that source exists
        source = await self.sources_collection.find_one({"_id": ObjectId(source_id)})
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source with ID {source_id} not found",
            )

        # Prepare update data
        update_data = {
            k: v
            for k, v in source_update.dict(exclude_unset=True).items()
            if v is not None
        }

        # If frequency is updated, recalculate next_scrape_at
        if "frequency" in update_data:
            update_data["next_scrape_at"] = self._calculate_next_scrape_time(
                update_data["frequency"]
            )

        # Update the source
        if update_data:
            update_data["updated_at"] = datetime.datetime.utcnow()
            await self.sources_collection.update_one(
                {"_id": ObjectId(source_id)}, {"$set": update_data}
            )

        # Return the updated source
        updated_source = await self.sources_collection.find_one(
            {"_id": ObjectId(source_id)}
        )
        if updated_source:
            updated_source["_id"] = str(updated_source["_id"])
        return updated_source

    async def get_sources(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[SourceStatus] = None,
        priority: Optional[SourcePriority] = None,
        frequency: Optional[SourceFrequency] = None,
    ) -> List[Dict]:
        """Get sources with optional filtering"""
        # Build query filter
        filter_query = {}
        if status:
            filter_query["status"] = status
        if priority:
            filter_query["priority"] = priority
        if frequency:
            filter_query["frequency"] = frequency

        # Execute query with pagination
        cursor = (
            self.sources_collection.find(filter_query)
            .sort("priority", ASCENDING)
            .skip(skip)
            .limit(limit)
        )
        sources = await cursor.to_list(length=limit)
        return sources

    async def get_source(self, source_id: str) -> Dict:
        """Get a specific source by ID"""
        source = await self.sources_collection.find_one({"_id": ObjectId(source_id)})
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source with ID {source_id} not found",
            )
        return source

    async def delete_source(self, source_id: str) -> bool:
        """Delete a source from the queue"""
        result = await self.sources_collection.delete_one({"_id": ObjectId(source_id)})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source with ID {source_id} not found",
            )
        # Delete associated tasks
        await self.tasks_collection.delete_many({"source_id": ObjectId(source_id)})
        return True

    async def get_next_batch(self, batch_size: int = 10) -> List[Dict]:
        """Get the next batch of sources to scrape based on priority and schedule"""
        current_time = datetime.datetime.utcnow()

        # Find sources that are active and due for scraping
        query = {
            "status": SourceStatus.ACTIVE,
            "next_scrape_at": {"$lte": current_time},
        }

        # Sort by priority (high to low) and then by next_scrape_at (oldest first)
        sort_order = [
            ("priority", ASCENDING),  # HIGH comes before LOW alphabetically
            ("next_scrape_at", ASCENDING),
        ]

        cursor = self.sources_collection.find(query).sort(sort_order).limit(batch_size)
        batch = await cursor.to_list(length=batch_size)
        return batch

    async def mark_source_as_scraped(
        self, source_id: str, status: SourceStatus, error: Optional[str] = None
    ) -> Dict:
        """Mark a source as scraped and update its next scrape time"""
        # Get the source to access its frequency
        source = await self.sources_collection.find_one({"_id": ObjectId(source_id)})
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source with ID {source_id} not found",
            )

        # Calculate the next scrape time
        current_time = datetime.datetime.utcnow()
        next_scrape_at = self._calculate_next_scrape_time(source["frequency"])

        # Update the source
        update_data = {
            "status": status,
            "last_scraped_at": current_time,
            "next_scrape_at": next_scrape_at,
            "updated_at": current_time,
        }

        if error:
            update_data["error_message"] = error
            update_data["status"] = SourceStatus.ERROR
        elif status:
            update_data["status"] = status
            update_data["error_message"] = None

        await self.sources_collection.update_one(
            {"_id": ObjectId(source_id)}, {"$set": update_data}
        )

        # Log the scraping task
        log_entry = {
            "source_id": ObjectId(source_id),
            "source_name": source["name"],
            "scheduled_at": source.get("next_scrape_at", current_time),
            "completed_at": current_time,
            "status": update_data["status"],
            "error_message": error,
        }
        await self.logs_collection.insert_one(log_entry)

        # Return the updated source
        updated_source = await self.sources_collection.find_one(
            {"_id": ObjectId(source_id)}
        )
        return updated_source

    async def get_scraping_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        source_id: Optional[str] = None,
        status: Optional[SourceStatus] = None,
    ) -> List[Dict]:
        """Get scraping logs with optional filtering"""
        # Build query filter
        filter_query = {}
        if source_id:
            filter_query["source_id"] = ObjectId(source_id)
        if status:
            filter_query["status"] = status

        # Execute query with pagination
        cursor = (
            self.logs_collection.find(filter_query)
            .sort("completed_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        logs = await cursor.to_list(length=limit)
        return logs

    def _calculate_next_scrape_time(
        self, frequency: Union[str, SourceFrequency]
    ) -> datetime.datetime:
        """Calculate the next scrape time based on frequency"""
        now = datetime.datetime.utcnow()

        if frequency == SourceFrequency.HOURLY:
            return now + datetime.timedelta(hours=1)
        elif frequency == SourceFrequency.DAILY:
            return now + datetime.timedelta(days=1)
        elif frequency == SourceFrequency.WEEKLY:
            return now + datetime.timedelta(weeks=1)
        elif frequency == SourceFrequency.MONTHLY:
            # Adding roughly a month (30 days)
            return now + datetime.timedelta(days=30)
        else:
            # Default to daily if frequency is unknown
            logger.warning(f"Unknown frequency: {frequency}, defaulting to daily")
            return now + datetime.timedelta(days=1)


# FastAPI router
router = APIRouter(
    prefix="/api/sources",
    tags=["Source Queue Manager"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=Source, status_code=status.HTTP_201_CREATED)
async def create_source(
    source: SourceCreate,
    sources_collection=Depends(get_sources_collection),
    tasks_collection=Depends(get_scraping_tasks_collection),
    logs_collection=Depends(get_scraping_logs_collection),
):
    """
    Add a new source to the scraping queue
    """
    source_queue = SourceQueueManager(
        sources_collection, tasks_collection, logs_collection
    )
    return await source_queue.add_source(source)


@router.get("/", response_model=List[Source])
async def read_sources(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[SourceStatus] = None,
    priority: Optional[SourcePriority] = None,
    frequency: Optional[SourceFrequency] = None,
    sources_collection=Depends(get_sources_collection),
    tasks_collection=Depends(get_scraping_tasks_collection),
    logs_collection=Depends(get_scraping_logs_collection),
):
    """
    Get all sources with optional filtering
    """
    source_queue = SourceQueueManager(
        sources_collection, tasks_collection, logs_collection
    )
    return await source_queue.get_sources(skip, limit, status, priority, frequency)


@router.get("/{source_id}", response_model=Source)
async def read_source(
    source_id: str,
    sources_collection=Depends(get_sources_collection),
    tasks_collection=Depends(get_scraping_tasks_collection),
    logs_collection=Depends(get_scraping_logs_collection),
):
    """
    Get a specific source by ID
    """
    source_queue = SourceQueueManager(
        sources_collection, tasks_collection, logs_collection
    )
    return await source_queue.get_source(source_id)


@router.put("/{source_id}", response_model=Source)
async def update_source(
    source_id: str,
    source_update: SourceUpdate,
    sources_collection=Depends(get_sources_collection),
    tasks_collection=Depends(get_scraping_tasks_collection),
    logs_collection=Depends(get_scraping_logs_collection),
):
    """
    Update a source in the queue
    """
    source_queue = SourceQueueManager(
        sources_collection, tasks_collection, logs_collection
    )
    return await source_queue.update_source(source_id, source_update)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    sources_collection=Depends(get_sources_collection),
    tasks_collection=Depends(get_scraping_tasks_collection),
    logs_collection=Depends(get_scraping_logs_collection),
):
    """
    Delete a source from the queue
    """
    source_queue = SourceQueueManager(
        sources_collection, tasks_collection, logs_collection
    )
    await source_queue.delete_source(source_id)
    return None


@router.get("/batch/next", response_model=List[Source])
async def get_next_batch(
    batch_size: int = Query(10, ge=1, le=100),
    sources_collection=Depends(get_sources_collection),
    tasks_collection=Depends(get_scraping_tasks_collection),
    logs_collection=Depends(get_scraping_logs_collection),
):
    """
    Get the next batch of sources to scrape
    """
    source_queue = SourceQueueManager(
        sources_collection, tasks_collection, logs_collection
    )
    return await source_queue.get_next_batch(batch_size)


@router.post("/{source_id}/scraped", response_model=Source)
async def mark_as_scraped(
    source_id: str,
    status: SourceStatus = SourceStatus.COMPLETED,
    error: Optional[str] = None,
    sources_collection=Depends(get_sources_collection),
    tasks_collection=Depends(get_scraping_tasks_collection),
    logs_collection=Depends(get_scraping_logs_collection),
):
    """
    Mark a source as scraped and update its next scrape time
    """
    source_queue = SourceQueueManager(
        sources_collection, tasks_collection, logs_collection
    )
    return await source_queue.mark_source_as_scraped(source_id, status, error)


@router.get("/logs/", response_model=List[ScrapingLog])
async def get_scraping_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    source_id: Optional[str] = None,
    status: Optional[SourceStatus] = None,
    sources_collection=Depends(get_sources_collection),
    tasks_collection=Depends(get_scraping_tasks_collection),
    logs_collection=Depends(get_scraping_logs_collection),
):
    """
    Get scraping logs with optional filtering
    """
    source_queue = SourceQueueManager(
        sources_collection, tasks_collection, logs_collection
    )
    return await source_queue.get_scraping_logs(skip, limit, source_id, status)
