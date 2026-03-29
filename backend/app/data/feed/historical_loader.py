"""Historical OHLCV data loader with pagination and gap filling."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config.constants import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAMES
from app.db.database import async_session_factory
from app.db.models import CandleModel
from app.data.normalization.normalizer import DataNormalizer
from app.data.providers.base import BaseExchangeProvider

logger = structlog.get_logger(__name__)

# Timeframe to timedelta mapping
TIMEFRAME_DELTA = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}

# Max candles per request (Binance limit)
MAX_CANDLES_PER_REQUEST = 1000

# Delay between requests to avoid rate limiting
REQUEST_DELAY = 0.2  # seconds


class HistoricalLoader:
    """Loads historical OHLCV data from exchange and stores in TimescaleDB.

    Features:
    - Paginated fetching with rate limiting
    - Gap detection: finds missing candles
    - Upsert to avoid duplicates (ON CONFLICT DO NOTHING)
    """

    def __init__(
        self,
        provider: BaseExchangeProvider,
        normalizer: DataNormalizer,
    ) -> None:
        self._provider = provider
        self._normalizer = normalizer

    async def load_history(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime | None = None,
    ) -> int:
        """Load historical candles for a symbol/timeframe range.

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            start: Start datetime (UTC)
            end: End datetime (UTC), defaults to now

        Returns:
            Number of candles stored
        """
        if end is None:
            end = datetime.now(tz=UTC)

        total_stored = 0
        since_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        logger.info(
            "historical.loading",
            symbol=symbol,
            timeframe=timeframe,
            start=start.isoformat(),
            end=end.isoformat(),
        )

        while since_ms < end_ms:
            try:
                raw_candles = await self._provider.fetch_ohlcv(
                    symbol, timeframe, since=since_ms, limit=MAX_CANDLES_PER_REQUEST
                )

                if not raw_candles:
                    break

                candles = self._normalizer.normalize_candles(raw_candles, symbol, timeframe)
                stored = await self._store_candles(candles)
                total_stored += stored

                # Move since to after the last candle
                last_ts_ms = raw_candles[-1][0]
                since_ms = last_ts_ms + 1

                logger.debug(
                    "historical.batch",
                    symbol=symbol,
                    timeframe=timeframe,
                    fetched=len(candles),
                    stored=stored,
                )

                # Rate limit
                await asyncio.sleep(REQUEST_DELAY)

                # If we got fewer candles than limit, we've reached the end
                if len(raw_candles) < MAX_CANDLES_PER_REQUEST:
                    break

            except Exception:
                logger.exception(
                    "historical.fetch_error",
                    symbol=symbol,
                    timeframe=timeframe,
                    since_ms=since_ms,
                )
                break

        logger.info(
            "historical.complete",
            symbol=symbol,
            timeframe=timeframe,
            total_stored=total_stored,
        )
        return total_stored

    async def load_all_defaults(self, days_back: int = 90) -> dict[str, int]:
        """Load history for all default symbols and timeframes.

        Args:
            days_back: Number of days of history to load

        Returns:
            Dict of "symbol:timeframe" -> candles stored
        """
        start = datetime.now(tz=UTC) - timedelta(days=days_back)
        results = {}

        for symbol in DEFAULT_SYMBOLS:
            for tf in DEFAULT_TIMEFRAMES:
                key = f"{symbol}:{tf}"
                try:
                    count = await self.load_history(symbol, str(tf), start)
                    results[key] = count
                except Exception:
                    logger.exception("historical.load_default_error", key=key)
                    results[key] = 0

        return results

    async def get_latest_candle_time(self, symbol: str, timeframe: str) -> datetime | None:
        """Get the timestamp of the most recent candle in DB for a symbol/timeframe."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(func.max(CandleModel.time)).where(
                    CandleModel.symbol == symbol,
                    CandleModel.timeframe == timeframe,
                )
            )
            return result.scalar_one_or_none()

    async def fill_gaps(self, symbol: str, timeframe: str) -> int:
        """Detect and fill gaps in stored candle data.

        Returns:
            Number of candles filled
        """
        latest = await self.get_latest_candle_time(symbol, timeframe)
        if latest is None:
            return 0

        delta = TIMEFRAME_DELTA.get(timeframe)
        if delta is None:
            return 0

        # Load from latest stored candle to now
        return await self.load_history(symbol, timeframe, latest, datetime.now(tz=UTC))

    async def _store_candles(self, candles: list) -> int:
        """Store candles in TimescaleDB using upsert (ON CONFLICT DO NOTHING).

        Returns:
            Number of rows inserted
        """
        if not candles:
            return 0

        async with async_session_factory() as session:
            rows = []
            for c in candles:
                rows.append({
                    "time": c.time,
                    "symbol": c.symbol,
                    "timeframe": c.timeframe,
                    "exchange": "binance",
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                    "quote_volume": c.quote_volume,
                    "trades_count": c.trades_count,
                })

            stmt = pg_insert(CandleModel).values(rows)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["time", "symbol", "timeframe"]
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount if result.rowcount else len(rows)
