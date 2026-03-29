"""Candle data REST endpoint — fetches real OHLCV from Binance Futures.

Uses CCXT to fetch live historical candles directly from Binance USDM Futures.
Falls back to TimescaleDB if Binance is unreachable.
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user, get_db
from app.db.models import CandleModel

logger = structlog.get_logger(__name__)

router = APIRouter()

# Timeframe -> seconds mapping for since calculation
_TF_SECONDS: dict[str, int] = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800,
    "12h": 43200, "1d": 86400, "1w": 604800, "1M": 2592000,
}

# In-memory candle cache: (cache_key, timestamp, data)
_candle_cache: dict[str, tuple[float, list[dict]]] = {}
# Cache TTL per timeframe (shorter timeframes need fresher data)
_CACHE_TTL = {
    "1m": 10,    # 10 seconds
    "3m": 15,    # 15 seconds
    "5m": 30,    # 30 seconds
    "15m": 60,   # 1 minute
    "30m": 90,   # 1.5 minutes
    "1h": 120,   # 2 minutes
    "2h": 180,   # 3 minutes
    "4h": 300,   # 5 minutes
    "6h": 360,   # 6 minutes
    "8h": 420,   # 7 minutes
    "12h": 480,  # 8 minutes
    "1d": 600,   # 10 minutes
    "1w": 1800,  # 30 minutes
    "1M": 3600,  # 1 hour
}


async def _fetch_candles_from_binance(
    symbol: str, timeframe: str, limit: int, end_time: int | None = None
) -> list[dict]:
    """Fetch OHLCV candles from Binance Futures via CCXT REST.

    Args:
        symbol: Trading pair (e.g. BTC/USDT)
        timeframe: Candle timeframe (e.g. 1h)
        limit: Max number of candles to return
        end_time: Unix timestamp (seconds) — fetch candles ending before this time.
                  Used for infinite scroll / loading historical data.
    """
    from app.data.providers.exchange_factory import create_exchange

    # Convert display symbol to futures format: BTC/USDT -> BTC/USDT:USDT
    exchange_symbol = f"{symbol}:USDT" if ":USDT" not in symbol else symbol

    exchange = await create_exchange()
    try:
        await exchange.load_markets()

        params: dict = {}
        since: int | None = None

        if end_time is not None:
            # Calculate 'since' by going back (limit * timeframe_seconds) from end_time
            # Also set Binance-specific endTime param to get candles strictly before end_time
            end_time_ms = end_time * 1000
            params["endTime"] = end_time_ms
            tf_seconds = _TF_SECONDS.get(timeframe, 3600)
            since = end_time_ms - (limit * tf_seconds * 1000)

        ohlcv = await exchange.fetch_ohlcv(
            exchange_symbol, timeframe, since=since, limit=limit, params=params
        )

        candles = []
        for row in ohlcv:
            # CCXT OHLCV format: [timestamp_ms, open, high, low, close, volume]
            ts = int(row[0] / 1000)
            # If end_time specified, ensure we only return candles strictly before it
            if end_time is not None and ts >= end_time:
                continue
            candles.append({
                "time": ts,
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })

        return candles
    finally:
        await exchange.close()


async def _fetch_candles_from_db(
    symbol: str, timeframe: str, limit: int, db, end_time: int | None = None
) -> list[dict]:
    """Fallback: fetch candles from TimescaleDB."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    filters = [
        CandleModel.symbol == symbol,
        CandleModel.timeframe == timeframe,
    ]
    if end_time is not None:
        filters.append(CandleModel.time < datetime.fromtimestamp(end_time, tz=timezone.utc))

    stmt = (
        select(CandleModel)
        .where(*filters)
        .order_by(CandleModel.time.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = list(reversed(result.scalars().all()))

    return [
        {
            "time": int(row.time.timestamp()),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
        }
        for row in rows
    ]


@router.get("")
async def get_candles(
    symbol: str = Query(default="BTC/USDT", pattern=r"^[A-Za-z0-9]{2,20}(/[A-Za-z0-9]{2,10})?$"),
    timeframe: str = Query(default="1h", pattern=r"^(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d|1w|1M)$"),
    limit: int = Query(default=300, ge=1, le=5000),
    end_time: int | None = Query(default=None, description="Unix timestamp (seconds) — return candles before this time. Used for lazy-loading history."),
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Fetch historical candle data for chart display.

    Primary source: Binance Futures REST API (real exchange data).
    Fallback: TimescaleDB (locally stored candles).

    Returns candles sorted ascending by time (oldest first)
    for TradingView Lightweight Charts compatibility.

    When ``end_time`` is provided the response contains only candles
    with ``time < end_time``, enabling lazy-load of older history.
    """
    # Check cache first (only for requests without end_time — history loads are unique)
    cache_key = f"{symbol}:{timeframe}:{limit}:{end_time or 'latest'}"
    ttl = _CACHE_TTL.get(timeframe, 120)
    now = time.time()

    if cache_key in _candle_cache:
        cached_time, cached_data = _candle_cache[cache_key]
        if (now - cached_time) < ttl:
            return {
                "candles": cached_data,
                "symbol": symbol,
                "timeframe": timeframe,
                "source": "binance_cached",
            }

    # Try Binance REST API first
    try:
        candles = await _fetch_candles_from_binance(
            symbol, timeframe, limit, end_time=end_time
        )
        if candles:
            _candle_cache[cache_key] = (now, candles)
            return {
                "candles": candles,
                "symbol": symbol,
                "timeframe": timeframe,
                "source": "binance",
            }
    except Exception as exc:
        logger.warning(
            "candles.binance_fetch_failed",
            symbol=symbol,
            timeframe=timeframe,
            error=str(exc),
        )

    # Fallback to TimescaleDB
    candles = await _fetch_candles_from_db(
        symbol, timeframe, limit, db, end_time=end_time
    )
    source = "database" if candles else "empty"

    return {
        "candles": candles,
        "symbol": symbol,
        "timeframe": timeframe,
        "source": source,
    }
