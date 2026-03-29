"""Bridge between Redis EventBus and WebSocket broadcast.

Subscribes to key EventBus channels and broadcasts updates to
all connected WebSocket clients via the ConnectionManager.
"""

from __future__ import annotations

import structlog

from app.api.websocket import ws_manager
from app.config.constants import EventChannel
from app.core.events import event_bus

logger = structlog.get_logger(__name__)

# Map EventBus channels to WebSocket message types
_CHANNEL_WS_TYPE_MAP = {
    EventChannel.SIGNAL_COMPOSITE: "signal_new",
    EventChannel.ORDER_FILLED: "position_update",
    EventChannel.RISK_ALERT: "bot_status",
    EventChannel.POSITION_CLOSED: "position_update",
    EventChannel.BOT_STATUS: "bot_status",
    "price.update": "price_update",
    "orderbook.update": "orderbook_update",
    "backtest.progress": "backtest_progress",
}


async def _on_event(channel: str, data: dict) -> None:
    """Handle an event from the EventBus and broadcast to WebSocket clients."""
    ws_type = _CHANNEL_WS_TYPE_MAP.get(channel, "event")
    message = {"type": ws_type, "data": data}
    await ws_manager.broadcast(message)
    logger.debug("ws_bridge.broadcast", ws_type=ws_type, channel=channel)


async def start_ws_bridge() -> None:
    """Subscribe to EventBus channels and start listening."""
    for channel in _CHANNEL_WS_TYPE_MAP:
        event_bus.subscribe(channel, _on_event)
    logger.info("ws_bridge.started", channels=list(_CHANNEL_WS_TYPE_MAP.keys()))


async def stop_ws_bridge() -> None:
    """Stop the EventBus (unsubscribe all)."""
    await event_bus.stop()
    logger.info("ws_bridge.stopped")
