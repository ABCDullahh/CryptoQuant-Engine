"""Unit tests for WebSocketManager - init, start, stop, add/remove streams.

asyncio.sleep patched with CancelledError so heartbeat loop exits immediately.
No real long-running tasks are created.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.data.feed.websocket_manager import StreamState, StreamStatus, WebSocketManager
from app.data.providers.base import BaseExchangeProvider

# Patch asyncio.sleep in the websocket_manager module so no real waits occur
_PATCH_SLEEP = "app.data.feed.websocket_manager.asyncio.sleep"


@pytest.fixture
def mock_provider():
    provider = AsyncMock(spec=BaseExchangeProvider)
    provider.watch_ohlcv = AsyncMock(
        return_value=[[1700000000000, 43000, 43500, 42900, 43200, 100]]
    )
    return provider


@pytest.fixture
def manager(mock_provider):
    return WebSocketManager(mock_provider)


def test_init(mock_provider):
    mgr = WebSocketManager(mock_provider)
    assert mgr._provider is mock_provider
    assert mgr._streams == {}
    assert mgr._running is False
    assert mgr._heartbeat_task is None
    assert mgr.is_running is False


def test_stream_id_format(manager):
    assert manager._stream_id("BTC/USDT", "1h") == "BTC/USDT:1h"
    assert manager._stream_id("ETH/USDT", "15m") == "ETH/USDT:15m"


async def test_start(manager):
    with patch(_PATCH_SLEEP, side_effect=asyncio.CancelledError):
        await manager.start()
        assert manager._running is True
        assert manager.is_running is True
        assert manager._heartbeat_task is not None
        assert isinstance(manager._heartbeat_task, asyncio.Task)
        await manager.stop()


async def test_start_already_running(manager):
    with patch(_PATCH_SLEEP, side_effect=asyncio.CancelledError):
        await manager.start()
        first_heartbeat = manager._heartbeat_task
        await manager.start()
        assert manager._heartbeat_task is first_heartbeat
        await manager.stop()


async def test_stop(manager, mock_provider):
    """Test stop cancels heartbeat and stream tasks."""
    # Mock watch_ohlcv to yield control then block (but sleep is patched so instant)
    mock_provider.watch_ohlcv = AsyncMock(side_effect=asyncio.CancelledError)

    with patch(_PATCH_SLEEP, side_effect=asyncio.CancelledError):
        await manager.start()
        callback = AsyncMock()
        sid = await manager.add_ohlcv_stream("BTC/USDT", "1h", callback)

        heartbeat_task = manager._heartbeat_task
        await manager.stop()

    assert manager._running is False
    assert manager._streams == {}
    assert heartbeat_task.cancelled() or heartbeat_task.done()


async def test_stop_without_start(manager):
    await manager.stop()
    assert manager._running is False


async def test_add_ohlcv_stream(manager):
    callback = AsyncMock()
    sid = await manager.add_ohlcv_stream("BTC/USDT", "1h", callback)
    assert sid == "BTC/USDT:1h"
    state = manager._streams[sid]
    assert isinstance(state, StreamState)
    assert state.status == StreamStatus.STOPPED
    assert state.task is None


async def test_add_ohlcv_stream_running(manager, mock_provider):
    """When manager is running, adding a stream creates a task."""
    mock_provider.watch_ohlcv = AsyncMock(side_effect=asyncio.CancelledError)

    with patch(_PATCH_SLEEP, side_effect=asyncio.CancelledError):
        await manager.start()
        callback = AsyncMock()
        sid = await manager.add_ohlcv_stream("BTC/USDT", "1h", callback)

        state = manager._streams[sid]
        assert state.task is not None
        assert isinstance(state.task, asyncio.Task)
        await manager.stop()


async def test_add_duplicate_stream(manager):
    sid1 = await manager.add_ohlcv_stream("BTC/USDT", "1h", AsyncMock())
    sid2 = await manager.add_ohlcv_stream("BTC/USDT", "1h", AsyncMock())
    assert sid1 == sid2
    assert len(manager._streams) == 1


async def test_add_multiple_different_streams(manager):
    cb = AsyncMock()
    sid1 = await manager.add_ohlcv_stream("BTC/USDT", "1h", cb)
    sid2 = await manager.add_ohlcv_stream("ETH/USDT", "1h", cb)
    sid3 = await manager.add_ohlcv_stream("BTC/USDT", "15m", cb)
    assert len(manager._streams) == 3


async def test_remove_stream(manager, mock_provider):
    """Remove a stream that has an active task."""
    mock_provider.watch_ohlcv = AsyncMock(side_effect=asyncio.CancelledError)

    with patch(_PATCH_SLEEP, side_effect=asyncio.CancelledError):
        await manager.start()
        sid = await manager.add_ohlcv_stream("BTC/USDT", "1h", AsyncMock())

        task = manager._streams[sid].task
        await manager.remove_stream(sid)

        assert sid not in manager._streams
        assert task.cancelled() or task.done()
        await manager.stop()


async def test_remove_stream_nonexistent(manager):
    await manager.remove_stream("nonexistent:stream")
    assert len(manager._streams) == 0


async def test_remove_stream_no_task(manager):
    sid = await manager.add_ohlcv_stream("BTC/USDT", "1h", AsyncMock())
    assert manager._streams[sid].task is None
    await manager.remove_stream(sid)
    assert sid not in manager._streams


async def test_streams_property_returns_copy(manager):
    await manager.add_ohlcv_stream("BTC/USDT", "1h", AsyncMock())
    external = manager.streams
    external["FAKE:stream"] = StreamState(stream_id="FAKE:stream", symbol="FAKE", timeframe="1m")
    external.pop("BTC/USDT:1h", None)
    assert len(manager._streams) == 1
    assert "BTC/USDT:1h" in manager._streams


def test_streams_property_empty(manager):
    assert manager.streams == {}
    assert manager.streams is not manager._streams
