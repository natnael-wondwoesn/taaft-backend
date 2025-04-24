from fastapi import APIRouter
from .router import router as auth_router
from .sso_router import router as sso_router
from .admin import router as admin_router

# Create a combined router
router = APIRouter()

# Include auth routers without prefix (prefix will be added in main.py)
router.include_router(auth_router, tags=["auth"])
router.include_router(sso_router, tags=["auth"])

# Admin router is already prefixed with '/admin'
router.include_router(admin_router)

__all__ = ["router"]
