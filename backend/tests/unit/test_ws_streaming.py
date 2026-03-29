"""Unit tests for WebSocketManager - streaming, reconnect, heartbeat.

All asyncio.sleep patched. MAX_RECONNECT_ATTEMPTS reduced to 3.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.data.feed.websocket_manager import StreamState, StreamStatus, WebSocketManager
from app.data.providers.base import BaseExchangeProvider

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
    mgr = WebSocketManager(mock_provider)
    mgr.MAX_RECONNECT_ATTEMPTS = 3  # reduce from 50 to save memory
    return mgr


async def test_run_ohlcv_stream_calls_callback(manager, mock_provider):
    raw_candles = [[1700000000000, 43000, 43500, 42900, 43200, 100]]
    call_count = 0

    async def limited_watch_ohlcv(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            manager._running = False
        return raw_candles

    mock_provider.watch_ohlcv = AsyncMock(side_effect=limited_watch_ohlcv)
    manager._running = True
    state = StreamState(stream_id="BTC/USDT:1h", symbol="BTC/USDT", timeframe="1h")
    callback = AsyncMock()

    await manager._run_ohlcv_stream(state, callback)

    callback.assert_called_with(raw_candles, "BTC/USDT", "1h")
    assert state.last_message_time > 0
    assert state.status == StreamStatus.STOPPED


async def test_run_ohlcv_stream_updates_status(manager, mock_provider):
    statuses_seen = []

    async def tracking_watch(*args, **kwargs):
        statuses_seen.append(state.status)
        manager._running = False
        return [[1700000000000, 43000, 43500, 42900, 43200, 100]]

    mock_provider.watch_ohlcv = AsyncMock(side_effect=tracking_watch)
    manager._running = True
    state = StreamState(stream_id="BTC/USDT:1h", symbol="BTC/USDT", timeframe="1h")
    callback = AsyncMock()

    await manager._run_ohlcv_stream(state, callback)

    assert StreamStatus.RUNNING in statuses_seen
    assert state.status == StreamStatus.STOPPED


async def test_run_ohlcv_stream_reconnects_on_error(manager, mock_provider):
    call_count = 0

    async def failing_watch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise ConnectionError("connection lost")
        manager._running = False
        return [[1700000000000, 43000, 43500, 42900, 43200, 100]]

    mock_provider.watch_ohlcv = AsyncMock(side_effect=failing_watch)
    manager._running = True
    state = StreamState(stream_id="BTC/USDT:1h", symbol="BTC/USDT", timeframe="1h")
    callback = AsyncMock()

    with patch(_PATCH_SLEEP, new_callable=AsyncMock):
        await manager._run_ohlcv_stream(state, callback)

    assert state.reconnect_count == 2
    assert callback.call_count == 1


async def test_run_ohlcv_stream_max_reconnects(manager, mock_provider):
    """Test max reconnect with reduced attempts (3 instead of 50)."""
    mock_provider.watch_ohlcv = AsyncMock(side_effect=ConnectionError("permanent failure"))
    manager._running = True
    state = StreamState(stream_id="BTC/USDT:1h", symbol="BTC/USDT", timeframe="1h")
    callback = AsyncMock()

    with patch(_PATCH_SLEEP, new_callable=AsyncMock):
        await manager._run_ohlcv_stream(state, callback)

    assert state.reconnect_count >= manager.MAX_RECONNECT_ATTEMPTS
    assert state.status == StreamStatus.ERROR
    callback.assert_not_called()


async def test_run_ohlcv_stream_exponential_backoff(manager, mock_provider):
    mock_provider.watch_ohlcv = AsyncMock(side_effect=ConnectionError("connection lost"))
    manager.MAX_RECONNECT_ATTEMPTS = 3
    manager._running = True
    state = StreamState(stream_id="BTC/USDT:1h", symbol="BTC/USDT", timeframe="1h")
    callback = AsyncMock()
    sleep_delays = []

    async def capture_sleep(delay):
        sleep_delays.append(delay)

    with patch(_PATCH_SLEEP, side_effect=capture_sleep):
        await manager._run_ohlcv_stream(state, callback)

    assert len(sleep_delays) == 3
    assert sleep_delays[0] == 2.0
    assert sleep_delays[1] == 4.0
    assert sleep_delays[2] == 8.0


async def test_run_ohlcv_stream_callback_error_does_not_crash(manager, mock_provider):
    call_count = 0

    async def one_shot_watch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            manager._running = False
        return [[1700000000000, 43000, 43500, 42900, 43200, 100]]

    mock_provider.watch_ohlcv = AsyncMock(side_effect=one_shot_watch)
    callback = AsyncMock(side_effect=ValueError("callback explosion"))
    manager._running = True
    state = StreamState(stream_id="BTC/USDT:1h", symbol="BTC/USDT", timeframe="1h")

    await manager._run_ohlcv_stream(state, callback)

    assert callback.call_count >= 1
    assert state.status == StreamStatus.STOPPED


async def test_run_ohlcv_stream_cancelled(manager, mock_provider):
    mock_provider.watch_ohlcv = AsyncMock(side_effect=asyncio.CancelledError)
    manager._running = True
    state = StreamState(stream_id="BTC/USDT:1h", symbol="BTC/USDT", timeframe="1h")
    callback = AsyncMock()

    await manager._run_ohlcv_stream(state, callback)

    assert state.status == StreamStatus.STOPPED
    callback.assert_not_called()


# --- Heartbeat ---


async def test_heartbeat_loop_detects_stale_stream(manager):
    manager._running = True
    state = StreamState(
        stream_id="BTC/USDT:1h", symbol="BTC/USDT", timeframe="1h",
        status=StreamStatus.RUNNING, last_message_time=1.0,
    )
    manager._streams["BTC/USDT:1h"] = state

    async def controlled_sleep(delay):
        manager._running = False

    with patch(_PATCH_SLEEP, side_effect=controlled_sleep):
        with patch("app.data.feed.websocket_manager.asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.time.return_value = 200.0
            await manager._heartbeat_loop()


async def test_heartbeat_loop_ignores_non_running_streams(manager):
    manager._running = True
    state = StreamState(
        stream_id="BTC/USDT:1h", symbol="BTC/USDT", timeframe="1h",
        status=StreamStatus.STOPPED, last_message_time=1.0,
    )
    manager._streams["BTC/USDT:1h"] = state

    async def controlled_sleep(delay):
        manager._running = False

    with patch(_PATCH_SLEEP, side_effect=controlled_sleep):
        await manager._heartbeat_loop()


async def test_heartbeat_loop_no_warning_fresh_stream(manager):
    manager._running = True
    state = StreamState(
        stream_id="BTC/USDT:1h", symbol="BTC/USDT", timeframe="1h",
        status=StreamStatus.RUNNING, last_message_time=199.0,
    )
    manager._streams["BTC/USDT:1h"] = state

    async def controlled_sleep(delay):
        manager._running = False

    with patch(_PATCH_SLEEP, side_effect=controlled_sleep):
        with patch("app.data.feed.websocket_manager.asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.time.return_value = 200.0
            await manager._heartbeat_loop()


# --- Models & constants ---


def test_stream_status_values():
    assert StreamStatus.STARTING == "STARTING"
    assert StreamStatus.RUNNING == "RUNNING"
    assert StreamStatus.RECONNECTING == "RECONNECTING"
    assert StreamStatus.STOPPED == "STOPPED"
    assert StreamStatus.ERROR == "ERROR"


def test_stream_state_defaults():
    state = StreamState(stream_id="X:1h", symbol="X", timeframe="1h")
    assert state.status == StreamStatus.STOPPED
    assert state.reconnect_count == 0
    assert state.task is None


def test_class_constants():
    assert WebSocketManager.MAX_RECONNECT_ATTEMPTS == 50
    assert WebSocketManager.BASE_RECONNECT_DELAY == 1.0
    assert WebSocketManager.MAX_RECONNECT_DELAY == 60.0
    assert WebSocketManager.HEARTBEAT_INTERVAL == 30.0
    assert WebSocketManager.HEARTBEAT_TIMEOUT == 90.0
