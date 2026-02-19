"""WebSocket connection manager for real-time collaboration."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


class ConnectionManager:
    """Manages WebSocket connections per project and dataset for real-time collaboration."""

    def __init__(self):
        # project_id -> {user_id -> WebSocket}
        self._project_connections: dict[str, dict[str, WebSocket]] = {}
        # dataset_item_id -> {user_id -> WebSocket}
        self._annotation_sessions: dict[str, dict[str, WebSocket]] = {}
        # user_id -> user info
        self._user_info: dict[str, dict] = {}

    async def connect_project(self, ws: WebSocket, project_id: str, user_id: str, user_name: str):
        """Register a user to a project channel."""
        await ws.accept()
        if project_id not in self._project_connections:
            self._project_connections[project_id] = {}
        self._project_connections[project_id][user_id] = ws
        self._user_info[user_id] = {"name": user_name, "id": user_id}

        # Notify others
        await self.broadcast_project(project_id, {
            "type": "user_joined",
            "user_id": user_id,
            "user_name": user_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, exclude=user_id)

        # Send current user list to the newly connected user
        users = self._get_project_users(project_id)
        await self._send(ws, {"type": "user_list", "users": users})

    async def connect_annotation(self, ws: WebSocket, item_id: str, user_id: str, user_name: str):
        """Register a user to an annotation session (specific dataset item)."""
        await ws.accept()
        if item_id not in self._annotation_sessions:
            self._annotation_sessions[item_id] = {}
        self._annotation_sessions[item_id][user_id] = ws
        self._user_info[user_id] = {"name": user_name, "id": user_id}

        await self.broadcast_annotation(item_id, {
            "type": "annotator_joined",
            "user_id": user_id,
            "user_name": user_name,
            "item_id": item_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, exclude=user_id)

    def disconnect_project(self, project_id: str, user_id: str):
        """Remove a user from a project channel."""
        if project_id in self._project_connections:
            self._project_connections[project_id].pop(user_id, None)
            if not self._project_connections[project_id]:
                del self._project_connections[project_id]

    def disconnect_annotation(self, item_id: str, user_id: str):
        """Remove a user from an annotation session."""
        if item_id in self._annotation_sessions:
            self._annotation_sessions[item_id].pop(user_id, None)
            if not self._annotation_sessions[item_id]:
                del self._annotation_sessions[item_id]

    async def broadcast_project(self, project_id: str, message: dict, exclude: str | None = None):
        """Send a message to all users in a project channel."""
        connections = self._project_connections.get(project_id, {})
        dead = []
        for uid, ws in connections.items():
            if uid == exclude:
                continue
            try:
                await self._send(ws, message)
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.disconnect_project(project_id, uid)

    async def broadcast_annotation(self, item_id: str, message: dict, exclude: str | None = None):
        """Send a message to all users annotating the same item."""
        connections = self._annotation_sessions.get(item_id, {})
        dead = []
        for uid, ws in connections.items():
            if uid == exclude:
                continue
            try:
                await self._send(ws, message)
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.disconnect_annotation(item_id, uid)

    def _get_project_users(self, project_id: str) -> list[dict]:
        connections = self._project_connections.get(project_id, {})
        return [
            self._user_info.get(uid, {"id": uid, "name": "Unknown"})
            for uid in connections
        ]

    def get_annotation_users(self, item_id: str) -> list[dict]:
        connections = self._annotation_sessions.get(item_id, {})
        return [
            self._user_info.get(uid, {"id": uid, "name": "Unknown"})
            for uid in connections
        ]

    async def _send(self, ws: WebSocket, data: dict):
        await ws.send_json(data)


# Singleton
_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
