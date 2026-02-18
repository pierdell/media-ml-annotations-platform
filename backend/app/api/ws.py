"""WebSocket endpoints for real-time collaboration."""

import json
import uuid

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.services.auth import decode_access_token, get_user_by_id
from app.services.websocket import get_connection_manager
from app.database import async_session

logger = structlog.get_logger()

router = APIRouter(tags=["websocket"])


async def _authenticate_ws(token: str) -> tuple[str, str] | None:
    """Validate token and return (user_id, user_name) or None."""
    user_id = decode_access_token(token)
    if not user_id:
        return None
    async with async_session() as db:
        user = await get_user_by_id(db, user_id)
        if user and user.is_active:
            return str(user.id), user.full_name
    return None


@router.websocket("/ws/projects/{project_id}")
async def project_ws(websocket: WebSocket, project_id: uuid.UUID, token: str = Query(...)):
    """
    WebSocket for project-level real-time updates.

    Events received:
      - cursor_move: {type, x, y} - user cursor position
      - annotation_update: {type, item_id, annotation} - live annotation changes
      - chat: {type, message} - project chat

    Events broadcast:
      - user_joined / user_left
      - cursor_move (relayed)
      - annotation_created / annotation_updated / annotation_deleted
      - indexing_progress
      - media_uploaded
    """
    auth = await _authenticate_ws(token)
    if not auth:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    user_id, user_name = auth
    manager = get_connection_manager()
    pid = str(project_id)

    await manager.connect_project(websocket, pid, user_id, user_name)
    logger.info("ws_project_connected", project_id=pid, user_id=user_id)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "cursor_move":
                await manager.broadcast_project(pid, {
                    "type": "cursor_move",
                    "user_id": user_id,
                    "user_name": user_name,
                    "x": data.get("x"),
                    "y": data.get("y"),
                    "item_id": data.get("item_id"),
                }, exclude=user_id)

            elif msg_type == "annotation_update":
                await manager.broadcast_project(pid, {
                    "type": "annotation_update",
                    "user_id": user_id,
                    "user_name": user_name,
                    "item_id": data.get("item_id"),
                    "annotation": data.get("annotation"),
                }, exclude=user_id)

            elif msg_type == "chat":
                await manager.broadcast_project(pid, {
                    "type": "chat",
                    "user_id": user_id,
                    "user_name": user_name,
                    "message": data.get("message", ""),
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect_project(pid, user_id)
        await manager.broadcast_project(pid, {
            "type": "user_left",
            "user_id": user_id,
            "user_name": user_name,
        })
        logger.info("ws_project_disconnected", project_id=pid, user_id=user_id)
    except Exception as e:
        manager.disconnect_project(pid, user_id)
        logger.error("ws_project_error", error=str(e))


@router.websocket("/ws/annotate/{item_id}")
async def annotation_ws(websocket: WebSocket, item_id: uuid.UUID, token: str = Query(...)):
    """
    WebSocket for co-annotation of a specific dataset item.

    Real-time annotation collaboration:
      - See other annotators' cursors
      - Live annotation previews
      - Lock regions to avoid conflicts
    """
    auth = await _authenticate_ws(token)
    if not auth:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    user_id, user_name = auth
    manager = get_connection_manager()
    iid = str(item_id)

    await manager.connect_annotation(websocket, iid, user_id, user_name)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "cursor_move":
                await manager.broadcast_annotation(iid, {
                    "type": "cursor_move",
                    "user_id": user_id,
                    "user_name": user_name,
                    "x": data.get("x"),
                    "y": data.get("y"),
                }, exclude=user_id)

            elif msg_type == "annotation_preview":
                await manager.broadcast_annotation(iid, {
                    "type": "annotation_preview",
                    "user_id": user_id,
                    "user_name": user_name,
                    "annotation": data.get("annotation"),
                }, exclude=user_id)

            elif msg_type == "annotation_committed":
                await manager.broadcast_annotation(iid, {
                    "type": "annotation_committed",
                    "user_id": user_id,
                    "user_name": user_name,
                    "annotation": data.get("annotation"),
                })

            elif msg_type == "region_lock":
                await manager.broadcast_annotation(iid, {
                    "type": "region_lock",
                    "user_id": user_id,
                    "user_name": user_name,
                    "region": data.get("region"),
                })

            elif msg_type == "region_unlock":
                await manager.broadcast_annotation(iid, {
                    "type": "region_unlock",
                    "user_id": user_id,
                    "region": data.get("region"),
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect_annotation(iid, user_id)
        await manager.broadcast_annotation(iid, {
            "type": "annotator_left",
            "user_id": user_id,
            "user_name": user_name,
        })
    except Exception as e:
        manager.disconnect_annotation(iid, user_id)
        logger.error("ws_annotation_error", error=str(e))
