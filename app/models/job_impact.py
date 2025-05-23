from pydantic import BaseModel, Field, validator, ConfigDict
from pydantic_core import core_schema  # Import for Pydantic v2
from typing import List, Optional, Any
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
    name: str
    logo_url: Optional[str] = None


class Task(BaseModel):
    name: str
    ai_impact_score: str
    tools: List[Tool] = []


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
                        "ai_impact_score": "80%",
                        "tools": [
                            {
                                "name": "Generated Photos",
                                "logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                            }
                        ],
                    },
                    {
                        "name": "Viral marketing photos",
                        "ai_impact_score": "80%",
                        "tools": [
                            {
                                "name": "Assembo",
                                "logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                            }
                        ],
                    },
                    {
                        "name": "Social media bios",
                        "ai_impact_score": "80%",
                        "tools": [
                            {
                                "name": "AI Social Bio",
                                "logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                            },
                            {
                                "name": "Twitter Bio Generator",
                                "logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                            },
                        ],
                    },
                ],
                "created_at": "2023-01-01T12:00:00Z",
                "updated_at": "2023-01-01T12:30:00Z",
            }
        },
    )


class JobImpactInDB(
    JobImpact
):  # This will represent data as stored in DB, including _id
    pass
