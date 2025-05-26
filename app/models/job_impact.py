from pydantic import (
    BaseModel,
    Field,
    validator,
    ConfigDict,
    field_validator,
    model_validator,
)
from pydantic_core import core_schema  # Import for Pydantic v2
from typing import List, Optional, Any, Dict, Union, ClassVar
import uuid
from datetime import datetime
from bson import ObjectId  # Import ObjectId


# Helper class for ObjectId handling if not already in your project
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(
        cls, v: Any, _: core_schema.ValidationInfo
    ) -> ObjectId:  # Add ValidationInfo
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Any,  # Changed from _handler to Any for broader compatibility
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(ObjectId),
                    core_schema.chain_schema(
                        [
                            core_schema.str_schema(),
                            core_schema.no_info_plain_validator_function(
                                cls.validate_object_id_from_str
                            ),
                        ]
                    ),
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x)
            ),
        )

    @classmethod
    def validate_object_id_from_str(cls, v: str) -> ObjectId:
        if not ObjectId.is_valid(v):
            raise ValueError(f"Invalid ObjectId string: {v}")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema_obj: core_schema.CoreSchema,
        handler: Any,  # Renamed for clarity
    ) -> dict[str, Any]:
        # Use the already defined core_schema's json_schema part
        json_schema = handler(core_schema_obj)
        # Ensure the type is string for OpenAPI schema
        json_schema.update(type="string", example="682b8b48314b48ef942800fd")
        return json_schema


class Tool(BaseModel):
    name: str = Field(alias="tool_name")
    logo_url: Optional[str] = None
    link: Optional[str] = None

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "tool_name": "Generated Photos",
                "logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                "link": "https://www.generatedphotos.com/",
            }
        },
    )


class Task(BaseModel):
    name: str
    ai_impact_score: Optional[str] = (
        None  # Make optional as it appears to be missing in some cases
    )
    tools: List[Tool] = []

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Whole body image generation",
                "ai_impact_score": "80%",
                "tools": [
                    {
                        "tool_name": "Generated Photos",
                        "logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                        "link": "https://www.generatedphotos.com/",
                    }
                ],
            }
        },
    )


class JobImpactBase(BaseModel):
    detail_page_link: str
    job_title: str
    slug: Optional[str] = None
    ai_impact_score: str
    description: str
    ai_impact_summary: Optional[str] = None
    detailed_analysis: Optional[str] = None
    job_category: Optional[str] = None
    tasks: List[Task]

    # Field validator to preprocess tasks from DB format to model format
    @field_validator("tasks", mode="before")
    @classmethod
    def preprocess_tasks(cls, v: Any) -> List[Dict[str, Any]]:
        if not isinstance(v, list):
            return v

        processed_tasks = []
        for task_data in v:
            if not isinstance(task_data, dict):
                continue

            # Handle ai_impact_score if missing
            if "ai_impact_score" not in task_data:
                task_data["ai_impact_score"] = None

            # Process tools
            if "tools" in task_data and isinstance(task_data["tools"], list):
                processed_tools = []
                for tool_data in task_data["tools"]:
                    if isinstance(tool_data, dict):
                        # Create a copy of the tool data
                        tool_copy = dict(tool_data)

                        # Ensure tool_name exists (required by the Tool model)
                        if "name" in tool_copy and "tool_name" not in tool_copy:
                            tool_copy["tool_name"] = tool_copy["name"]
                        elif "tool_name" in tool_copy and "name" not in tool_copy:
                            tool_copy["name"] = tool_copy["tool_name"]

                        # Handle logo_url mapping
                        if "tool_logo_url" in tool_copy and "logo_url" not in tool_copy:
                            tool_copy["logo_url"] = tool_copy["tool_logo_url"]
                        if "tool_link" in tool_copy and "link" not in tool_copy:
                            tool_copy["link"] = tool_copy["tool_link"]

                        processed_tools.append(tool_copy)
                task_data["tools"] = processed_tools

            processed_tasks.append(task_data)

        return processed_tasks


class JobImpactCreate(JobImpactBase):
    pass  # No extra fields needed for creation beyond base + auto-generated slug/timestamps


class JobImpact(JobImpactBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,  # Pydantic v2 equivalent of allow_population_by_field_name
        arbitrary_types_allowed=True,  # Allow custom types like PyObjectId
        json_encoders={
            ObjectId: str,  # Serialize ObjectId to string
            datetime: lambda dt: dt.isoformat(),  # Serialize datetime to ISO format string
        },
        json_schema_extra={
            "example": {
                "_id": "682b8b48314b48ef942800fd",
                "detail_page_link": "https://theresanaiforthat.com/job/model",
                "job_title": "Model",
                "slug": "model",
                "ai_impact_score": "5%",
                "description": "A model is a person who is responsible for showcasing fashion, products, or ideas through visual representation. They work with photographers, designers, stylists, and other industry professionals to create stunning images that attract and captivate audiences.",
                "ai_impact_summary": "AI has a moderate impact on the modeling industry, facilitating certain tasks like image generation and social media content creation, but physical modeling still requires human presence and attributes.",
                "detailed_analysis": "While AI tools can aid in creating visual content and enhancing digital presence, the core responsibilities of a model, such as physical presence and showcasing products, are less impacted by AI. Tasks like body image generation and social media management can be enhanced with AI tools, allowing models to reach broader audiences and streamline content creation.",
                "job_category": "Fashion and Modeling",
                "tasks": [
                    {
                        "name": "Whole body image generation",
                        "task_ai_impact_score": "80%",
                        "tools": [
                            {
                                "tool_name": "Generated Photos",
                                "tool_logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                                "tool_link": "https://www.generatedphotos.com/",
                            }
                        ],
                    },
                    {
                        "name": "Viral marketing photos",
                        "task_ai_impact_score": "80%",
                        "tools": [
                            {
                                "tool_name": "Assembo",
                                "tool_logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                                "tool_link": "https://www.assemble.ai/",
                            }
                        ],
                    },
                    {
                        "name": "Social media bios",
                        "task_ai_impact_score": "80%",
                        "tools": [
                            {
                                "tool_name": "AI Social Bio",
                                "tool_logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                                "tool_link": "https://www.aisocialbio.com/",
                            },
                            {
                                "tool_name": "Twitter Bio Generator",
                                "tool_logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                                "tool_link": "https://www.twitterbio.com/",
                            },
                        ],
                    },
                ],
                "created_at": "2023-01-01T12:00:00Z",
                "updated_at": "2023-01-01T12:30:00Z",
            }
        },
    )


class JobImpactInDB(JobImpact):
    """
    This class represents a JobImpact as stored in the MongoDB database.
    It includes additional functionality for handling MongoDB-specific operations and field formats.
    """

    # MongoDB collection name used for this model
    collection_name: ClassVar[str] = "tools_Job_impacts"

    @model_validator(mode="before")
    @classmethod
    def preprocess_db_document(cls, data: Any) -> Any:
        """
        Preprocess the MongoDB document before validation.
        Handles tool_name to name mapping and other DB-specific conversions.
        """
        if not isinstance(data, dict):
            return data

        # Make a copy to avoid modifying original data
        data_copy = dict(data)

        # Process tasks if they exist
        if "tasks" in data_copy and isinstance(data_copy["tasks"], list):
            processed_tasks = []

            for task in data_copy["tasks"]:
                if not isinstance(task, dict):
                    continue

                # Create a task copy
                task_copy = dict(task)

                # Ensure ai_impact_score exists
                if "ai_impact_score" not in task_copy:
                    task_copy["ai_impact_score"] = None

                # Ensure task_ai_impact_score exists
                if "task_ai_impact_score" not in task_copy:
                    task_copy["task_ai_impact_score"] = None

                # Process tools
                if "tools" in task_copy and isinstance(task_copy["tools"], list):
                    processed_tools = []

                    for tool in task_copy["tools"]:
                        if not isinstance(tool, dict):
                            continue

                        # Create tool copy
                        tool_copy = dict(tool)

                        # Handle field mappings to ensure both name and tool_name exist
                        if "name" in tool_copy and "tool_name" not in tool_copy:
                            tool_copy["tool_name"] = tool_copy["name"]
                        elif "tool_name" in tool_copy and "name" not in tool_copy:
                            tool_copy["name"] = tool_copy["tool_name"]

                        # Handle tool_link mapping
                        if "tool_link" in tool_copy and "link" not in tool_copy:
                            tool_copy["link"] = tool_copy["tool_link"]

                        # Handle tool_logo_url mapping
                        if "tool_logo_url" in tool_copy and "logo_url" not in tool_copy:
                            tool_copy["logo_url"] = tool_copy["tool_logo_url"]

                        processed_tools.append(tool_copy)

                    task_copy["tools"] = processed_tools

                processed_tasks.append(task_copy)

            data_copy["tasks"] = processed_tasks

        return data_copy

    @classmethod
    async def get_by_id(cls, db, id: Union[str, ObjectId]) -> Optional["JobImpactInDB"]:
        """
        Retrieve a job impact by ID from the database.

        Args:
            db: MongoDB database connection
            id: ObjectId or string representation of ObjectId

        Returns:
            JobImpactInDB instance or None if not found
        """
        if isinstance(id, str):
            if not ObjectId.is_valid(id):
                return None
            id = ObjectId(id)

        result = await db[cls.collection_name].find_one({"_id": id})
        if result:
            return cls(**result)
        return None

    @classmethod
    async def get_by_slug(cls, db, slug: str) -> Optional["JobImpactInDB"]:
        """
        Retrieve a job impact by slug from the database.

        Args:
            db: MongoDB database connection
            slug: URL-friendly job slug

        Returns:
            JobImpactInDB instance or None if not found
        """
        result = await db[cls.collection_name].find_one({"slug": slug})
        if result:
            return cls(**result)
        return None

    @classmethod
    async def get_all(
        cls,
        db,
        skip: int = 0,
        limit: int = 20,
        sort_by: str = "job_title",
        sort_order: int = 1,
    ) -> List["JobImpactInDB"]:
        """
        Retrieve all job impacts with pagination.

        Args:
            db: MongoDB database connection
            skip: Number of items to skip
            limit: Maximum number of items to return
            sort_by: Field to sort by
            sort_order: 1 for ascending, -1 for descending

        Returns:
            List of JobImpactInDB instances
        """
        cursor = (
            db[cls.collection_name]
            .find()
            .sort(sort_by, sort_order)
            .skip(skip)
            .limit(limit)
        )
        results = await cursor.to_list(length=limit)

        jobs = []
        for doc in results:
            try:
                jobs.append(cls(**doc))
            except Exception as e:
                # Log error but continue processing
                print(f"Error processing job {doc.get('_id')}: {str(e)}")
                continue

        return jobs

    @classmethod
    async def search(
        cls, db, query: str, skip: int = 0, limit: int = 20
    ) -> List["JobImpactInDB"]:
        """
        Search for job impacts by job title.

        Args:
            db: MongoDB database connection
            query: Search query string
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of JobImpactInDB instances matching the search
        """
        import re

        regex_query = re.compile(f".*{re.escape(query)}.*", re.IGNORECASE)
        cursor = (
            db[cls.collection_name]
            .find({"job_title": regex_query})
            .skip(skip)
            .limit(limit)
        )
        results = await cursor.to_list(length=limit)

        jobs = []
        for doc in results:
            try:
                jobs.append(cls(**doc))
            except Exception as e:
                # Log error but continue processing
                print(f"Error processing job {doc.get('_id')}: {str(e)}")
                continue

        return jobs

    async def save(self, db) -> bool:
        """
        Save the current job impact to the database.
        Updates if _id exists, otherwise creates a new document.

        Args:
            db: MongoDB database connection

        Returns:
            True if operation was successful, False otherwise
        """
        now = datetime.utcnow()
        self.updated_at = now

        data = self.model_dump(by_alias=True)

        if hasattr(self, "id") and self.id:
            # Update existing document
            result = await db[self.collection_name].update_one(
                {"_id": self.id}, {"$set": data}
            )
            return result.modified_count > 0
        else:
            # Insert new document
            self.created_at = now
            result = await db[self.collection_name].insert_one(data)
            self.id = result.inserted_id
            return bool(result.inserted_id)


# Helper function to preprocess job data from database before model validation
def preprocess_job_data(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Preprocess job data from database to ensure it can be validated by the model.
    This helps handle mismatches between database and model structure.
    """
    if not job_data:
        return job_data

    # Make a copy to avoid modifying the original
    job_data = dict(job_data)

    # Process tasks if they exist
    if "tasks" in job_data and isinstance(job_data["tasks"], list):
        processed_tasks = []

        for task in job_data["tasks"]:
            if not isinstance(task, dict):
                continue

            # Create a processed task
            processed_task = dict(task)

            # Ensure ai_impact_score exists
            if "ai_impact_score" not in processed_task:
                processed_task["ai_impact_score"] = None

            # Ensure task_ai_impact_score exists
            if "task_ai_impact_score" not in processed_task:
                processed_task["task_ai_impact_score"] = None

            # Process tools if they exist
            if "tools" in processed_task and isinstance(processed_task["tools"], list):
                processed_tools = []

                for tool in processed_task["tools"]:
                    if not isinstance(tool, dict):
                        continue

                    processed_tool = dict(tool)

                    # Ensure both name and tool_name exist
                    if "name" in processed_tool and "tool_name" not in processed_tool:
                        processed_tool["tool_name"] = processed_tool["name"]
                    elif "tool_name" in processed_tool and "name" not in processed_tool:
                        processed_tool["name"] = processed_tool["tool_name"]

                    # Handle tool_link mapping
                    if "tool_link" in processed_tool and "link" not in processed_tool:
                        processed_tool["link"] = processed_tool["tool_link"]

                    # Handle tool_logo_url mapping
                    if (
                        "tool_logo_url" in processed_tool
                        and "logo_url" not in processed_tool
                    ):
                        processed_tool["logo_url"] = processed_tool["tool_logo_url"]

                    processed_tools.append(processed_tool)

                processed_task["tools"] = processed_tools

            processed_tasks.append(processed_task)

        job_data["tasks"] = processed_tasks

    return job_data
