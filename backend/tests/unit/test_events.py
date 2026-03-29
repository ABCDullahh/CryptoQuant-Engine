"""Unit tests for EventBus in backend/app/core/events.py"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import Redis

from app.core.events import EventBus, event_bus
from app.core.models import EventMessage


@pytest.fixture
def bus():
    """Create a fresh EventBus instance for testing."""
    return EventBus()


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock(spec=Redis)
    redis.publish = AsyncMock(return_value=1)
    redis.pubsub = MagicMock()
    return redis


def test_event_bus_init():
    """Test that a new EventBus starts with correct initial state."""
    b = EventBus()
    assert b._redis is None
    assert b._subscribers == {}
    assert b._tasks == []
    assert b._running is False


def test_subscribe_registers_handler(bus):
    """Test subscribe adds a handler to _subscribers."""
    async def handler(channel, data):
        pass

    bus.subscribe("test_channel", handler)

    assert "test_channel" in bus._subscribers
    assert handler in bus._subscribers["test_channel"]
    assert len(bus._subscribers["test_channel"]) == 1


def test_subscribe_multiple_handlers(bus):
    """Test multiple handlers on the same channel."""
    async def handler1(channel, data):
        pass

    async def handler2(channel, data):
        pass

    bus.subscribe("test_channel", handler1)
    bus.subscribe("test_channel", handler2)

    assert len(bus._subscribers["test_channel"]) == 2
    assert handler1 in bus._subscribers["test_channel"]
    assert handler2 in bus._subscribers["test_channel"]


def test_subscribe_multiple_channels(bus):
    """Test handlers on different channels."""
    async def handler1(channel, data):
        pass

    async def handler2(channel, data):
        pass

    bus.subscribe("channel1", handler1)
    bus.subscribe("channel2", handler2)

    assert "channel1" in bus._subscribers
    assert "channel2" in bus._subscribers
    assert len(bus._subscribers) == 2


async def test_publish_calls_redis(bus, mock_redis):
    """Test publish calls redis.publish with correct payload."""
    bus._redis = mock_redis

    event = EventMessage(event_type="test_event", data={"key": "value"})
    count = await bus.publish("test_channel", event)

    assert count == 1
    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "test_channel"

    payload = call_args[0][1]
    parsed = json.loads(payload)
    assert parsed["event_type"] == "test_event"
    assert parsed["data"] == {"key": "value"}


async def test_publish_auto_connects(bus, mock_redis):
    """Test publish calls connect if _redis is None."""
    assert bus._redis is None

    with patch("app.core.events.get_redis", return_value=mock_redis):
        event = EventMessage(event_type="test_event", data={})
        await bus.publish("test_channel", event)

        assert bus._redis is not None
        mock_redis.publish.assert_called_once()


async def test_publish_raw_serializes_dict(bus, mock_redis):
    """Test publish_raw serializes dict to JSON."""
    bus._redis = mock_redis

    data = {"key": "value", "number": 42}
    count = await bus.publish_raw("test_channel", data)

    assert count == 1
    call_args = mock_redis.publish.call_args
    payload = call_args[0][1]
    parsed = json.loads(payload)
    assert parsed == data


async def test_stop_clears_tasks(bus):
    """Test stop sets _running to False and clears _tasks."""

    async def _dummy_coro():
        await asyncio.sleep(100)

    task = asyncio.create_task(_dummy_coro())
    bus._tasks.append(task)
    bus._running = True

    await bus.stop()

    assert bus._running is False
    assert bus._tasks == []
    assert task.cancelled()


async def test_start_without_subscribers_returns(bus):
    """Test start returns early when no subscribers."""
    assert bus._subscribers == {}

    await bus.start()

    assert bus._tasks == []
    assert bus._running is False


def test_global_event_bus_exists():
    """Test that the global event_bus singleton is an EventBus instance."""
    assert isinstance(event_bus, EventBus)
