from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, ClassVar, Union, List
from bson import ObjectId

from app.models.job_impact import PyObjectId


class JobImpactToolCountBase(BaseModel):
    job_impact_name: str
    total_tool_count: int

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "job_impact_name": "Model",
                "total_tool_count": 5
            }
        },
    )


class JobImpactToolCount(JobImpactToolCountBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda dt: dt.isoformat(),
        },
    )


class JobImpactToolCountInDB(JobImpactToolCount):
    """
    This class represents a JobImpactToolCount as stored in the MongoDB database.
    """
    # MongoDB collection name used for this model
    collection_name: ClassVar[str] = "job_impact_tool_counts"

    @classmethod
    async def get_by_job_name(cls, db, job_name: str) -> Optional["JobImpactToolCountInDB"]:
        """
        Retrieve a job impact tool count by job name from the database.
        """
        result = await db[cls.collection_name].find_one({"job_impact_name": job_name})
        if result:
            return cls(**result)
        return None
    
    @classmethod
    async def get_all(
        cls, 
        db, 
        skip: int = 0, 
        limit: int = 20,
        sort_by: str = "total_tool_count",
        sort_order: int = -1
    ) -> List["JobImpactToolCountInDB"]:
        """
        Retrieve all job impact tool counts with pagination.
        Default sorting is by total_tool_count in descending order.
        
        Args:
            db: MongoDB database connection
            skip: Number of items to skip
            limit: Maximum number of items to return
            sort_by: Field to sort by
            sort_order: 1 for ascending, -1 for descending
            
        Returns:
            List of JobImpactToolCountInDB instances
        """
        cursor = (
            db[cls.collection_name]
            .find()
            .sort(sort_by, sort_order)
            .skip(skip)
            .limit(limit)
        )
        results = await cursor.to_list(length=limit)
        
        tool_counts = []
        for doc in results:
            try:
                tool_counts.append(cls(**doc))
            except Exception as e:
                # Log error but continue processing
                print(f"Error processing tool count {doc.get('_id')}: {str(e)}")
                continue
                
        return tool_counts

    async def save(self, db) -> bool:
        """
        Save the current job impact tool count to the database.
        Updates if job_impact_name exists, otherwise creates a new document.
        """
        now = datetime.utcnow()
        self.updated_at = now

        # Check if entry for this job_impact_name already exists
        existing = await db[self.collection_name].find_one(
            {"job_impact_name": self.job_impact_name}
        )

        if existing:
            # Update existing document
            # Create update data manually to avoid _id field
            update_data = {
                "job_impact_name": self.job_impact_name,
                "total_tool_count": self.total_tool_count,
                "updated_at": self.updated_at
            }
            result = await db[self.collection_name].update_one(
                {"job_impact_name": self.job_impact_name}, {"$set": update_data}
            )
            return result.modified_count > 0
        else:
            # Insert new document
            self.created_at = now
            data = self.model_dump(by_alias=True)
            result = await db[self.collection_name].insert_one(data)
            self.id = result.inserted_id
            return bool(result.inserted_id) 