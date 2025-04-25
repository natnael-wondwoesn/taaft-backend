# app/chat/database.py
"""
Database access for chat feature
Provides MongoDB collection access and helper functions for chat data
"""
from motor.motor_asyncio import AsyncIOMotorCollection
from ..database import database
from fastapi import Depends
from bson import ObjectId
import datetime
from typing import Dict, List, Optional, Any
import os


# Check for test mode
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"


# Get MongoDB collections
def get_chat_sessions_collection() -> AsyncIOMotorCollection:
    """Get the chat sessions collection"""
    return database.client.get_database("taaft_db").get_collection("chat_sessions")


def get_chat_messages_collection() -> AsyncIOMotorCollection:
    """Get the chat messages collection"""
    return database.client.get_database("taaft_db").get_collection("chat_messages")


# Helper class for chat database operations
class ChatDB:
    def __init__(
        self,
        sessions_collection: AsyncIOMotorCollection,
        messages_collection: AsyncIOMotorCollection,
    ):
        self.sessions = sessions_collection
        self.messages = messages_collection

    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new chat session"""
        # Add timestamps
        now = datetime.datetime.utcnow()
        session_data["created_at"] = now
        session_data["updated_at"] = now
        session_data["message_count"] = 0
        session_data["is_active"] = True

        # Insert into database
        result = await self.sessions.insert_one(session_data)

        # Return the created session
        session = await self.sessions.find_one({"_id": result.inserted_id})
        return session

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a chat session by ID"""
        try:
            return await self.sessions.find_one({"_id": ObjectId(session_id)})
        except:
            return None

    async def update_session(
        self, session_id: str, update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a chat session"""
        # Add updated timestamp
        update_data["updated_at"] = datetime.datetime.utcnow()

        # Update the session
        result = await self.sessions.update_one(
            {"_id": ObjectId(session_id)}, {"$set": update_data}
        )

        if result.modified_count == 0:
            return None

        # Return the updated session
        return await self.sessions.find_one({"_id": ObjectId(session_id)})

    async def increment_message_count(self, session_id: str) -> None:
        """Increment the message count for a session"""
        await self.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$inc": {"message_count": 1},
                "$set": {"updated_at": datetime.datetime.utcnow()},
            },
        )

    async def add_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new message to a chat session"""
        # Add timestamp if not present
        if "timestamp" not in message_data:
            message_data["timestamp"] = datetime.datetime.utcnow()

        # Insert into database
        result = await self.messages.insert_one(message_data)

        # Increment message count for the session
        await self.increment_message_count(message_data["chat_id"])

        # Return the created message
        message = await self.messages.find_one({"_id": result.inserted_id})
        return message

    async def get_messages(
        self, session_id: str, limit: int = 100, skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get messages for a chat session, ordered by timestamp"""
        # First fetch all messages ordered by timestamp
        cursor = self.messages.find({"chat_id": ObjectId(session_id)}).sort(
            "timestamp", 1
        )

        # Convert to list so we can filter
        all_messages = await cursor.to_list(length=None)

        # Filter out Algolia tool messages
        filtered_messages = []
        for message in all_messages:
            print(f"message: {message}")
            content = message.get("content", "")
            # Skip Algolia summary messages which have this specific format
            if message.get("role") == "assistant" and content.startswith(
                "Hey! Great News!"
            ):
                pass
            else:
                filtered_messages.append(message)

        # Apply skip and limit to the filtered list
        return filtered_messages[skip : skip + limit]

    async def get_user_sessions(
        self, user_id: str, limit: int = 20, skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all chat sessions for a user, ordered by most recent"""
        cursor = (
            self.sessions.find({"user_id": user_id})
            .sort("updated_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and all its messages"""
        # Delete the session
        session_result = await self.sessions.delete_one({"_id": ObjectId(session_id)})

        # Delete all messages for the session
        await self.messages.delete_many({"chat_id": ObjectId(session_id)})

        return session_result.deleted_count > 0

    async def archive_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Archive a chat session (mark as inactive)"""
        result = await self.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"is_active": False, "updated_at": datetime.datetime.utcnow()}},
        )

        if result.modified_count == 0:
            return None

        return await self.sessions.find_one({"_id": ObjectId(session_id)})

    async def search_messages(
        self, query: str, user_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search for messages containing the query text"""
        filter_query = {"content": {"$regex": query, "$options": "i"}}

        # If user_id is provided, only search their messages
        if user_id:
            # We need to find the user's session IDs first
            session_cursor = self.sessions.find({"user_id": user_id}, {"_id": 1})
            session_ids = await session_cursor.to_list(length=None)
            session_obj_ids = [session["_id"] for session in session_ids]

            # Then search messages in those sessions
            filter_query["chat_id"] = {"$in": session_obj_ids}

        # Execute the search
        cursor = self.messages.find(filter_query).limit(limit)
        messages = await cursor.to_list(length=limit)

        # For each message, get the session info
        for message in messages:
            session = await self.sessions.find_one({"_id": message["chat_id"]})
            if session:
                message["session_title"] = session.get("title", "Untitled Chat")

        return messages


# In-memory storage for test mode
class MockDB:
    def __init__(self):
        self.chat_sessions = {}
        self.chat_messages = {}
        self.session_counter = 1000
        self.message_counter = 1000

    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new chat session"""
        session_id = f"mock_session_{self.session_counter}"
        self.session_counter += 1

        # Add timestamps and default values
        session = session_data.copy()
        session["_id"] = session_id
        session["created_at"] = datetime.datetime.utcnow()
        session["updated_at"] = datetime.datetime.utcnow()
        session["message_count"] = 0
        session["is_active"] = True

        # Store in memory
        self.chat_sessions[session_id] = session
        return session

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a chat session by ID"""
        return self.chat_sessions.get(session_id)

    async def update_session(
        self, session_id: str, update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a chat session"""
        session = self.chat_sessions.get(session_id)
        if not session:
            return None

        # Update fields
        for key, value in update_data.items():
            session[key] = value

        # Update timestamp
        session["updated_at"] = datetime.datetime.utcnow()
        return session

    async def increment_message_count(self, session_id: str) -> None:
        """Increment the message count for a session"""
        session = self.chat_sessions.get(session_id)
        if session:
            session["message_count"] += 1
            session["updated_at"] = datetime.datetime.utcnow()

    async def add_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new message to a chat session"""
        message_id = f"mock_message_{self.message_counter}"
        self.message_counter += 1

        # Create message object
        message = message_data.copy()
        message["_id"] = message_id

        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.datetime.utcnow()

        # Store message
        self.chat_messages[message_id] = message

        # Update message count in session
        chat_id = message_data.get("chat_id")
        if isinstance(chat_id, str):
            await self.increment_message_count(chat_id)
        elif chat_id:
            await self.increment_message_count(str(chat_id))

        return message

    async def get_messages(
        self, session_id: str, limit: int = 100, skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get messages for a chat session, ordered by timestamp"""
        # Filter messages by session
        session_messages = [
            msg
            for msg in self.chat_messages.values()
            if str(msg.get("chat_id")) == str(session_id)
        ]

        # Sort by timestamp
        session_messages.sort(key=lambda x: x.get("timestamp", datetime.datetime.min))

        # Filter out Algolia tool messages
        filtered_messages = []
        for message in session_messages:
            content = message.get("content", "")
            # Skip Algolia summary messages which have this specific format
            if message.get("role") == "assistant" and content.startswith(
                "Hey! Great News! I have found Plenty of tools"
            ):
                continue

            filtered_messages.append(message)

        # Apply skip and limit
        return filtered_messages[skip : skip + limit]

    async def get_user_sessions(
        self, user_id: str, limit: int = 20, skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all chat sessions for a user, ordered by most recent"""
        # Filter sessions by user
        user_sessions = [
            session
            for session in self.chat_sessions.values()
            if session.get("user_id") == user_id
        ]

        # Sort by updated_at
        user_sessions.sort(
            key=lambda x: x.get("updated_at", datetime.datetime.min), reverse=True
        )

        # Apply skip and limit
        return user_sessions[skip : skip + limit]

    async def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and all its messages"""
        if session_id not in self.chat_sessions:
            return False

        # Delete session
        del self.chat_sessions[session_id]

        # Delete all messages for this session
        message_ids_to_delete = [
            msg_id
            for msg_id, msg in self.chat_messages.items()
            if str(msg.get("chat_id")) == str(session_id)
        ]

        for msg_id in message_ids_to_delete:
            del self.chat_messages[msg_id]

        return True

    async def archive_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Archive a chat session (mark as inactive)"""
        session = self.chat_sessions.get(session_id)
        if not session:
            return None

        session["is_active"] = False
        session["updated_at"] = datetime.datetime.utcnow()
        return session

    async def search_messages(
        self, query: str, user_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search for messages containing the query text"""
        # Filter messages containing the query
        matching_messages = [
            msg
            for msg in self.chat_messages.values()
            if query.lower() in str(msg.get("content", "")).lower()
        ]

        # If user_id is provided, filter by user's sessions
        if user_id:
            user_session_ids = [
                session["_id"]
                for session in self.chat_sessions.values()
                if session.get("user_id") == user_id
            ]

            matching_messages = [
                msg
                for msg in matching_messages
                if str(msg.get("chat_id")) in user_session_ids
            ]

        # Add session info
        for message in matching_messages:
            chat_id = str(message.get("chat_id"))
            session = self.chat_sessions.get(chat_id)
            if session:
                message["session_title"] = session.get("title", "Untitled Chat")

        # Apply limit
        return matching_messages[:limit]


# Create a mock database instance
mock_db = MockDB()


# Dependencies for FastAPI
async def get_chat_db():
    """Dependency for the ChatDB service"""
    if TEST_MODE:
        # Return mock database in test mode
        return mock_db
    else:
        # Return real database connection
        sessions_collection = get_chat_sessions_collection()
        messages_collection = get_chat_messages_collection()
        return ChatDB(sessions_collection, messages_collection)
