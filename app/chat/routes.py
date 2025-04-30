# app/chat/routes.py
"""
API routes for chat feature
Handles endpoints for creating and managing chat sessions and messages
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from typing import Dict, List, Optional, Any
from bson import ObjectId
import datetime
from fastapi.responses import HTMLResponse, StreamingResponse
import json
import asyncio

from .models import (
    ChatSessionCreate,
    ChatSession,
    MessageCreate,
    Message,
    ChatMessageRequest,
    ChatMessageResponse,
    MessageRole,
    ChatModelType,
)
from .database import ChatDB, get_chat_db
from .llm_service import llm_service
from ..logger import logger
from ..database.database import database

router = APIRouter(
    prefix="/api/chat",
    tags=["Chat"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/sessions", response_model=ChatSession, status_code=status.HTTP_201_CREATED
)
async def create_chat_session(
    session: ChatSessionCreate, chat_db: ChatDB = Depends(get_chat_db)
):
    """Create a new chat session"""
    # Convert Pydantic model to dict
    session_data = session.dict()

    # Validate user_id if provided
    if session.user_id:
        # Check if the user_id is a valid ObjectId
        try:
            user_id_obj = ObjectId(session.user_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid user ID format: {session.user_id}",
            )

        # Check if the user exists in the database
        user = await database.users.find_one({"_id": user_id_obj})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with ID {session.user_id} not found",
            )

    # Create session in database
    created_session = await chat_db.create_session(session_data)

    # If system prompt was provided, add it as a system message
    if session.system_prompt:
        message_data = {
            "role": MessageRole.SYSTEM,
            "content": session.system_prompt,
            "chat_id": created_session["_id"],
            "timestamp": datetime.datetime.utcnow(),
        }
        await chat_db.add_message(message_data)

    return created_session


@router.get("/sessions", response_model=List[ChatSession])
async def get_user_sessions(
    user_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    chat_db: ChatDB = Depends(get_chat_db),
):
    """Get all chat sessions for a user"""
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User ID is required"
        )

    sessions = await chat_db.get_user_sessions(user_id, limit, skip)
    return sessions


@router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_chat_session(session_id: str, chat_db: ChatDB = Depends(get_chat_db)):
    """Get a chat session by ID"""
    session = await chat_db.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    return session


@router.put("/sessions/{session_id}", response_model=ChatSession)
async def update_chat_session(
    session_id: str, update_data: Dict[str, Any], chat_db: ChatDB = Depends(get_chat_db)
):
    """Update a chat session"""
    # Remove protected fields
    protected_fields = ["_id", "created_at", "message_count"]
    for field in protected_fields:
        if field in update_data:
            del update_data[field]

    updated_session = await chat_db.update_session(session_id, update_data)
    if not updated_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    return updated_session


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(session_id: str, chat_db: ChatDB = Depends(get_chat_db)):
    """Delete a chat session and all its messages"""
    success = await chat_db.delete_session(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    return None


@router.post("/sessions/{session_id}/archive", response_model=ChatSession)
async def archive_chat_session(session_id: str, chat_db: ChatDB = Depends(get_chat_db)):
    """Archive a chat session (mark as inactive)"""
    archived_session = await chat_db.archive_session(session_id)
    if not archived_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    return archived_session


@router.get("/sessions/{session_id}/messages", response_model=List[Message])
async def get_chat_messages(
    session_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    chat_db: ChatDB = Depends(get_chat_db),
):
    """Get all messages for a chat session"""
    # Verify the session exists
    session = await chat_db.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    # Get messages
    messages = await chat_db.get_messages(session_id, limit, skip)
    return messages


@router.post("/sessions/{session_id}/messages/stream")
async def stream_chat_message(
    session_id: str, request: ChatMessageRequest, chat_db: ChatDB = Depends(get_chat_db)
):
    """Send a message to the chat and get a streaming response from the LLM using SSE"""
    try:
        # Verify the session exists
        session = await chat_db.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat session with ID {session_id} not found",
            )

        # Save user message to database
        user_message_data = {
            "role": MessageRole.USER,
            "content": request.message,
            "chat_id": ObjectId(session_id),
            "timestamp": datetime.datetime.utcnow(),
            "metadata": request.metadata or {},
        }
        user_message = await chat_db.add_message(user_message_data)

        # Get system prompt from session
        system_prompt = session.get("system_prompt")

        # Get previous messages for context
        previous_messages = await chat_db.get_messages(session_id, limit=20)

        # Format messages for the LLM
        formatted_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in previous_messages
            if msg["role"]
            != MessageRole.SYSTEM  # System messages are handled separately
        ]

        # Use model from request or session
        model_type = request.model or session.get("model") or ChatModelType.DEFAULT

        # Create streaming response
        async def event_generator():
            # Variables to collect the full response
            full_response = ""
            message_id = str(ObjectId())
            formatted_data = None

            # Initial event with message ID
            yield f"data: {json.dumps({'event': 'start', 'message_id': message_id})}\n\n"

            # Stream the LLM response
            async for chunk in llm_service.get_streaming_llm_response(
                messages=formatted_messages,
                model_type=model_type,
                system_prompt=system_prompt,
            ):
                # Check if this is a formatted_data message
                if isinstance(chunk, dict) and chunk.get("type") == "formatted_data":
                    formatted_data = chunk.get("data")
                    yield f"data: {json.dumps({'event': 'formatted_data', 'data': formatted_data})}\n\n"
                else:
                    full_response += chunk
                    yield f"data: {json.dumps({'event': 'chunk', 'content': chunk})}\n\n"
                    await asyncio.sleep(0.01)  # Small delay to control flow

            # Final event
            yield f"data: {json.dumps({'event': 'end', 'message_id': message_id})}\n\n"

            # Save the complete response to the database
            assistant_message = {
                "role": MessageRole.ASSISTANT,
                "content": full_response,
                "chat_id": ObjectId(session_id),
                "timestamp": datetime.datetime.utcnow(),
                "metadata": {
                    "model": model_type,
                    "tokens": llm_service.estimate_tokens(full_response),
                    "formatted_data": formatted_data,
                },
                "_id": ObjectId(message_id),
            }
            await chat_db.add_message(assistant_message)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    except Exception as e:
        logger.error(f"Error in stream_chat_message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error streaming response: {str(e)}",
        )


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_chat_message(
    session_id: str, request: ChatMessageRequest, chat_db: ChatDB = Depends(get_chat_db)
):
    """Send a message to the chat and get a response from the LLM (non-streaming)"""
    try:
        # Verify the session exists
        session = await chat_db.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat session with ID {session_id} not found",
            )

        # Save user message to database
        user_message_data = {
            "role": MessageRole.USER,
            "content": request.message,
            "chat_id": ObjectId(session_id),
            "timestamp": datetime.datetime.utcnow(),
            "metadata": request.metadata or {},
        }
        user_message = await chat_db.add_message(user_message_data)

        # Get system prompt from session
        system_prompt = session.get("system_prompt")

        # Get previous messages for context
        previous_messages = await chat_db.get_messages(session_id, limit=20)

        # Format messages for the LLM
        formatted_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in previous_messages
            if msg["role"]
            != MessageRole.SYSTEM  # System messages are handled separately
        ]

        # Use model from request or session
        model_type = request.model or session.get("model") or ChatModelType.DEFAULT

        # Get response from LLM
        llm_response = await llm_service.get_llm_response(
            messages=formatted_messages,
            model_type=model_type,
            system_prompt=system_prompt,
        )

        # Extract message and formatted_data from the response
        message_content = llm_response.get("message", "")
        formatted_data = llm_response.get("formatted_data")

        # Save assistant's response to database
        message_id = str(ObjectId())
        assistant_message = {
            "role": MessageRole.ASSISTANT,
            "content": message_content,
            "chat_id": ObjectId(session_id),
            "timestamp": datetime.datetime.utcnow(),
            "metadata": {
                "model": model_type,
                "tokens": llm_service.estimate_tokens(message_content),
            },
            "_id": ObjectId(message_id),
        }
        await chat_db.add_message(assistant_message)

        # Update session metadata
        await chat_db.update_session(
            session_id,
            {
                "updated_at": datetime.datetime.utcnow(),
                "message_count": (session.get("message_count") or 0) + 2,
            },
        )

        # Return the formatted response
        return ChatMessageResponse(
            message=message_content,
            chat_id=session_id,
            message_id=message_id,
            timestamp=assistant_message["timestamp"],
            model=model_type,
            metadata=assistant_message.get("metadata"),
            formatted_data=formatted_data,
        )

    except Exception as e:
        logger.error(f"Error in send_chat_message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting response from language model: {str(e)}",
        )


@router.get("/search", response_model=List[Message])
async def search_chat_messages(
    query: str,
    user_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    chat_db: ChatDB = Depends(get_chat_db),
):
    """Search for chat messages containing the query text"""
    if not query or len(query.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must be at least 3 characters",
        )

    messages = await chat_db.search_messages(query, user_id, limit)
    return messages


@router.post("/", response_model=ChatMessageResponse)
async def quick_chat(
    message_request: ChatMessageRequest, chat_db: ChatDB = Depends(get_chat_db)
):
    """
    Quick chat endpoint - creates a new session and sends a message in one request.
    Useful for simple one-off questions without managing sessions.
    """
    # Create a new session
    session_data = {
        "title": (
            message_request.message[:50] + "..."
            if len(message_request.message) > 50
            else message_request.message
        ),
        "user_id": (
            message_request.metadata.get("user_id")
            if message_request.metadata
            else None
        ),
        "model": message_request.model or ChatModelType.DEFAULT,
        "system_prompt": message_request.system_prompt,
    }

    session = await chat_db.create_session(session_data)
    session_id = str(session["_id"])

    # Use the regular message endpoint
    return await send_chat_message(session_id, message_request, chat_db)


@router.get("/test", response_class=HTMLResponse)
async def chat_test_page():
    """Serve a test page for the chat interface"""
    with open("app/chat/templates/chat.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)
