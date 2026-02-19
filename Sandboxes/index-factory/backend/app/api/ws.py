"""WebSocket endpoint for real-time indexing status updates."""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.config import get_settings

router = APIRouter()
settings = get_settings()

# Simple in-memory connection manager
_connections: dict[str, list[WebSocket]] = {}


class ConnectionManager:
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        _connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in _connections:
            _connections[user_id] = [ws for ws in _connections[user_id] if ws != websocket]

    async def send_to_user(self, user_id: str, message: dict):
        if user_id not in _connections:
            return
        dead = []
        for ws in _connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _connections[user_id].remove(ws)


manager = ConnectionManager()


@router.websocket("/ws/indexing/{user_id}")
async def indexing_ws(websocket: WebSocket, user_id: str):
    """
    WebSocket for live indexing status.
    Clients connect and receive messages like:
    - {"type": "indexing_started", "item_id": "...", "item_type": "image"}
    - {"type": "indexing_complete", "item_id": "...", "item_type": "document", "chunks": 5}
    - {"type": "auto_categorized", "item_id": "...", "node_name": "...", "confidence": 0.85}
    """
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive, handle pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


async def notify_indexing_started(user_id: str, item_id: str, item_type: str):
    await manager.send_to_user(user_id, {
        "type": "indexing_started",
        "item_id": item_id,
        "item_type": item_type,
    })


async def notify_indexing_complete(user_id: str, item_id: str, item_type: str, **extra):
    await manager.send_to_user(user_id, {
        "type": "indexing_complete",
        "item_id": item_id,
        "item_type": item_type,
        **extra,
    })


async def notify_auto_categorized(user_id: str, item_id: str, node_name: str, confidence: float):
    await manager.send_to_user(user_id, {
        "type": "auto_categorized",
        "item_id": item_id,
        "node_name": node_name,
        "confidence": confidence,
    })
