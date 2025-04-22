# app/categories/routes.py
"""
API routes for categories management
"""
from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Optional

from .models import CategoryResponse
from .service import categories_service
from ..logger import logger

router = APIRouter(
    prefix="/api/categories",
    tags=["Categories"],
    responses={404: {"description": "Not found"}},
)


@router.get("", response_model=List[CategoryResponse])
async def get_categories():
    """
    Get all available categories for tools

    Returns:
        List of category objects with id, name, slug, and count
    """
    categories = await categories_service.get_all_categories()
    return categories


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category_by_id(category_id: str):
    """
    Get a category by its ID

    Args:
        category_id: ID of the category to fetch

    Returns:
        Category object with id, name, slug, and count
    """
    category = await categories_service.get_category_by_id(category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID {category_id} not found",
        )
    return category


@router.get("/slug/{slug}", response_model=CategoryResponse)
async def get_category_by_slug(slug: str):
    """
    Get a category by its slug

    Args:
        slug: Slug of the category to fetch

    Returns:
        Category object with id, name, slug, and count
    """
    category = await categories_service.get_category_by_slug(slug)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with slug '{slug}' not found",
        )
    return category
