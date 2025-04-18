from .router import router as auth_router
from .tiers import router as tiers_router
from .admin import router as admin_router
from fastapi import APIRouter

# Create a combined router
router = APIRouter()
router.include_router(auth_router)
router.include_router(tiers_router)
router.include_router(admin_router)

__all__ = ["router"]
