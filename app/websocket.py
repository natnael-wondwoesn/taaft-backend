from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional
import json
from .logger import logger


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[Dict[str, Any]] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(
            {"websocket": websocket, "user_id": None, "chat_id": None}
        )
        logger.info(
            f"New WebSocket connection, total connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        for i, connection in enumerate(self.active_connections):
            if connection["websocket"] == websocket:
                self.active_connections.pop(i)
                break
        logger.info(
            f"WebSocket disconnected, remaining connections: {len(self.active_connections)}"
        )

    def get_connection_by_websocket(
        self, websocket: WebSocket
    ) -> Optional[Dict[str, Any]]:
        for connection in self.active_connections:
            if connection["websocket"] == websocket:
                return connection
        return None

    def get_connections_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        return [conn for conn in self.active_connections if conn["user_id"] == user_id]

    def get_connections_by_chat(self, chat_id: str) -> List[Dict[str, Any]]:
        return [conn for conn in self.active_connections if conn["chat_id"] == chat_id]

    async def associate_user(self, websocket: WebSocket, user_id: str):
        conn = self.get_connection_by_websocket(websocket)
        if conn:
            conn["user_id"] = user_id
            logger.info(f"User {user_id} associated with WebSocket connection")

    async def associate_chat(self, websocket: WebSocket, chat_id: str):
        conn = self.get_connection_by_websocket(websocket)
        if conn:
            conn["chat_id"] = chat_id
            logger.info(f"Chat {chat_id} associated with WebSocket connection")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def send_personal_json(self, data: Dict[str, Any], websocket: WebSocket):
        await websocket.send_text(json.dumps(data))

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.get("websocket").send_text(message)

    async def broadcast_json(self, data: Dict[str, Any]):
        json_data = json.dumps(data)
        for connection in self.active_connections:
            await connection.get("websocket").send_text(json_data)

    async def broadcast_to_user(self, data: Dict[str, Any], user_id: str):
        json_data = json.dumps(data)
        connections = self.get_connections_by_user(user_id)
        for connection in connections:
            await connection.get("websocket").send_text(json_data)

    async def broadcast_to_chat(self, data: Dict[str, Any], chat_id: str):
        json_data = json.dumps(data)
        connections = self.get_connections_by_chat(chat_id)
        for connection in connections:
            await connection.get("websocket").send_text(json_data)

    async def send_streaming_chunk(
        self, content: str, chat_id: str, user_id: Optional[str] = None
    ):
        """Send a chunk of streaming content to either a specific user or all users in a chat"""
        data = {"type": "llm_chunk", "content": content, "chat_id": chat_id}

        # If user_id is provided, send only to that user
        if user_id:
            await self.broadcast_to_user(data, user_id)
        else:
            # Otherwise send to all users in this chat
            await self.broadcast_to_chat(data, chat_id)

    async def send_stream_end(
        self, message_id: str, chat_id: str, user_id: Optional[str] = None
    ):
        """Send a message that the stream has ended"""
        data = {"type": "stream_end", "message_id": message_id, "chat_id": chat_id}

        # If user_id is provided, send only to that user
        if user_id:
            await self.broadcast_to_user(data, user_id)
        else:
            # Otherwise send to all users in this chat
            await self.broadcast_to_chat(data, chat_id)


manager = ConnectionManager()
