from fastapi import APIRouter

# Create router for shares endpoints
router = APIRouter(prefix="/share", tags=["shares"])

# Import routes to make them available
from .routes import *

# Export the router
__all__ = ["router"]
