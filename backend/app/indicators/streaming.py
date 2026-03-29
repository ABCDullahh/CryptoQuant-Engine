"""Streaming (incremental) indicator pipeline using talipp.

O(1) per-candle updates instead of O(n) full recomputation.
Used for LIVE trading. Batch IndicatorPipeline kept for backtesting.

Usage:
    pipeline = StreamingIndicatorPipeline()
    pipeline.initialize(historical_candles)  # warm-up
    # Then on each new candle:
    values = pipeline.add_candle(candle)     # O(1)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from app.core.models import Candle

try:
    from talipp.indicators import (
        EMA,
        SMA,
        RSI,
        MACD,
        BB,
        ADX,
        ATR,
        OBV,
        Stoch,
    )
    from talipp.ohlcv import OHLCV

    TALIPP_AVAILABLE = True
except ImportError:
    TALIPP_AVAILABLE = False
    logger.warning("talipp not installed — streaming indicators unavailable")


@dataclass
class StreamingValues:
    """Snapshot of all indicator values at a point in time."""

    close: float = 0.0
    ema_9: float | None = None
    ema_21: float | None = None
    ema_55: float | None = None
    ema_200: float | None = None
    sma_20: float | None = None
    rsi_14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    bb_width: float | None = None
    adx: float | None = None
    atr_14: float | None = None
    obv: float | None = None
    mfi: float | None = None
    stoch_k: float | None = None
    stoch_d: float | None = None
    volume_sma_20: float | None = None


class StreamingIndicatorPipeline:
    """O(1) incremental indicator computation using talipp.

    Initialize once with historical candles, then call add_candle()
    for each new candle — only the delta is computed.
    """

    def __init__(self) -> None:
        if not TALIPP_AVAILABLE:
            raise ImportError("talipp is required for streaming indicators: pip install talipp")

        # Price-based indicators
        self._ema_9 = EMA(period=9)
        self._ema_21 = EMA(period=21)
        self._ema_55 = EMA(period=55)
        self._ema_200 = EMA(period=200)
        self._sma_20 = SMA(period=20)
        self._rsi_14 = RSI(period=14)
        self._macd = MACD(fast_period=12, slow_period=26, signal_period=9)
        self._bb = BB(period=20, std_dev_mult=2.0)
        self._adx = ADX(di_period=14, adx_period=14)
        self._atr = ATR(period=14)

        # Volume-based indicators (OHLCV input)
        self._obv = OBV()
        self._stoch = Stoch(period=14, smoothing_period=3)

        # Volume SMA (manual — talipp SMA on volume)
        self._vol_sma = SMA(period=20)

        self._candle_count = 0
        self._initialized = False

    def initialize(self, candles: list[Candle]) -> StreamingValues | None:
        """Warm up all indicators with historical data.

        Args:
            candles: List of historical candles (oldest first).

        Returns:
            Latest indicator values after warm-up, or None if insufficient data.
        """
        if not candles:
            return None

        for candle in candles:
            self._feed_candle(candle)

        self._initialized = True
        self._candle_count = len(candles)
        logger.info(
            "streaming_pipeline.initialized",
            candles=len(candles),
        )
        return self._snapshot(candles[-1].close)

    def add_candle(self, candle: Candle) -> StreamingValues:
        """Add a single new candle — O(1) incremental update.

        Args:
            candle: New candle data.

        Returns:
            Updated indicator values.
        """
        self._feed_candle(candle)
        self._candle_count += 1
        return self._snapshot(candle.close)

    def _feed_candle(self, candle: Candle) -> None:
        """Feed a candle to all indicators."""
        close = candle.close
        high = candle.high
        low = candle.low
        volume = candle.volume

        # Price-based (float input)
        self._ema_9.add(close)
        self._ema_21.add(close)
        self._ema_55.add(close)
        self._ema_200.add(close)
        self._sma_20.add(close)
        self._rsi_14.add(close)
        self._macd.add(close)
        self._bb.add(close)

        # OHLCV-based (OHLCV object input)
        ohlcv = OHLCV(candle.open, high, low, close, volume)
        self._adx.add(ohlcv)
        self._atr.add(ohlcv)
        self._stoch.add(ohlcv)
        self._obv.add(ohlcv)

        # Volume SMA (float input)
        self._vol_sma.add(volume)

    def _snapshot(self, close: float) -> StreamingValues:
        """Create a snapshot of current indicator values."""
        vals = StreamingValues(close=close)

        # Safe extraction — talipp returns None until enough data
        vals.ema_9 = _last(self._ema_9)
        vals.ema_21 = _last(self._ema_21)
        vals.ema_55 = _last(self._ema_55)
        vals.ema_200 = _last(self._ema_200)
        vals.sma_20 = _last(self._sma_20)
        vals.rsi_14 = _last(self._rsi_14)

        macd_val = _last_obj(self._macd)
        if macd_val:
            vals.macd = macd_val.macd if hasattr(macd_val, "macd") else None
            vals.macd_signal = macd_val.signal if hasattr(macd_val, "signal") else None
            vals.macd_histogram = macd_val.histogram if hasattr(macd_val, "histogram") else None

        bb_val = _last_obj(self._bb)
        if bb_val:
            vals.bb_upper = bb_val.ub if hasattr(bb_val, "ub") else None
            vals.bb_middle = bb_val.cb if hasattr(bb_val, "cb") else None
            vals.bb_lower = bb_val.lb if hasattr(bb_val, "lb") else None
            if vals.bb_upper and vals.bb_lower:
                vals.bb_width = vals.bb_upper - vals.bb_lower

        vals.adx = _last(self._adx)
        vals.atr_14 = _last(self._atr)
        vals.obv = _last(self._obv)

        stoch_val = _last_obj(self._stoch)
        if stoch_val:
            vals.stoch_k = getattr(stoch_val, "k", None) or getattr(stoch_val, "slow_k", None)
            vals.stoch_d = getattr(stoch_val, "d", None) or getattr(stoch_val, "slow_d", None)

        vals.volume_sma_20 = _last(self._vol_sma)

        return vals

    @property
    def is_warm(self) -> bool:
        """True if enough candles have been processed for all indicators."""
        return self._candle_count >= 200

    @property
    def candle_count(self) -> int:
        return self._candle_count


def _last(indicator) -> float | None:
    """Safely get the last value from a talipp indicator."""
    try:
        if indicator and len(indicator) > 0:
            val = indicator[-1]
            if val is not None and not (isinstance(val, float) and val != val):  # NaN check
                return float(val)
    except (IndexError, TypeError, ValueError):
        pass
    return None


def _last_obj(indicator):
    """Safely get the last composite value from a talipp indicator."""
    try:
        if indicator and len(indicator) > 0:
            return indicator[-1]
    except (IndexError, TypeError):
        pass
    return None
