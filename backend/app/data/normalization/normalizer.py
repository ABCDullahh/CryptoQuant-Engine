"""Data normalization and Redis caching for market data."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import structlog
from redis.asyncio import Redis

from app.core.models import Candle, FundingRate, OrderBook
from app.db.redis_client import get_redis

logger = structlog.get_logger(__name__)

# Redis cache key patterns
CACHE_CANDLE = "candle:{symbol}:{timeframe}"
CACHE_ORDERBOOK = "orderbook:{symbol}"
CACHE_FUNDING = "funding:{symbol}"
CACHE_TICKER = "ticker:{symbol}"

# Cache TTL in seconds
CANDLE_TTL = 300      # 5 minutes
ORDERBOOK_TTL = 10    # 10 seconds
FUNDING_TTL = 3600    # 1 hour
TICKER_TTL = 30       # 30 seconds


class DataNormalizer:
    """Normalizes raw exchange data to Pydantic models and caches in Redis."""

    def __init__(self) -> None:
        self._redis: Redis | None = None

    async def _get_redis(self) -> Redis:
        if self._redis is None:
            self._redis = await get_redis()
        return self._redis

    def normalize_candle(self, raw: list, symbol: str, timeframe: str) -> Candle:
        """Convert raw CCXT OHLCV [ts_ms, o, h, l, c, v] to Candle model.

        Args:
            raw: CCXT format [timestamp_ms, open, high, low, close, volume]
            symbol: Trading pair e.g. "BTC/USDT"
            timeframe: e.g. "1h"
        """
        return Candle(
            time=datetime.fromtimestamp(raw[0] / 1000, tz=UTC),
            symbol=symbol,
            timeframe=timeframe,
            open=float(raw[1]),
            high=float(raw[2]),
            low=float(raw[3]),
            close=float(raw[4]),
            volume=float(raw[5]),
        )

    def normalize_candles(self, raw_list: list[list], symbol: str, timeframe: str) -> list[Candle]:
        """Convert list of raw OHLCV to Candle models, skipping invalid candles."""
        result: list[Candle] = []
        for raw in raw_list:
            candle = self.normalize_candle(raw, symbol, timeframe)
            if self._validate_candle(candle):
                result.append(candle)
        return result

    def _validate_candle(self, candle: Candle) -> bool:
        """Validate candle data integrity.

        Checks:
        - All OHLC prices > 0
        - high >= low
        - high >= open and high >= close
        - low <= open and low <= close
        - volume >= 0
        - No NaN/None values

        Returns True if valid, False if invalid (logs warning).
        """
        values = [candle.open, candle.high, candle.low, candle.close, candle.volume]
        # Check for None or NaN
        for v in values:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                logger.warning(
                    "normalizer.invalid_candle",
                    symbol=candle.symbol,
                    reason="NaN or None value",
                )
                return False

        # All OHLC must be positive
        if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
            logger.warning(
                "normalizer.invalid_candle",
                symbol=candle.symbol,
                reason="non-positive price",
            )
            return False

        # Volume must be non-negative
        if candle.volume < 0:
            logger.warning(
                "normalizer.invalid_candle",
                symbol=candle.symbol,
                reason="negative volume",
            )
            return False

        # OHLC invariants
        if candle.high < candle.low:
            logger.warning(
                "normalizer.invalid_candle",
                symbol=candle.symbol,
                reason="high < low",
            )
            return False
        if candle.high < candle.open or candle.high < candle.close:
            logger.warning(
                "normalizer.invalid_candle",
                symbol=candle.symbol,
                reason="high < open or high < close",
            )
            return False
        if candle.low > candle.open or candle.low > candle.close:
            logger.warning(
                "normalizer.invalid_candle",
                symbol=candle.symbol,
                reason="low > open or low > close",
            )
            return False

        return True

    def normalize_order_book(self, raw: dict, symbol: str) -> OrderBook:
        """Convert raw CCXT order book to OrderBook model.

        Args:
            raw: CCXT format {bids: [[price, qty], ...], asks: [[price, qty], ...], timestamp: ms}
        """
        timestamp_ms = raw.get("timestamp") or raw.get("datetime")
        if isinstance(timestamp_ms, (int, float)):
            ts = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
        elif isinstance(timestamp_ms, str):
            ts = datetime.fromisoformat(timestamp_ms.replace("Z", "+00:00"))
        else:
            ts = datetime.now(tz=UTC)

        return OrderBook(
            symbol=symbol,
            timestamp=ts,
            bids=[(float(b[0]), float(b[1])) for b in raw.get("bids", [])],
            asks=[(float(a[0]), float(a[1])) for a in raw.get("asks", [])],
        )

    def normalize_funding_rate(self, raw: dict, symbol: str) -> FundingRate:
        """Convert raw CCXT funding rate to FundingRate model.

        Args:
            raw: CCXT format {fundingRate: float, fundingTimestamp: int, ...}
        """
        ts_ms = raw.get("fundingTimestamp") or raw.get("timestamp")
        if isinstance(ts_ms, (int, float)):
            ts = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        else:
            ts = datetime.now(tz=UTC)

        next_ts = raw.get("nextFundingTimestamp")
        next_dt = None
        if isinstance(next_ts, (int, float)):
            next_dt = datetime.fromtimestamp(next_ts / 1000, tz=UTC)

        return FundingRate(
            symbol=symbol,
            timestamp=ts,
            rate=float(raw.get("fundingRate", 0)),
            next_funding_time=next_dt,
        )

    async def cache_candle(self, candle: Candle) -> None:
        """Cache latest candle in Redis."""
        redis = await self._get_redis()
        key = CACHE_CANDLE.format(symbol=candle.symbol, timeframe=candle.timeframe)
        await redis.set(key, candle.model_dump_json(), ex=CANDLE_TTL)

    async def cache_order_book(self, ob: OrderBook) -> None:
        """Cache latest order book in Redis."""
        redis = await self._get_redis()
        key = CACHE_ORDERBOOK.format(symbol=ob.symbol)
        await redis.set(key, ob.model_dump_json(), ex=ORDERBOOK_TTL)

    async def cache_funding_rate(self, fr: FundingRate) -> None:
        """Cache latest funding rate in Redis."""
        redis = await self._get_redis()
        key = CACHE_FUNDING.format(symbol=fr.symbol)
        await redis.set(key, fr.model_dump_json(), ex=FUNDING_TTL)

    async def get_cached_candle(self, symbol: str, timeframe: str) -> Candle | None:
        """Get cached candle from Redis."""
        redis = await self._get_redis()
        key = CACHE_CANDLE.format(symbol=symbol, timeframe=timeframe)
        data = await redis.get(key)
        if data:
            return Candle.model_validate_json(data)
        return None

    async def get_cached_order_book(self, symbol: str) -> OrderBook | None:
        """Get cached order book from Redis."""
        redis = await self._get_redis()
        key = CACHE_ORDERBOOK.format(symbol=symbol)
        data = await redis.get(key)
        if data:
            return OrderBook.model_validate_json(data)
        return None

    async def get_cached_funding_rate(self, symbol: str) -> FundingRate | None:
        """Get cached funding rate from Redis."""
        redis = await self._get_redis()
        key = CACHE_FUNDING.format(symbol=symbol)
        data = await redis.get(key)
        if data:
            return FundingRate.model_validate_json(data)
        return None
