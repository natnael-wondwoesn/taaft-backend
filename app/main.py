# app/main.py
from fastapi import FastAPI, WebSocket, Depends, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
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

# Import routers for source queue manager
from .source_queue_manager import router as source_router
from .dashboard_api import router as dashboard_router

# Import the chat router
from .chat import router as chat_router

# Import the Algolia router
from .algolia import router as algolia_router, algolia_config

# Import the auth router
from .auth import router as auth_router
from .auth.dependencies import RateLimitMiddleware

# Import the tools router
from .tools import router as tools_router

load_dotenv()

# Check for test mode
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not TEST_MODE:
        try:
            logger.info("Setting up database...")
            await setup_database()
            logger.info("Database setup completed")

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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limit middleware
app.add_middleware(RateLimitMiddleware)

# Include routers for source queue manager
app.include_router(source_router)
app.include_router(dashboard_router)
app.include_router(chat_router)
app.include_router(algolia_router)
app.include_router(auth_router)  # Include auth router
app.include_router(tools_router)  # Include tools router

# Add StaticFiles mount
app.mount("/static", StaticFiles(directory="static"), name="static")


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

        async for chunk in llm_service.get_streaming_llm_response(
            messages=formatted_messages,
            model_type=model_type,
            system_prompt=system_prompt,
        ):
            # Add new content to the accumulated response
            streamed_chunks.append(chunk)
            response_data["content"] = "".join(streamed_chunks)

            # Send the updated response to all connections for this chat
            for conn in chat_connections:
                await manager.send_personal_json(response_data, conn["websocket"])

        # Mark the response as complete
        response_data["status"] = "complete"
        for conn in chat_connections:
            await manager.send_personal_json(response_data, conn["websocket"])

        # Save the complete response to the database
        assistant_message = {
            "role": MessageRole.ASSISTANT,
            "content": "".join(streamed_chunks),
            "chat_id": ObjectId(chat_id),
            "timestamp": datetime.datetime.utcnow(),
            "metadata": {
                "model": model_type,
                "tokens": llm_service.estimate_tokens("".join(streamed_chunks)),
            },
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


@app.get("/")
async def read_root():
    return {"message": "TAAFT API Server"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat()}
