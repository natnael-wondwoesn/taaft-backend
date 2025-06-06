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
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
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

# Import the terms router
from .terms import router as terms_router

# Import the GHL (GoHighLevel) router
from .ghl.router import router as ghl_router

# Import the blog router
from .blog import router as blog_router

# Import the favorites router
from .favorites import router as favorites_router

# Import the shares router
from .shares import router as shares_router

# Import the bidirectional linking router
from .bidirectional_linking import router as bidirectional_linking_router

# Import the glossary seed script
from .seed_glossary import seed_glossary_terms

from typing import Optional

load_dotenv()

# Check for test mode
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# Get search cache configuration from environment variables
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

            # Seed glossary terms
            logger.info("Seeding glossary terms...")
            await seed_glossary_terms()
            logger.info("Glossary seeding completed")

            # Configure Algolia indexes if available
            if algolia_config.is_configured():
                logger.info("Configuring Algolia indexes...")
                algolia_config.configure_tools_index()
                algolia_config.configure_glossary_index()
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


app = FastAPI(lifespan=lifespan)
# Add this line - must be added before other middlewares
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv(
        "SESSION_SECRET_KEY"
    ),  # Use a secure random string, ideally from env var
)


# Add middleware - CORS must be first, then other middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Frontend development server
        "https://taaft.ai",  # Production frontend
        "https://www.taaft.ai",
        "https://taaft-deploy-18xw.vercel.app/",
        "*",  # For development and testing (remove in production)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# The order is important here:
# 1. PublicFeaturedToolsMiddleware - to mark certain routes as public
# 2. AdminControlMiddleware - to restrict admin operations
#    Note: Regular authenticated endpoints like /tools/keyword-search will use their
#    own authentication via the route handler's get_current_active_user dependency
# 3. RateLimitMiddleware - to limit request rates for authenticated users
# 4. SearchPerformanceMiddleware - to monitor and cache search responses
app.add_middleware(PublicFeaturedToolsMiddleware)
app.add_middleware(AdminControlMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    SearchPerformanceMiddleware,
    cache_enabled=SEARCH_CACHE_ENABLED,
    default_ttl=SEARCH_CACHE_TTL,
)

# Include routers
app.include_router(chat_router)
app.include_router(algolia_router)
app.include_router(auth_router)  # Include auth router with prefix
app.include_router(tools_router)  # Include tools router
app.include_router(public_tools_router)  # Include public tools router
app.include_router(site_queue_router)  # Include site queue router
app.include_router(site_dashboard_router)  # Include site dashboard router
app.include_router(glossary_router)  # Include glossary router
app.include_router(categories_router)  # Include categories router
app.include_router(terms_router)  # Include terms router
app.include_router(admin_router)  # Include admin router
app.include_router(ghl_router)  # Include GHL integration router
app.include_router(blog_router)  # Include blog router
app.include_router(favorites_router)  # Include favorites router
app.include_router(shares_router)  # Include shares router
app.include_router(bidirectional_linking_router)  # Include bidirectional linking router

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/frontend", StaticFiles(directory="static/frontend"), name="frontend")


# Serve the index.html file for the root route
@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse("static/frontend/index.html")


# Handle email verification link from emails
@app.get("/verify-email", include_in_schema=False)
async def handle_email_verification(token: str):
    """
    Handle email verification links from emails.
    This route receives the token via GET request and verifies the email.
    """
    try:
        # Import verify_email function from auth router
        from .auth.utils import decode_token
        from bson import ObjectId

        # Decode and validate token
        token_data = decode_token(token)
        if token_data is None:
            return HTMLResponse(
                content=f"""
            <html>
            <head>
                <title>Email Verification Failed</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                    .container {{ max-width: 600px; margin: 0 auto; }}
                    .error {{ color: #dc3545; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 class="error">Verification Failed</h1>
                    <p>The verification link is invalid or has expired.</p>
                    <p>Please request a new verification link from the login page.</p>
                </div>
            </body>
            </html>
            """,
                status_code=400,
            )

        # Verify the token is for email verification
        if token_data.purpose != "email_verification":
            return HTMLResponse(
                content=f"""
            <html>
            <head>
                <title>Email Verification Failed</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                    .container {{ max-width: 600px; margin: 0 auto; }}
                    .error {{ color: #dc3545; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 class="error">Verification Failed</h1>
                    <p>Invalid token purpose.</p>
                    <p>Please request a new verification link from the login page.</p>
                </div>
            </body>
            </html>
            """,
                status_code=400,
            )

        # Update user verification status
        result = await database.users.update_one(
            {"_id": ObjectId(token_data.sub)},
            {"$set": {"is_verified": True, "updated_at": datetime.datetime.utcnow()}},
        )

        if result.modified_count == 0:
            # Check if user already verified
            user = await database.users.find_one({"_id": ObjectId(token_data.sub)})
            if user and user.get("is_verified", False):
                return HTMLResponse(
                    content=f"""
                <html>
                <head>
                    <title>Email Already Verified</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                        .container {{ max-width: 600px; margin: 0 auto; }}
                        .success {{ color: #28a745; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1 class="success">Already Verified</h1>
                        <p>Your email has already been verified.</p>
                        <p>You can now login to your account.</p>
                    </div>
                </body>
                </html>
                """
                )
            else:
                return HTMLResponse(
                    content=f"""
                <html>
                <head>
                    <title>Email Verification Failed</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                        .container {{ max-width: 600px; margin: 0 auto; }}
                        .error {{ color: #dc3545; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1 class="error">Verification Failed</h1>
                        <p>User not found or verification failed.</p>
                        <p>Please contact support if this issue persists.</p>
                    </div>
                </body>
                </html>
                """,
                    status_code=400,
                )

        # Return success page
        return HTMLResponse(
            content=f"""
        <html>
        <head>
            <title>Email Verified</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .success {{ color: #28a745; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="success">Email Verified</h1>
                <p>Your email has been successfully verified.</p>
                <p>You can now login to your account and access all features.</p>
            </div>
        </body>
        </html>
        """
        )
    except Exception as e:
        logger.error(f"Error verifying email: {str(e)}")
        return HTMLResponse(
            content=f"""
        <html>
        <head>
            <title>Email Verification Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .error {{ color: #dc3545; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="error">Verification Error</h1>
                <p>An error occurred during verification.</p>
                <p>Please try again or contact support if this issue persists.</p>
            </div>
        </body>
        </html>
        """,
            status_code=500,
        )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data_str = await websocket.receive_text()
            logger.info(f"Received WebSocket message")

            try:
                data = json.loads(data_str)

                # Handle different message types
                if data.get("type") == "chat_message":
                    await handle_chat_message(websocket, data)
                elif data.get("type") == "user_connected":
                    # Associate user ID with this websocket connection
                    user_id = data.get("user_id")
                    if user_id:
                        await manager.associate_user(websocket, user_id)
                        await manager.send_personal_json(
                            {"type": "connected", "status": "success"}, websocket
                        )
                else:
                    # Unknown message type
                    await manager.send_personal_json(
                        {"type": "error", "message": "Unknown message type"}, websocket
                    )

            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {data_str}")
                await manager.send_personal_json(
                    {"type": "error", "message": "Invalid JSON"}, websocket
                )
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                await manager.send_personal_json(
                    {"type": "error", "message": f"Error processing request: {str(e)}"},
                    websocket,
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected from WebSocket")


async def handle_chat_message(websocket: WebSocket, data: dict):
    """Process a chat message received through WebSocket"""
    from .chat.llm_service import llm_service
    from .chat.database import get_chat_db
    from .chat.models import ChatModelType, MessageRole

    # Get needed parameters
    chat_id = data.get("chat_id")
    user_id = data.get("user_id")
    message = data.get("message")
    model_type = data.get("model") or ChatModelType.DEFAULT

    if not chat_id or not message:
        await manager.send_personal_json(
            {"type": "error", "message": "Missing required fields (chat_id, message)"},
            websocket,
        )
        return

    # Associate this websocket with the chat
    await manager.associate_chat(websocket, chat_id)

    try:
        # Get database connection
        chat_db = await get_chat_db()

        # Verify the session exists
        session = await chat_db.get_session(chat_id)
        if not session:
            await manager.send_personal_json(
                {
                    "type": "error",
                    "message": f"Chat session with ID {chat_id} not found",
                },
                websocket,
            )
            return

        # Save user message to database
        user_message_data = {
            "role": MessageRole.USER,
            "content": message,
            "chat_id": ObjectId(chat_id),
            "timestamp": datetime.datetime.utcnow(),
            "metadata": {"source": "websocket", "user_id": user_id},
        }
        user_message = await chat_db.add_message(user_message_data)

        # Get system prompt from session
        system_prompt = session.get("system_prompt")

        # Get previous messages for context
        previous_messages = await chat_db.get_messages(chat_id, limit=20)

        # Format messages for the LLM
        formatted_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in previous_messages
            if msg["role"]
            != MessageRole.SYSTEM  # System messages are handled separately
        ]

        # Stream response from LLM
        stream_response_task = asyncio.create_task(
            stream_llm_response(
                formatted_messages=formatted_messages,
                model_type=model_type,
                system_prompt=system_prompt,
                chat_id=chat_id,
                user_id=user_id,
                chat_db=chat_db,
            )
        )

        # Update the session title if this is the first user message
        if len(previous_messages) <= 1:  # 0 or just the system message
            # Generate a title based on the first message
            title = message[:50] + "..." if len(message) > 50 else message
            await chat_db.update_session(chat_id, {"title": title})

    except Exception as e:
        logger.error(f"Error handling WebSocket chat message: {str(e)}")
        await manager.send_personal_json(
            {"type": "error", "message": f"Error processing chat message: {str(e)}"},
            websocket,
        )


async def stream_llm_response(
    formatted_messages, model_type, system_prompt, chat_id, user_id, chat_db
):
    """Stream a response from the LLM through the WebSocket"""
    from .chat.llm_service import llm_service
    from .chat.models import MessageRole

    try:
        # Get connections for this chat
        chat_connections = manager.get_connections_by_chat(chat_id)
        if not chat_connections:
            logger.warning(f"No connections for chat {chat_id}")
            return

        # Begin streaming the response
        streamed_chunks = []
        response_data = {
            "type": "chat_response",
            "chat_id": chat_id,
            "user_id": user_id,
            "content": "",
            "status": "streaming",
        }

        formatted_data = None
        message_id = str(ObjectId())

        async for chunk in llm_service.get_streaming_llm_response(
            messages=formatted_messages,
            model_type=model_type,
            system_prompt=system_prompt,
        ):
            # Check if this is a formatted_data message
            if isinstance(chunk, dict) and chunk.get("type") == "formatted_data":
                formatted_data = chunk.get("data")
                # Send the formatted data in a separate message
                formatted_data_response = {
                    "type": "formatted_data",
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "data": formatted_data,
                }
                for conn in chat_connections:
                    await manager.send_personal_json(
                        formatted_data_response, conn["websocket"]
                    )
            else:
                # Add new content to the accumulated response
                streamed_chunks.append(chunk)
                response_data["content"] = "".join(streamed_chunks)

                # Send the updated response to all connections for this chat
                for conn in chat_connections:
                    await manager.send_personal_json(response_data, conn["websocket"])

        # Mark the response as complete
        response_data["status"] = "complete"
        response_data["message_id"] = message_id
        if formatted_data:
            response_data["formatted_data"] = formatted_data

        # Send final response to all connections
        for conn in chat_connections:
            await manager.send_personal_json(response_data, conn["websocket"])

        # Save assistant's response to database
        assistant_message = {
            "role": MessageRole.ASSISTANT,
            "content": "".join(streamed_chunks),
            "chat_id": ObjectId(chat_id),
            "timestamp": datetime.datetime.utcnow(),
            "metadata": {
                "model": model_type,
                "tokens": llm_service.estimate_tokens("".join(streamed_chunks)),
                "formatted_data": formatted_data,
            },
            "_id": ObjectId(message_id),
        }
        await chat_db.add_message(assistant_message)

        logger.info(f"Completed streaming response for chat {chat_id}")

    except Exception as e:
        logger.error(f"Error streaming LLM response: {str(e)}")
        error_data = {
            "type": "error",
            "message": f"Error generating response: {str(e)}",
        }
        for conn in manager.get_connections_by_chat(chat_id):
            await manager.send_personal_json(error_data, conn["websocket"])


@app.get("/test-nlp-search")
async def test_nlp_search_page():
    """Serve the NLP search test page"""
    return FileResponse("static/test-nlp-search.html")


@app.get("/simple-nlp-test")
async def simple_nlp_test_page():
    """Serve the simple NLP test page"""
    return FileResponse("static/simple-nlp-test.html")


@app.post("/test-api/nlp-search")
async def test_nlp_search_api(request_data: dict):
    """Debug endpoint for NLP search API"""
    return {
        "received": request_data,
        "message": "This is a test endpoint to debug the NLP search API request format",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "time": datetime.datetime.now().isoformat(),
        "websocket_status": "available",
        "active_connections": len(manager.active_connections),
    }


@app.get("/tools")
async def get_all_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    category: Optional[str] = Query(None, description="Filter by category"),
    price_type: Optional[str] = Query(None, description="Filter by price type"),
    sort_by: Optional[str] = Query(
        None, description="Field to sort by (name, created_at, updated_at)"
    ),
    sort_order: str = Query("asc", description="Sort order (asc or desc)"),
):
    """
    List all tools with pagination, filtering and sorting.
    This endpoint is publicly accessible without authentication.
    """
    from .tools.tools_service import get_tools

    # Build filters dictionary from query parameters
    filters = {}
    if category:
        filters["category"] = category
    if price_type:
        filters["price"] = price_type

    # Validate sort_by field if provided
    valid_sort_fields = ["name", "created_at", "updated_at", "price"]
    if sort_by and sort_by not in valid_sort_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by field. Must be one of: {', '.join(valid_sort_fields)}",
        )

    # Validate sort_order
    if sort_order.lower() not in ["asc", "desc"]:
        raise HTTPException(
            status_code=400, detail="Invalid sort_order. Must be 'asc' or 'desc'"
        )

    # Get the tools with filtering and sorting
    tools = await get_tools(
        skip=skip,
        limit=limit,
        filters=filters if filters else None,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Get total count with the same filters
    total = await get_tools(count_only=True, filters=filters if filters else None)

    return {"tools": tools, "total": total, "skip": skip, "limit": limit}


@app.post("/mock-api/nlp-search")
async def mock_nlp_search_api(nlq: NaturalLanguageQuery = Body(...)):
    """Mock NLP search endpoint that returns a valid SearchResult without requiring Algolia"""

    question = nlq.question.lower()

    # Create some mock tool data based on the query
    mock_tools = []

    # Writing tool example
    if "writing" in question or "blog" in question or "content" in question:
        mock_tools.append(
            AlgoliaToolRecord(
                objectID="writing-tool-1",
                name="BlogGenius AI",
                description="AI-powered blog post generator with SEO optimization",
                slug="bloggenius-ai",
                logo_url="https://via.placeholder.com/100",
                website="https://example.com/bloggenius",
                categories=[
                    ToolCategory(id="writing", name="Writing", slug="writing"),
                    ToolCategory(
                        id="content", name="Content Creation", slug="content-creation"
                    ),
                ],
                features=["Blog generation", "SEO optimization", "Content planning"],
                pricing=ToolPricing(type=PricingType.FREEMIUM, starting_at="$0"),
                ratings=ToolRatings(average=4.7, count=120),
                trending_score=95,
            )
        )

    # Image tool example
    if "image" in question or "picture" in question or "photo" in question:
        mock_tools.append(
            AlgoliaToolRecord(
                objectID="image-tool-1",
                name="PixelMaster AI",
                description="Create stunning images with AI in seconds",
                slug="pixelmaster-ai",
                logo_url="https://via.placeholder.com/100",
                website="https://example.com/pixelmaster",
                categories=[
                    ToolCategory(
                        id="image", name="Image Generation", slug="image-generation"
                    ),
                    ToolCategory(id="design", name="Design", slug="design"),
                ],
                features=["Image generation", "Style transfer", "Image editing"],
                pricing=ToolPricing(type=PricingType.FREEMIUM, starting_at="$0"),
                ratings=ToolRatings(average=4.5, count=250),
                trending_score=98,
            )
        )

    # Code tool example
    if "code" in question or "programming" in question or "developer" in question:
        mock_tools.append(
            AlgoliaToolRecord(
                objectID="code-tool-1",
                name="CodeCompanion AI",
                description="AI assistant for developers that helps write, debug and optimize code",
                slug="codecompanion-ai",
                logo_url="https://via.placeholder.com/100",
                website="https://example.com/codecompanion",
                categories=[
                    ToolCategory(
                        id="code", name="Code Generation", slug="code-generation"
                    ),
                    ToolCategory(
                        id="development", name="Development", slug="development"
                    ),
                ],
                features=["Code completion", "Bug fixing", "Code optimization"],
                pricing=ToolPricing(type=PricingType.FREEMIUM, starting_at="$0"),
                ratings=ToolRatings(average=4.8, count=320),
                trending_score=97,
            )
        )

    # Add a generic AI tool if no specific matches or to pad results
    if len(mock_tools) < 2:
        mock_tools.append(
            AlgoliaToolRecord(
                objectID="ai-tool-generic",
                name="AI Assistant Pro",
                description="A versatile AI assistant for everyday tasks",
                slug="ai-assistant-pro",
                logo_url="https://via.placeholder.com/100",
                website="https://example.com/aiassistant",
                categories=[
                    ToolCategory(
                        id="productivity", name="Productivity", slug="productivity"
                    ),
                    ToolCategory(id="assistant", name="Assistant", slug="assistant"),
                ],
                features=["Task automation", "Information lookup", "Scheduling"],
                pricing=ToolPricing(type=PricingType.FREE, starting_at="$0"),
                ratings=ToolRatings(average=4.3, count=150),
                trending_score=85,
            )
        )

    # Create a processed query based on the input
    processed_query = ProcessedQuery(
        original_question=nlq.question,
        search_query="AI tools "
        + nlq.question.lower().replace("i need", "").replace("looking for", ""),
        categories=(
            ["Writing", "Content Creation"]
            if "writing" in question or "blog" in question
            else None
        ),
        pricing_types=(
            [PricingType.FREE, PricingType.FREEMIUM] if "free" in question else None
        ),
        interpreted_intent=f"User is looking for AI tools related to {nlq.question}",
    )

    # Construct the SearchResult
    result = SearchResult(
        tools=mock_tools,
        total=len(mock_tools),
        page=1,
        per_page=10,
        pages=1,
        processing_time_ms=123,
    )
    # Add the processed query to the result
    result.processed_query = processed_query

    return result


# Define all public routes that should bypass auth
public_routes = [
    "/auth/token",
    "/auth/register",
    "/auth/verify-email",
    "/auth/request-password-reset",
    "/auth/reset-password",
    "/api/auth/reset-password",  # Ensure both route patterns are included
    "/auth/refresh-token",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/",
    "/tools/featured",
    "/tools/sponsored",
    "/public/",
]
