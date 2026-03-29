"""WebSocket connection manager for real-time streaming."""

from __future__ import annotations

import asyncio
import json
import time

import structlog
from fastapi import WebSocket, WebSocketDisconnect

from app.api.auth import decode_access_token

logger = structlog.get_logger(__name__)

HEARTBEAT_INTERVAL = 30  # seconds


class ConnectionManager:
    """Manages WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._heartbeat_task: asyncio.Task | None = None

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("ws.connected", total=self.active_count)

        # Start heartbeat if this is the first connection
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("ws.disconnected", total=self.active_count)

    async def broadcast(self, message: dict) -> None:
        """Send a message to all connected clients."""
        if not self._connections:
            return

        payload = json.dumps(message, default=str)
        disconnected = []

        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def send_personal(self, websocket: WebSocket, message: dict) -> None:
        """Send a message to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat to all clients."""
        while self._connections:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await self.broadcast({
                "type": "heartbeat",
                "timestamp": time.time(),
            })

    async def handle_client(self, websocket: WebSocket, token: str | None = None) -> None:
        """Handle a WebSocket client lifecycle.

        Args:
            token: JWT token for authentication. If not provided or invalid,
                   the connection is closed with code 4001.
        """
        if token:
            subject = decode_access_token(token)
            if subject is None:
                await websocket.close(code=4001, reason="Invalid or expired token")
                return
            logger.info("ws.authenticated", user=subject)
        else:
            await websocket.close(code=4001, reason="Authentication required")
            return

        await self.connect(websocket)
        try:
            while True:
                # Keep connection alive, handle client messages
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    msg_type = msg.get("type", "")
                    if msg_type == "ping":
                        await self.send_personal(websocket, {"type": "pong"})
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            self.disconnect(websocket)
        except Exception:
            self.disconnect(websocket)


# Global connection manager singleton
ws_manager = ConnectionManager()
