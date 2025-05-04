from fastapi import APIRouter

# Create router for favorites endpoints
router = APIRouter(prefix="/favorites", tags=["favorites"])

# Import routes to make them available
from .routes import *

# Export the router
__all__ = ["router"]
