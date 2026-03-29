"""Data collection orchestrator - manages all market data streams."""

from __future__ import annotations

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config.constants import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAMES, EventChannel
from app.core.events import event_bus
from app.core.models import Candle, EventMessage, FundingRate
from app.db.database import async_session_factory
from app.db.models import CandleModel
from app.data.normalization.normalizer import DataNormalizer
from app.data.providers.binance import BinanceProvider
from app.data.feed.websocket_manager import WebSocketManager
from app.data.feed.rest_client import RestClient
from app.data.feed.historical_loader import HistoricalLoader

logger = structlog.get_logger(__name__)


class DataCollector:
    """Main data collection orchestrator.

    Coordinates:
    - Binance WebSocket streams (OHLCV per symbol/timeframe)
    - REST polling (funding rates)
    - Historical data loading
    - Data normalization, DB storage, Redis cache, event publishing
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        timeframes: list[str] | None = None,
    ) -> None:
        self._symbols = symbols or DEFAULT_SYMBOLS
        self._timeframes = timeframes or [str(tf) for tf in DEFAULT_TIMEFRAMES]

        # Sub-components
        self._provider = BinanceProvider()
        self._normalizer = DataNormalizer()
        self._ws_manager = WebSocketManager(self._provider)
        self._rest_client = RestClient(self._provider, self._normalizer, self._symbols)
        self._historical_loader = HistoricalLoader(self._provider, self._normalizer)

        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def provider(self) -> BinanceProvider:
        return self._provider

    @property
    def normalizer(self) -> DataNormalizer:
        return self._normalizer

    @property
    def historical_loader(self) -> HistoricalLoader:
        return self._historical_loader

    async def start(self) -> None:
        """Start all data collection streams."""
        if self._running:
            logger.warning("collector.already_running")
            return

        logger.info(
            "collector.starting",
            symbols=self._symbols,
            timeframes=self._timeframes,
        )

        # 1. Connect to exchange
        await self._provider.connect()

        # 2. Connect event bus
        await event_bus.connect()

        # 3. Start WebSocket manager
        await self._ws_manager.start()

        # 4. Add OHLCV streams for all symbol/timeframe pairs
        for symbol in self._symbols:
            for tf in self._timeframes:
                await self._ws_manager.add_ohlcv_stream(
                    symbol, tf, self._on_ohlcv_update
                )

        # 5. Start REST polling (funding rates)
        await self._rest_client.start()

        self._running = True
        logger.info("collector.started", stream_count=len(self._symbols) * len(self._timeframes))

    async def stop(self) -> None:
        """Stop all data collection streams."""
        logger.info("collector.stopping")
        self._running = False

        await self._rest_client.stop()
        await self._ws_manager.stop()
        await self._provider.close()

        logger.info("collector.stopped")

    async def load_historical(self, days_back: int = 90) -> dict[str, int]:
        """Load historical data for configured symbols/timeframes.

        Loads for both the collector's configured timeframes AND default
        timeframes (for multi-timeframe analysis). For 1m/5m, caps at
        1 day back to avoid excessive API calls.

        Args:
            days_back: Number of days of history to load

        Returns:
            Dict mapping "symbol:timeframe" to count of candles loaded
        """
        from datetime import UTC, datetime, timedelta

        if not self._provider.is_connected:
            await self._provider.connect()

        # Combine collector's timeframes with defaults (for strategy analysis)
        all_timeframes = set(self._timeframes) | {str(tf) for tf in DEFAULT_TIMEFRAMES}
        results = {}

        for symbol in self._symbols:
            for tf in all_timeframes:
                # Cap short timeframes to avoid excessive data
                if tf in ("1m", "3m"):
                    tf_days = min(days_back, 1)
                elif tf in ("5m", "15m"):
                    tf_days = min(days_back, 7)
                else:
                    tf_days = days_back

                start = datetime.now(tz=UTC) - timedelta(days=tf_days)
                key = f"{symbol}:{tf}"
                try:
                    count = await self._historical_loader.load_history(
                        symbol, tf, start
                    )
                    results[key] = count
                except Exception:
                    logger.warning("collector.history_load_error", key=key)
                    results[key] = 0

        return results

    async def get_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list[Candle]:
        """Get recent candles from DB, with exchange fallback.

        For strategy evaluation, we need a full history window (e.g. 200+ candles).
        The Redis cache only stores the latest single candle (for real-time display),
        so we always query TimescaleDB when limit > 1 to get the full series.

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            limit: Number of candles to fetch
        """
        # For single-candle requests, use cache for speed (e.g. price display)
        if limit == 1:
            cached = await self._normalizer.get_cached_candle(symbol, timeframe)
            if cached is not None:
                return [cached]

        # Query TimescaleDB for the full history window
        candles = await self._load_candles_from_db(symbol, timeframe, limit)
        if candles and len(candles) >= limit * 0.8:
            return candles

        # Fallback: fetch from exchange REST API if DB is empty or insufficient
        if not self._provider.is_connected:
            await self._provider.connect()
        raw = await self._provider.fetch_ohlcv(symbol, timeframe, limit=limit)
        return self._normalizer.normalize_candles(raw, symbol, timeframe)

    async def _load_candles_from_db(
        self, symbol: str, timeframe: str, limit: int
    ) -> list[Candle]:
        """Load candles from TimescaleDB, sorted ascending (oldest first)."""
        try:
            from sqlalchemy import select

            async with async_session_factory() as session:
                stmt = (
                    select(CandleModel)
                    .where(
                        CandleModel.symbol == symbol,
                        CandleModel.timeframe == timeframe,
                    )
                    .order_by(CandleModel.time.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()

            if not rows:
                return []

            # Convert to Candle models, sorted ascending (oldest first)
            candles = []
            for row in reversed(rows):
                candles.append(
                    Candle(
                        symbol=row.symbol,
                        timeframe=row.timeframe,
                        time=row.time,
                        open=float(row.open),
                        high=float(row.high),
                        low=float(row.low),
                        close=float(row.close),
                        volume=float(row.volume),
                        quote_volume=float(row.quote_volume) if row.quote_volume else 0,
                        trades_count=int(row.trades_count) if row.trades_count else 0,
                    )
                )
            return candles
        except Exception:
            logger.warning(
                "collector.db_load_error", symbol=symbol, timeframe=timeframe
            )
            return []

    async def get_funding_rate(self, symbol: str) -> FundingRate | None:
        """Get current funding rate - cache first, then exchange."""
        cached = await self._normalizer.get_cached_funding_rate(symbol)
        if cached:
            return cached
        return await self._rest_client.fetch_funding_rate(symbol)

    # --- Internal callbacks ---

    async def _on_ohlcv_update(
        self, raw_candles: list[list], symbol: str, timeframe: str
    ) -> None:
        """Called by WebSocketManager when new OHLCV data arrives.

        Flow: normalize → store DB → cache Redis → publish event
        """
        if not raw_candles:
            return

        # Process the latest candle (last in the list)
        candle = self._normalizer.normalize_candle(raw_candles[-1], symbol, timeframe)

        # Store in TimescaleDB
        await self._store_candle(candle)

        # Cache in Redis
        await self._normalizer.cache_candle(candle)

        # Publish event
        channel = EventChannel.MARKET_CANDLE.format(timeframe=timeframe)
        await event_bus.publish(
            channel,
            EventMessage(
                event_type="candle_update",
                data=candle.model_dump(mode="json"),
            ),
        )

    async def _store_candle(self, candle: Candle) -> None:
        """Store a single candle in TimescaleDB (upsert)."""
        try:
            async with async_session_factory() as session:
                stmt = pg_insert(CandleModel).values(
                    time=candle.time,
                    symbol=candle.symbol,
                    timeframe=candle.timeframe,
                    exchange="binance",
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                    quote_volume=candle.quote_volume,
                    trades_count=candle.trades_count,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["time", "symbol", "timeframe"],
                    set_={
                        "open": stmt.excluded.open,
                        "high": stmt.excluded.high,
                        "low": stmt.excluded.low,
                        "close": stmt.excluded.close,
                        "volume": stmt.excluded.volume,
                        "quote_volume": stmt.excluded.quote_volume,
                        "trades_count": stmt.excluded.trades_count,
                    },
                )
                await session.execute(stmt)
                await session.commit()
        except Exception as exc:
            logger.error(
                "collector.store_candle_error",
                symbol=candle.symbol,
                timeframe=candle.timeframe,
                error=str(exc),
            )
