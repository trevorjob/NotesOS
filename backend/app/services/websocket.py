"""
NotesOS - WebSocket Service
Real-time updates for collaborative note-taking.
"""

from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
import json


class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""

    def __init__(self):
        # course_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

        # websocket -> user_id mapping
        self.connection_users: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, course_id: str, user_id: str):
        """
        Accept a new WebSocket connection.

        Args:
            websocket: WebSocket instance
            course_id: Course to subscribe to
            user_id: Authenticated user ID
        """
        await websocket.accept()

        # Add to course room
        if course_id not in self.active_connections:
            self.active_connections[course_id] = set()

        self.active_connections[course_id].add(websocket)
        self.connection_users[websocket] = user_id

        # Notify others of new user
        await self.broadcast_to_course(
            course_id,
            {
                "type": "user_joined",
                "user_id": user_id,
                "timestamp": None,  # Will be set by client
            },
            exclude=websocket,
        )

    def disconnect(self, websocket: WebSocket, course_id: str):
        """
        Remove a WebSocket connection.

        Args:
            websocket: WebSocket to disconnect
            course_id: Course the user was in
        """
        if course_id in self.active_connections:
            self.active_connections[course_id].discard(websocket)

            # Clean up empty course rooms
            if not self.active_connections[course_id]:
                del self.active_connections[course_id]

        # Get user ID before removing
        user_id = self.connection_users.pop(websocket, None)

        return user_id

    async def broadcast_to_course(
        self, course_id: str, message: dict, exclude: WebSocket = None
    ):
        """
        Broadcast message to all connections in a course.

        Args:
            course_id: Course to broadcast to
            message: Message dict (will be JSON serialized)
            exclude: Optional WebSocket to exclude from broadcast
        """
        if course_id not in self.active_connections:
            return

        # Serialize message
        message_json = json.dumps(message)

        # Send to all connections except excluded one
        dead_connections = []

        for connection in self.active_connections[course_id]:
            if connection == exclude:
                continue

            try:
                await connection.send_text(message_json)
            except WebSocketDisconnect:
                dead_connections.append(connection)
            except Exception:
                dead_connections.append(connection)

        # Clean up dead connections
        for dead in dead_connections:
            self.disconnect(dead, course_id)

    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """
        Send message to specific connection.

        Args:
            websocket: Target connection
            message: Message dict
        """
        try:
            await websocket.send_text(json.dumps(message))
        except Exception:
            pass

    def get_active_users(self, course_id: str) -> Set[str]:
        """
        Get set of active user IDs in a course.

        Args:
            course_id: Course to check

        Returns:
            Set of user IDs currently connected
        """
        if course_id not in self.active_connections:
            return set()

        users = set()
        for connection in self.active_connections[course_id]:
            user_id = self.connection_users.get(connection)
            if user_id:
                users.add(user_id)

        return users

    async def start_redis_listener(self):
        """Start listening for Redis messages to broadcast."""
        from app.services.redis_client import redis_client

        async for message in redis_client.subscribe("course_updates"):
            course_id = message.get("course_id")
            payload = message.get("message")

            if course_id and payload:
                await self.broadcast_to_course(course_id, payload)


# Singleton instance
connection_manager = ConnectionManager()


# Event types for broadcasting
async def broadcast_resource_created(course_id: str, resource_data: dict):
    """Broadcast when a new resource is created."""
    await connection_manager.broadcast_to_course(
        course_id, {"type": "resource_created", "data": resource_data}
    )


async def broadcast_resource_updated(course_id: str, resource_data: dict):
    """Broadcast when a resource is updated."""
    await connection_manager.broadcast_to_course(
        course_id, {"type": "resource_updated", "data": resource_data}
    )


async def broadcast_resource_deleted(course_id: str, resource_id: str):
    """Broadcast when a resource is deleted."""
    await connection_manager.broadcast_to_course(
        course_id, {"type": "resource_deleted", "resource_id": resource_id}
    )


async def broadcast_processing_status(course_id: str, resource_id: str, status: str):
    """
    Broadcast resource processing status (chunking/embedding progress).

    Args:
        course_id: Course ID
        resource_id: Resource being processed
        status: 'processing', 'completed', 'failed'
    """
    await connection_manager.broadcast_to_course(
        course_id,
        {"type": "processing_status", "resource_id": resource_id, "status": status},
    )
