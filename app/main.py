# app/main.py
from fastapi import (
    FastAPI,
    WebSocket,
    Depends,
    WebSocketDisconnect,
    Body,
    Request,
    HTTPException,
    status,
    Query,
)
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from .websocket import manager
from .database import database
from .database.setup import setup_database, cleanup_database
from .logger import logger
from dotenv import load_dotenv
import os
from contextlib import asynccontextmanager
import json
import asyncio
from bson import ObjectId
import datetime
from .algolia.models import (
    SearchResult,
    NaturalLanguageQuery,
    ProcessedQuery,
    AlgoliaToolRecord,
    ToolCategory,
    ToolPricing,
    ToolRatings,
    PricingType,
)

# Import Redis cache service
from .services.redis_cache import redis_client, REDIS_CACHE_ENABLED

# Import the chat router
from .chat import router as chat_router

# Import the Algolia router
from .algolia import (
    router as algolia_router,
    algolia_config,
    SearchPerformanceMiddleware,
)

# Import the auth router
from .auth import router as auth_router
from .auth.dependencies import RateLimitMiddleware, AdminControlMiddleware

# Import the tools router
from .tools import router as tools_router
from .tools import public_router as public_tools_router
from .tools.middleware import PublicFeaturedToolsMiddleware

# Import the admin router
from .admin import router as admin_router

# Import the site queue routers
from .queue import api_router as site_queue_router
from .queue import dashboard_router as site_dashboard_router

# Import the glossary router
from .glossary import router as glossary_router

# Import the categories router
from .categories import router as categories_router
from .categories.routes import public_router as public_categories_router

# Import the blog router
from .blog import router as blog_router

# Import the favorites router
from .favorites import router as favorites_router

# Import the shares router
from .shares import router as shares_router

# Import the bidirectional linking router
from .bidirectional_linking import router as bidirectional_linking_router

# Import the job impacts router
from .routers.job_impacts import router as job_impacts_router

# Import the tool logs router
from .tool_logs import router as tool_logs_router
from .tool_logs import public_router as public_tool_logs_router

# Import glossary seeder
from .seed_glossary import seed_glossary_terms
from typing import Dict, Any, List, Optional
from .models.glossary import GlossaryTerm
import time

load_dotenv()

# Check for testing mode
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# Default timeout for cache (5 minutes)
SEARCH_CACHE_ENABLED = os.getenv("SEARCH_CACHE_ENABLED", "true").lower() == "true"
SEARCH_CACHE_TTL = int(os.getenv("SEARCH_CACHE_TTL", "300"))  # Default 5 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not TEST_MODE:
        try:
            logger.info("Setting up database...")
            await setup_database()
            logger.info("Database setup completed")

            # Ensure all search indexes exist
            logger.info("Ensuring search indexes...")
            from .tools.tools_service import ensure_search_indexes
            await ensure_search_indexes()
            logger.info("Search indexes ready")

            # Check Redis connection
            if REDIS_CACHE_ENABLED and redis_client:
                logger.info("Redis cache is enabled and connected")
            else:
                logger.warning("Redis cache is disabled or not connected")

            # Seed glossary terms
            logger.info("Seeding glossary terms...")
            await seed_glossary_terms()
            logger.info("Glossary seeding completed")

            # Configure Algolia indexes if available
            if algolia_config.is_configured():
                logger.info("Configuring Algolia indexes...")
                algolia_config.configure_tools_index()
                algolia_config.configure_glossary_index()
                algolia_config.configure_tools_job_impacts_index()
                logger.info("Algolia indexes configured successfully")
            else:
                logger.warning(
                    "Algolia not configured. Search functionality will be limited."
                )

            # Check for admin users
            from .models.user import ServiceTier

            admin_count = await database.users.count_documents(
                {"service_tier": ServiceTier.ENTERPRISE}
            )
            if admin_count == 0:
                logger.warning(
                    "No admin users found. Use the /admin/init-admin endpoint to create the first admin user."
                )

        except Exception as e:
            logger.error(f"Error during startup: {str(e)}")
            if TEST_MODE:
                logger.warning("Running in TEST_MODE: Startup errors will be ignored")
            else:
                raise
    else:
        logger.warning("TEST_MODE enabled: Skipping initialization")
    yield

    # Shutdown
    if not TEST_MODE:
        logger.info("Shutting down application...")
        await cleanup_database()
        logger.info("Shutdown complete.")


# Create FastAPI app with proxy support
app = FastAPI(lifespan=lifespan,root_path="/api")

# Add this line - must be added before other middlewares
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv(
        "SESSION_SECRET_KEY"
    ),  # Use a secure random string, ideally from env var
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://taaft-deploy-18xw.vercel.app",  # Old production frontend
        "https://taaft-development.vercel.app",
        "http://taaft-development.vercel.app",
        "http://taaft-development.vercel.app/",
        "https://taaft-development.vercel.app/",
        "https://taaft-deploy-18xw-git-fixes-natnael-alemsegeds-projects.vercel.app",  # Additional frontend
        "https://api.aibyhour.com",
        "https://www.aibyhour.com",  # Main domain for API access
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Custom middleware to handle X-Forwarded-Proto headers from Nginx
class TrustProxyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Get the X-Forwarded-Proto header, default to http if not present
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
        
        # Store original scheme
        request.state.original_scheme = request.url.scheme
        
        # Update request scope with the correct scheme from the proxy
        request.scope["scheme"] = forwarded_proto
        
        # Update request base URL with correct scheme
        request._url = request._url.replace(scheme=forwarded_proto)
        
        return await call_next(request)

# The order is important here:
# 0. TrustProxyMiddleware - to correctly handle HTTPS through Nginx
# 1. PublicFeaturedToolsMiddleware - to mark certain routes as public
# 2. AdminControlMiddleware - to restrict admin operations
#    Note: Regular authenticated endpoints like /tools/keyword-search will use their
#    own authentication via the route handler's get_current_active_user dependency
# 3. RateLimitMiddleware - to limit request rates for authenticated users
# 4. SearchPerformanceMiddleware - to monitor and cache search responses
app.add_middleware(TrustProxyMiddleware)
app.add_middleware(PublicFeaturedToolsMiddleware)
app.add_middleware(AdminControlMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    SearchPerformanceMiddleware,
    cache_enabled=SEARCH_CACHE_ENABLED,
    default_ttl=SEARCH_CACHE_TTL,
)

# Add a global OPTIONS handler for CORS preflight
@app.options("/{full_path:path}")
async def options_handler():
    """Handle CORS preflight requests"""
    return {"status": "ok"}

# Include routers
app.include_router(chat_router)
app.include_router(algolia_router)
app.include_router(auth_router)  # Include auth router with prefix
app.include_router(tools_router)  # Include tools router
app.include_router(public_tools_router)  # Include public tools router
app.include_router(public_categories_router)  # Include public categories router
app.include_router(site_queue_router)
app.include_router(site_dashboard_router)  # Include site dashboard router
app.include_router(glossary_router)  # Include glossary router
app.include_router(categories_router)  # Include categories router
app.include_router(admin_router)  # Include admin router
app.include_router(blog_router)  # Include blog router
app.include_router(favorites_router)  # Include favorites router
app.include_router(shares_router)  # Include shares router
app.include_router(bidirectional_linking_router)  # Include bidirectional linking router
app.include_router(job_impacts_router)  # Include job impacts router
app.include_router(tool_logs_router)  # Include tool logs router
app.include_router(public_tool_logs_router)  # Include public tool logs router

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/frontend", StaticFiles(directory="static/frontend"), name="frontend")

class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = (time.perf_counter() - start_time) * 1000  # ms
        endpoint = request.url.path
        method = request.method
        # Log the performance
        logger.info(f"[PERF] {method} {endpoint} took {process_time:.2f} ms")
        # Optionally, add the timing to the response headers
        response.headers["X-Process-Time-ms"] = str(f"{process_time:.2f}")
        return response

app.add_middleware(PerformanceLoggingMiddleware)
