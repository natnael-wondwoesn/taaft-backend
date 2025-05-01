from fastapi import APIRouter
from .admin_chat import router as admin_chat_router

# Create a combined router for admin endpoints
router = APIRouter(prefix="/admin", tags=["admin"])

# Include admin routers
router.include_router(admin_chat_router, prefix="")

__all__ = ["router"]
