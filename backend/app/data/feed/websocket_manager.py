"""WebSocket stream manager with auto-reconnect and lifecycle management."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum

import structlog

from app.data.providers.base import BaseExchangeProvider

logger = structlog.get_logger(__name__)


class StreamStatus(StrEnum):
    """WebSocket stream status."""
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    RECONNECTING = "RECONNECTING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass
class StreamState:
    """Track state of a single WebSocket stream."""
    stream_id: str
    symbol: str
    timeframe: str
    status: StreamStatus = StreamStatus.STOPPED
    reconnect_count: int = 0
    last_message_time: float = 0.0
    error_count: int = 0
    task: asyncio.Task | None = field(default=None, repr=False)


class WebSocketManager:
    """Manages multiple WebSocket streams with auto-reconnect.

    Features:
    - Auto-reconnect with exponential backoff
    - Stream state tracking
    - Graceful shutdown
    - Configurable max reconnect attempts
    """

    MAX_RECONNECT_ATTEMPTS = 50
    BASE_RECONNECT_DELAY = 1.0  # seconds
    MAX_RECONNECT_DELAY = 60.0  # seconds
    HEARTBEAT_INTERVAL = 30.0   # seconds
    HEARTBEAT_TIMEOUT = 90.0    # seconds since last message

    def __init__(self, provider: BaseExchangeProvider) -> None:
        self._provider = provider
        self._streams: dict[str, StreamState] = {}
        self._running = False
        self._heartbeat_task: asyncio.Task | None = None

    @property
    def streams(self) -> dict[str, StreamState]:
        return dict(self._streams)

    @property
    def is_running(self) -> bool:
        return self._running

    def _stream_id(self, symbol: str, timeframe: str) -> str:
        return f"{symbol}:{timeframe}"

    async def start(self) -> None:
        """Start the WebSocket manager and heartbeat monitor."""
        if self._running:
            return
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("ws_manager.started")

    async def stop(self) -> None:
        """Stop all streams and the heartbeat monitor."""
        self._running = False

        # Cancel heartbeat
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Cancel all stream tasks
        for state in self._streams.values():
            if state.task and not state.task.done():
                state.task.cancel()
                try:
                    await state.task
                except asyncio.CancelledError:
                    pass
            state.status = StreamStatus.STOPPED

        self._streams.clear()
        logger.info("ws_manager.stopped")

    async def add_ohlcv_stream(
        self,
        symbol: str,
        timeframe: str,
        callback,  # async callable(Candle)
    ) -> str:
        """Add an OHLCV WebSocket stream.

        Args:
            symbol: Trading pair e.g. "BTC/USDT"
            timeframe: e.g. "1h"
            callback: Async function called with each new candle batch (raw CCXT data)

        Returns:
            Stream ID
        """
        sid = self._stream_id(symbol, timeframe)
        if sid in self._streams:
            logger.warning("ws_manager.stream_exists", stream_id=sid)
            return sid

        state = StreamState(stream_id=sid, symbol=symbol, timeframe=timeframe)
        self._streams[sid] = state

        if self._running:
            state.task = asyncio.create_task(
                self._run_ohlcv_stream(state, callback)
            )

        logger.info("ws_manager.stream_added", stream_id=sid, symbol=symbol, timeframe=timeframe)
        return sid

    async def remove_stream(self, stream_id: str) -> None:
        """Remove and stop a stream."""
        state = self._streams.pop(stream_id, None)
        if state and state.task and not state.task.done():
            state.task.cancel()
            try:
                await state.task
            except asyncio.CancelledError:
                pass
        logger.info("ws_manager.stream_removed", stream_id=stream_id)

    async def _run_ohlcv_stream(self, state: StreamState, callback) -> None:
        """Run a single OHLCV stream with auto-reconnect."""
        state.status = StreamStatus.STARTING

        while self._running and state.reconnect_count < self.MAX_RECONNECT_ATTEMPTS:
            try:
                state.status = StreamStatus.RUNNING
                state.error_count = 0

                while self._running:
                    raw_candles = await self._provider.watch_ohlcv(
                        state.symbol, state.timeframe
                    )
                    state.last_message_time = asyncio.get_event_loop().time()

                    try:
                        await callback(raw_candles, state.symbol, state.timeframe)
                    except Exception:
                        logger.exception(
                            "ws_manager.callback_error",
                            stream_id=state.stream_id,
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                state.error_count += 1
                state.reconnect_count += 1
                state.status = StreamStatus.RECONNECTING

                delay = min(
                    self.BASE_RECONNECT_DELAY * (2 ** min(state.reconnect_count, 6)),
                    self.MAX_RECONNECT_DELAY,
                )

                logger.warning(
                    "ws_manager.reconnecting",
                    stream_id=state.stream_id,
                    attempt=state.reconnect_count,
                    delay=delay,
                    error=str(e),
                )
                await asyncio.sleep(delay)

        if state.reconnect_count >= self.MAX_RECONNECT_ATTEMPTS:
            state.status = StreamStatus.ERROR
            logger.error(
                "ws_manager.max_reconnects",
                stream_id=state.stream_id,
                attempts=state.reconnect_count,
            )
        else:
            state.status = StreamStatus.STOPPED

    async def _heartbeat_loop(self) -> None:
        """Monitor stream health and log warnings for stale streams."""
        while self._running:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                now = asyncio.get_event_loop().time()

                for sid, state in self._streams.items():
                    if state.status == StreamStatus.RUNNING:
                        if state.last_message_time > 0:
                            elapsed = now - state.last_message_time
                            if elapsed > self.HEARTBEAT_TIMEOUT:
                                logger.warning(
                                    "ws_manager.stream_stale",
                                    stream_id=sid,
                                    seconds_since_last=round(elapsed, 1),
                                )
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("ws_manager.heartbeat_error")
