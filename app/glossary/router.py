from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from ..models.glossary import (
    GlossaryTerm,
    GlossaryTermResponse,
    GlossaryTermCreate,
    GlossaryTermUpdate,
    GlossaryTermFilter,
)
from .database import get_glossary_db, GlossaryDB
from ..logger import logger
import datetime
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

# Create router
router = APIRouter(
    prefix="/api/glossary",
    tags=["glossary"],
    responses={404: {"description": "Not found"}},
)


@router.get("/terms", response_model=List[GlossaryTermResponse])
async def list_glossary_terms(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(
        None, description="Search text in name and definition"
    ),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of items to return"),
    sort_by: str = Query("name", description="Field to sort by"),
    sort_desc: bool = Query(False, description="Sort in descending order"),
    glossary_db: GlossaryDB = Depends(get_glossary_db),
):
    """
    List glossary terms with pagination and filtering.
    No authentication required (free tier access).
    """
    try:
        # Create filter parameters
        filter_params = GlossaryTermFilter(category=category, search=search)

        # Determine sort order
        sort_order = DESCENDING if sort_desc else ASCENDING

        # Get terms
        terms = await glossary_db.list_terms(
            filter_params=filter_params,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Convert ObjectId to string for response
        for term in terms:
            term["id"] = str(term.pop("_id"))

        return terms

    except Exception as e:
        logger.error(f"Error listing glossary terms: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/terms/{term_id}", response_model=GlossaryTermResponse)
async def get_glossary_term(
    term_id: str,
    glossary_db: GlossaryDB = Depends(get_glossary_db),
):
    """
    Get a specific glossary term by ID.
    No authentication required (free tier access).
    """
    try:
        term = await glossary_db.get_term_by_id(term_id)

        if not term:
            raise HTTPException(status_code=404, detail="Glossary term not found")

        # Convert ObjectId to string for response
        term["id"] = str(term.pop("_id"))

        return term

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting glossary term: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/terms", response_model=GlossaryTermResponse, status_code=201)
async def create_glossary_term(
    term: GlossaryTermCreate,
    glossary_db: GlossaryDB = Depends(get_glossary_db),
):
    """
    Create a new glossary term.
    No authentication required for this implementation (free tier access).
    """
    try:
        # Check if term with this name already exists
        existing_term = await glossary_db.get_term_by_name(term.name)
        if existing_term:
            raise HTTPException(
                status_code=409,
                detail=f"Glossary term with name '{term.name}' already exists",
            )

        # Prepare term data with timestamps
        now = datetime.datetime.utcnow()
        term_data = {
            **term.dict(),
            "created_at": now,
            "updated_at": now,
        }

        # Create term
        created_term = await glossary_db.create_term(term_data)

        # Convert ObjectId to string for response
        created_term["id"] = str(created_term.pop("_id"))

        return created_term

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating glossary term: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/terms/{term_id}", response_model=GlossaryTermResponse)
async def update_glossary_term(
    term_id: str,
    term_update: GlossaryTermUpdate,
    glossary_db: GlossaryDB = Depends(get_glossary_db),
):
    """
    Update an existing glossary term.
    No authentication required for this implementation (free tier access).
    """
    try:
        # Check if term exists
        existing_term = await glossary_db.get_term_by_id(term_id)
        if not existing_term:
            raise HTTPException(status_code=404, detail="Glossary term not found")

        # If name is being updated, check it's not a duplicate
        if term_update.name and term_update.name != existing_term["name"]:
            name_exists = await glossary_db.get_term_by_name(term_update.name)
            if name_exists:
                raise HTTPException(
                    status_code=409,
                    detail=f"Glossary term with name '{term_update.name}' already exists",
                )

        # Add updated_at timestamp
        update_data = {
            **term_update.dict(exclude_unset=True, exclude_none=True),
            "updated_at": datetime.datetime.utcnow(),
        }

        # Update term
        updated_term = await glossary_db.update_term(term_id, update_data)

        if not updated_term:
            raise HTTPException(status_code=404, detail="Glossary term not found")

        # Convert ObjectId to string for response
        updated_term["id"] = str(updated_term.pop("_id"))

        return updated_term

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating glossary term: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/terms/{term_id}", status_code=204)
async def delete_glossary_term(
    term_id: str,
    glossary_db: GlossaryDB = Depends(get_glossary_db),
):
    """
    Delete a glossary term.
    No authentication required for this implementation (free tier access).
    """
    try:
        # Check if term exists first
        existing_term = await glossary_db.get_term_by_id(term_id)
        if not existing_term:
            raise HTTPException(status_code=404, detail="Glossary term not found")

        # Delete term
        deleted = await glossary_db.delete_term(term_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Glossary term not found")

        return JSONResponse(status_code=204, content=None)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting glossary term: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/categories", response_model=List[str])
async def get_glossary_categories(
    glossary_db: GlossaryDB = Depends(get_glossary_db),
):
    """
    Get all unique categories from the glossary terms.
    No authentication required (free tier access).
    """
    try:
        categories = await glossary_db.get_categories()
        return categories

    except Exception as e:
        logger.error(f"Error getting glossary categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/terms/count", response_model=int)
async def count_glossary_terms(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(
        None, description="Search text in name and definition"
    ),
    glossary_db: GlossaryDB = Depends(get_glossary_db),
):
    """
    Count the total number of glossary terms with optional filtering.
    No authentication required (free tier access).
    """
    try:
        # Create filter parameters
        filter_params = GlossaryTermFilter(category=category, search=search)

        # Count terms
        count = await glossary_db.count_terms(filter_params=filter_params)
        return count

    except Exception as e:
        logger.error(f"Error counting glossary terms: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
