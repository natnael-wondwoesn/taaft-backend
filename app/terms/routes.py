# app/terms/routes.py
"""
API routes for terms feature
Handles endpoints for defining terms and retrieving term history
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Dict, List, Optional, Any
import datetime

from .models import (
    TermDefinitionRequest,
    TermDefinitionResponse,
    TermDefinition,
    PopularTerm,
    TermModelType,
    GlossaryTermRequest,
)
from .database import TermsDB, get_terms_db
from .llm_service import terms_llm_service
from ..logger import logger

router = APIRouter(
    prefix="/api/terms",
    tags=["Terms"],
    responses={404: {"description": "Not found"}},
)


@router.post("/define", response_model=TermDefinitionResponse)
async def define_term(
    request: TermDefinitionRequest, terms_db: TermsDB = Depends(get_terms_db)
):
    """Define a term and get a description with examples"""
    # Check if we already have this term defined (case-insensitive match)
    existing_term = await terms_db.get_term_by_exact_match(request.term)

    # If we have an exact match and it's recent (less than 30 days old), return it
    if (
        existing_term
        and (datetime.datetime.utcnow() - existing_term["timestamp"]).days < 30
    ):
        logger.info(f"Using existing definition for term: {request.term}")

        # Still update the popular terms count
        await terms_db._update_popular_term(request.term)

        return {
            "term": existing_term["term"],
            "description": existing_term["description"],
            "examples": existing_term["examples"],
            "id": str(existing_term["_id"]),
            "timestamp": existing_term["timestamp"],
            "model": existing_term.get("model", TermModelType.DEFAULT),
        }

    # Otherwise, get a new definition from the LLM
    model_type = request.model or TermModelType.DEFAULT

    try:
        # Get definition from LLM
        description, examples = await terms_llm_service.get_term_definition(
            request.term, model_type
        )

        # Save to database
        term_data = {
            "term": request.term,
            "description": description,
            "examples": examples,
            "user_id": request.user_id,
            "model": model_type,
        }

        created_term = await terms_db.create_term_definition(term_data)

        # Return response
        return {
            "term": request.term,
            "description": description,
            "examples": examples,
            "id": str(created_term["_id"]),
            "timestamp": created_term["timestamp"],
            "model": model_type,
        }

    except Exception as e:
        logger.error(f"Error defining term '{request.term}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting term definition: {str(e)}",
        )


@router.get("/history", response_model=List[TermDefinition])
async def get_term_history(
    user_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    terms_db: TermsDB = Depends(get_terms_db),
):
    """Get history of term definitions"""
    try:
        if user_id:
            # Get history for a specific user
            terms = await terms_db.get_user_term_history(user_id, limit, skip)
        else:
            # Get all term history
            terms = await terms_db.get_term_history(limit, skip)

        return terms
    except Exception as e:
        logger.error(f"Error retrieving term history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving term history: {str(e)}",
        )


@router.get("/popular", response_model=List[PopularTerm])
async def get_popular_terms(
    limit: int = Query(10, ge=1, le=50),
    terms_db: TermsDB = Depends(get_terms_db),
):
    """Get popular terms"""
    try:
        popular_terms = await terms_db.get_popular_terms(limit)
        return popular_terms
    except Exception as e:
        logger.error(f"Error retrieving popular terms: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving popular terms: {str(e)}",
        )


# @router.post("/glossary-term", response_model=TermDefinitionResponse)
# async def get_glossary_term(
#     request: GlossaryTermRequest, terms_db: TermsDB = Depends(get_terms_db)
# ):
#     """Retrieve a specific term from the glossary, or generate it if it doesn't exist"""
#     # First, check if we already have this term defined (case-insensitive match)
#     existing_term = await terms_db.get_term_by_exact_match(request.term)

#     if existing_term:
#         logger.info(f"Found existing glossary term: {request.term}")

#         # Update the popular terms count
#         await terms_db._update_popular_term(request.term)

#         return {
#             "term": existing_term["term"],
#             "description": existing_term["description"],
#             "examples": existing_term["examples"],
#             "id": str(existing_term["_id"]),
#             "timestamp": existing_term["timestamp"],
#             "model": existing_term.get("model", TermModelType.DEFAULT),
#         }

#     # If term doesn't exist in the glossary, generate it using the LLM service
#     model_type = request.model or TermModelType.DEFAULT

#     try:
#         # Get definition from LLM
#         description, examples = await terms_llm_service.get_term_definition(
#             request.term, model_type
#         )

#         # Save to database
#         term_data = {
#             "term": request.term,
#             "description": description,
#             "examples": examples,
#             "user_id": request.user_id,
#             "model": model_type,
#         }

#         created_term = await terms_db.create_term_definition(term_data)

#         # Return response
#         return {
#             "term": request.term,
#             "description": description,
#             "examples": examples,
#             "id": str(created_term["_id"]),
#             "timestamp": created_term["timestamp"],
#             "model": model_type,
#         }

#     except Exception as e:
#         logger.error(f"Error retrieving glossary term '{request.term}': {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error retrieving glossary term: {str(e)}",
#         )
