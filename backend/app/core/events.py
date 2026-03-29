"""Redis Pub/Sub event bus for inter-component communication."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from typing import Any

import structlog
from redis.asyncio import Redis

from app.core.models import EventMessage
from app.db.redis_client import get_redis

logger = structlog.get_logger(__name__)


class EventBus:
    """Redis-based event bus for publishing and subscribing to events."""

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._subscribers: dict[str, list[Callable[..., Coroutine[Any, Any, None]]]] = {}
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def connect(self) -> None:
        """Connect to Redis."""
        self._redis = await get_redis()
        logger.info("event_bus.connected")

    async def publish(self, channel: str, event: EventMessage) -> int:
        """Publish an event to a channel. Returns number of subscribers that received it."""
        if self._redis is None:
            await self.connect()

        payload = event.model_dump_json()
        count = await self._redis.publish(channel, payload)
        logger.debug("event_bus.published", channel=channel, event_type=event.event_type, receivers=count)
        return count

    async def publish_raw(self, channel: str, data: dict) -> int:
        """Publish raw dict data to a channel."""
        if self._redis is None:
            await self.connect()

        payload = json.dumps(data, default=str)
        return await self._redis.publish(channel, payload)

    def subscribe(
        self,
        channel: str,
        handler: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        """Register a handler for a channel. Call before start()."""
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        self._subscribers[channel].append(handler)
        logger.info("event_bus.subscribed", channel=channel, handler=handler.__name__)

    def unsubscribe(
        self,
        channel: str,
        handler: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        """Remove a handler from a channel."""
        handlers = self._subscribers.get(channel, [])
        if handler in handlers:
            handlers.remove(handler)
            logger.info("event_bus.unsubscribed", channel=channel, handler=handler.__name__)

    async def start(self) -> None:
        """Start listening for events on all subscribed channels."""
        if not self._subscribers:
            logger.warning("event_bus.no_subscribers")
            return

        if self._redis is None:
            await self.connect()

        self._running = True
        pubsub = self._redis.pubsub()

        channels = list(self._subscribers.keys())
        await pubsub.subscribe(*channels)
        logger.info("event_bus.listening", channels=channels)

        task = asyncio.create_task(self._listen(pubsub))
        self._tasks.append(task)

    async def _listen(self, pubsub) -> None:
        """Internal listener loop."""
        while self._running:
            try:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message and message["type"] == "message":
                    channel = message["channel"]
                    data = message["data"]

                    handlers = self._subscribers.get(channel, [])
                    for handler in handlers:
                        try:
                            parsed = json.loads(data) if isinstance(data, str) else data
                            await handler(channel, parsed)
                        except Exception as exc:
                            logger.error(
                                "event_bus.handler_error",
                                channel=channel,
                                handler=handler.__name__,
                                error=str(exc),
                            )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("event_bus.listen_error", error=str(exc))
                await asyncio.sleep(1)

        await pubsub.unsubscribe()
        await pubsub.close()

    async def stop(self) -> None:
        """Stop the event bus."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        logger.info("event_bus.stopped")


# Global event bus singleton
event_bus = EventBus()
