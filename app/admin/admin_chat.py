from fastapi import APIRouter, HTTPException, status, Depends, Query, Path
from typing import Dict, List, Optional, Any
from bson import ObjectId
from datetime import datetime, timedelta

from ..auth.dependencies import get_admin_user
from ..models.user import UserInDB
from ..chat.database import get_chat_db, ChatDB
from ..logger import logger

router = APIRouter(prefix="/admin/chat", tags=["admin"])


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_chat_session(
    session_id: str = Path(...),
    current_user: UserInDB = Depends(get_admin_user),
    chat_db: ChatDB = Depends(get_chat_db),
):
    """
    Delete a chat session and all its messages. Admin only.
    """
    # Validate session ID format
    if not ObjectId.is_valid(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID format"
        )

    # Delete the session
    success = await chat_db.delete_session(session_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    # Log the deletion
    logger.info(f"Chat session {session_id} deleted by admin {current_user.email}")

    return None


@router.get("/sessions", response_model=List[Dict[str, Any]])
async def admin_list_chat_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = None,
    current_user: UserInDB = Depends(get_admin_user),
    chat_db: ChatDB = Depends(get_chat_db),
):
    """
    List all chat sessions with pagination and optional filtering by user. Admin only.
    """
    # Access the sessions collection directly for more flexible querying
    filter_query = {}

    # Add user filter if provided
    if user_id:
        filter_query["user_id"] = user_id

    # Execute the query with pagination
    cursor = (
        chat_db.sessions.find(filter_query)
        .sort("updated_at", -1)
        .skip(skip)
        .limit(limit)
    )
    sessions = await cursor.to_list(length=limit)

    # Convert ObjectIds to strings for JSON response
    for session in sessions:
        session["_id"] = str(session["_id"])

        # Convert ObjectIds in any metadata
        if "metadata" in session and isinstance(session["metadata"], dict):
            for key, value in session["metadata"].items():
                if isinstance(value, ObjectId):
                    session["metadata"][key] = str(value)

    return sessions


@router.delete("/users/{user_id}/sessions", status_code=status.HTTP_200_OK)
async def admin_delete_user_chat_sessions(
    user_id: str = Path(...),
    current_user: UserInDB = Depends(get_admin_user),
    chat_db: ChatDB = Depends(get_chat_db),
):
    """
    Delete all chat sessions for a specific user. Admin only.
    """
    # Validate user ID format
    if not ObjectId.is_valid(user_id) and user_id != "all":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )

    # Find all sessions for this user
    if user_id == "all":
        # Delete all sessions (dangerous operation, admin only)
        cursor = chat_db.sessions.find({})
    else:
        # Delete sessions for specific user
        cursor = chat_db.sessions.find({"user_id": user_id})

    sessions = await cursor.to_list(length=None)
    session_ids = [str(session["_id"]) for session in sessions]

    # Delete each session
    deleted_count = 0
    for session_id in session_ids:
        success = await chat_db.delete_session(session_id)
        if success:
            deleted_count += 1

    # Log the bulk deletion
    if user_id == "all":
        logger.info(
            f"All {deleted_count} chat sessions deleted by admin {current_user.email}"
        )
    else:
        logger.info(
            f"{deleted_count} chat sessions for user {user_id} deleted by admin {current_user.email}"
        )

    return {
        "deleted_count": deleted_count,
        "message": f"Successfully deleted {deleted_count} chat sessions",
    }


@router.get("/sessions/stats", response_model=Dict[str, Any])
async def admin_get_chat_statistics(
    current_user: UserInDB = Depends(get_admin_user),
    chat_db: ChatDB = Depends(get_chat_db),
):
    """
    Get statistics about chat sessions. Admin only.
    """
    # Get total number of sessions
    total_sessions = await chat_db.sessions.count_documents({})

    # Get number of active sessions
    active_sessions = await chat_db.sessions.count_documents({"is_active": True})

    # Get total number of messages
    total_messages = await chat_db.messages.count_documents({})

    # Get unique users with chat sessions
    unique_users = await chat_db.sessions.distinct("user_id")
    unique_user_count = len([u for u in unique_users if u])  # Filter out None values

    # Get sessions created in the last 7 days
    one_week_ago = datetime.now() - timedelta(days=7)
    recent_sessions = await chat_db.sessions.count_documents(
        {"created_at": {"$gte": one_week_ago}}
    )

    # Get average messages per session
    avg_messages = (
        round(total_messages / total_sessions, 2) if total_sessions > 0 else 0
    )

    # Return all statistics
    return {
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "archived_sessions": total_sessions - active_sessions,
        "total_messages": total_messages,
        "unique_users": unique_user_count,
        "recent_sessions": recent_sessions,
        "avg_messages_per_session": avg_messages,
        "timestamp": datetime.now().isoformat(),
    }
