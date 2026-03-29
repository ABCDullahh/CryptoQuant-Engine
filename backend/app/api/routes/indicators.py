"""Indicator REST endpoint — computes technical indicators from Binance candle data.

Fetches candles via CCXT REST, converts to Candle models, runs IndicatorPipeline,
and returns indicator values keyed by timestamp.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import numpy as np
import structlog
from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user
from app.indicators.base import IndicatorPipeline
from app.indicators.trend import calc_ema, calc_macd, calc_sma, calc_adx
from app.indicators.momentum import calc_rsi, calc_stochastic
from app.indicators.volatility import calc_bollinger_bands, calc_atr
from app.indicators.volume import calc_vwap, calc_vwap_bands, calc_obv, calc_volume_sma, calc_mfi
from app.core.models import Candle

logger = structlog.get_logger(__name__)

router = APIRouter()

# In-memory indicator cache: (cache_key -> (timestamp, data))
_indicator_cache: dict[str, tuple[float, dict]] = {}

# Cache TTL per timeframe (match candles endpoint)
_CACHE_TTL = {
    "1m": 10,
    "3m": 15,
    "5m": 30,
    "15m": 60,
    "30m": 90,
    "1h": 120,
    "2h": 180,
    "4h": 300,
    "6h": 360,
    "8h": 420,
    "12h": 480,
    "1d": 600,
    "1w": 1800,
    "1M": 3600,
}

# Supported indicator names and their required output keys
_SUPPORTED_INDICATORS = {
    "ema_9", "ema_21", "ema_55", "ema_200",
    "sma_20", "sma_50", "sma_200",
    "rsi_14", "macd", "bb",
    "stoch", "adx", "atr", "vwap", "obv", "mfi", "vol_sma",
}


async def _fetch_candles_from_binance(
    symbol: str, timeframe: str, limit: int
) -> list[dict]:
    """Fetch OHLCV candles from Binance Futures via CCXT REST."""
    from app.data.providers.exchange_factory import create_exchange

    exchange_symbol = f"{symbol}:USDT" if ":USDT" not in symbol else symbol

    exchange = await create_exchange()
    try:
        await exchange.load_markets()
        ohlcv = await exchange.fetch_ohlcv(exchange_symbol, timeframe, limit=limit)

        candles = []
        for row in ohlcv:
            candles.append({
                "time": int(row[0] / 1000),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })

        return candles
    finally:
        await exchange.close()


def _compute_selected_indicators(
    candles: list[Candle],
    indicators: set[str],
) -> list[dict]:
    """Compute requested indicators and return per-timestamp dicts."""
    closes = np.array([c.close for c in candles], dtype=float)
    highs = np.array([c.high for c in candles], dtype=float)
    lows = np.array([c.low for c in candles], dtype=float)
    volumes = np.array([c.volume for c in candles], dtype=float)
    n = len(candles)

    computed: dict[str, np.ndarray] = {}

    # Support dynamic EMA/SMA/RSI periods: ema_N, sma_N, rsi_N
    for ind in indicators:
        if ind.startswith("ema_") and ind not in {"ema_9", "ema_21", "ema_55", "ema_200"}:
            try:
                period = int(ind.split("_")[1])
                computed[ind] = calc_ema(closes, period)
            except (IndexError, ValueError):
                pass
        elif ind.startswith("sma_") and ind not in {"sma_20", "sma_50", "sma_200"}:
            try:
                period = int(ind.split("_")[1])
                computed[ind] = calc_sma(closes, period)
            except (IndexError, ValueError):
                pass
        elif ind.startswith("rsi_") and ind != "rsi_14":
            try:
                period = int(ind.split("_")[1])
                computed[ind] = calc_rsi(closes, period)
            except (IndexError, ValueError):
                pass

    # Trend — EMA
    if "ema_9" in indicators:
        computed["ema_9"] = calc_ema(closes, 9)
    if "ema_21" in indicators:
        computed["ema_21"] = calc_ema(closes, 21)
    if "ema_55" in indicators:
        computed["ema_55"] = calc_ema(closes, 55)
    if "ema_200" in indicators:
        computed["ema_200"] = calc_ema(closes, 200)

    # Trend — SMA
    if "sma_20" in indicators:
        computed["sma_20"] = calc_sma(closes, 20)
    if "sma_50" in indicators:
        computed["sma_50"] = calc_sma(closes, 50)
    if "sma_200" in indicators:
        computed["sma_200"] = calc_sma(closes, 200)

    # Momentum — RSI
    if "rsi_14" in indicators:
        computed["rsi_14"] = calc_rsi(closes)

    # Trend — MACD
    if "macd" in indicators:
        macd_line, macd_signal, macd_hist = calc_macd(closes)
        computed["macd"] = macd_line
        computed["macd_signal"] = macd_signal
        computed["macd_histogram"] = macd_hist

    # Volatility — Bollinger Bands
    if "bb" in indicators:
        bb_upper, bb_middle, bb_lower = calc_bollinger_bands(closes)
        computed["bb_upper"] = bb_upper
        computed["bb_middle"] = bb_middle
        computed["bb_lower"] = bb_lower

    # Momentum — Stochastic
    if "stoch" in indicators:
        stoch_k, stoch_d = calc_stochastic(highs, lows, closes)
        computed["stoch_k"] = stoch_k
        computed["stoch_d"] = stoch_d

    # Trend — ADX
    if "adx" in indicators:
        computed["adx"] = calc_adx(highs, lows, closes)

    # Volatility — ATR
    if "atr" in indicators:
        computed["atr"] = calc_atr(highs, lows, closes)

    # Volume — VWAP with bands
    if "vwap" in indicators:
        vwap_line, vwap_upper, vwap_lower = calc_vwap_bands(highs, lows, closes, volumes)
        computed["vwap"] = vwap_line
        computed["vwap_upper"] = vwap_upper
        computed["vwap_lower"] = vwap_lower

    # Volume — OBV
    if "obv" in indicators:
        computed["obv"] = calc_obv(closes, volumes)

    # Volume — MFI
    if "mfi" in indicators:
        computed["mfi"] = calc_mfi(highs, lows, closes, volumes)

    # Volume — Volume SMA
    if "vol_sma" in indicators:
        computed["vol_sma"] = calc_volume_sma(volumes)

    # Build per-timestamp result
    results = []
    for i in range(n):
        row: dict = {
            "time": int(candles[i].time.timestamp()),
            "close": candles[i].close,
        }
        for key, arr in computed.items():
            val = arr[i]
            row[key] = None if np.isnan(val) else round(float(val), 6)
        results.append(row)

    return results


@router.get("")
async def get_indicators(
    symbol: str = Query(default="BTC/USDT", pattern=r"^[A-Za-z0-9]{2,20}(/[A-Za-z0-9]{2,10})?$"),
    timeframe: str = Query(default="1h", pattern=r"^(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d|1w|1M)$"),
    limit: int = Query(default=300, ge=1, le=5000),
    indicators: str = Query(default="ema_9,rsi_14,macd,bb"),
    user: str = Depends(get_current_user),
):
    """Compute technical indicators from live Binance candle data.

    Query params:
        symbol: Trading pair (default BTC/USDT)
        timeframe: Candle timeframe (default 1h)
        limit: Number of candles to fetch (default 300, max 1500)
        indicators: Comma-separated indicator names.
            Fixed-period: ema_9, ema_21, ema_55, ema_200, sma_20, sma_50, sma_200, rsi_14
            Dynamic-period: ema_N, sma_N, rsi_N (e.g. ema_50, sma_100, rsi_21)
            Trend: macd (gives macd, macd_signal, macd_histogram), adx
            Volatility: bb (gives bb_upper, bb_middle, bb_lower), atr
            Momentum: stoch (gives stoch_k, stoch_d)
            Volume: vwap, obv, mfi, vol_sma
    """
    requested = {s.strip().lower() for s in indicators.split(",") if s.strip()}

    # Check cache
    cache_key = f"ind:{symbol}:{timeframe}:{limit}:{','.join(sorted(requested))}"
    ttl = _CACHE_TTL.get(timeframe, 120)
    now = time.time()

    if cache_key in _indicator_cache:
        cached_time, cached_data = _indicator_cache[cache_key]
        if (now - cached_time) < ttl:
            return cached_data

    # Fetch candles from Binance
    raw_candles = await _fetch_candles_from_binance(symbol, timeframe, limit)

    if not raw_candles:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "indicators": list(requested),
            "data": [],
            "source": "empty",
        }

    # Convert to Candle models
    candle_models = [
        Candle(
            time=datetime.fromtimestamp(c["time"], tz=timezone.utc),
            symbol=symbol,
            timeframe=timeframe,
            open=c["open"],
            high=c["high"],
            low=c["low"],
            close=c["close"],
            volume=c["volume"],
        )
        for c in raw_candles
    ]

    # Compute
    data = _compute_selected_indicators(candle_models, requested)

    result = {
        "symbol": symbol,
        "timeframe": timeframe,
        "indicators": list(requested),
        "data": data,
        "source": "binance",
        "count": len(data),
    }

    _indicator_cache[cache_key] = (now, result)
    return result
