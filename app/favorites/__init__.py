from fastapi import APIRouter

# Create router for favorites endpoints
router = APIRouter(prefix="/favorites", tags=["favorites"], include_in_schema=True)

# Import routes to make them available
from .routes import *

# Export the router
__all__ = ["router"]
