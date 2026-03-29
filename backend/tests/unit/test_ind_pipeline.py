"""Unit tests for IndicatorPipeline - integration of all indicators."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from app.core.models import Candle, IndicatorValues
from app.indicators.base import IndicatorPipeline


def _make_candles(n: int = 60, base_price: float = 43000.0) -> list[Candle]:
    """Generate n synthetic candles with realistic OHLCV data."""
    np.random.seed(42)
    candles = []
    price = base_price
    for i in range(n):
        change = np.random.randn() * 50
        price += change
        o = price
        h = price + abs(np.random.randn() * 30)
        l = price - abs(np.random.randn() * 30)
        c = price + np.random.randn() * 20
        vol = abs(np.random.randn() * 100) + 50
        candles.append(Candle(
            time=datetime(2024, 1, 1, i % 24, 0, tzinfo=UTC),
            symbol="BTC/USDT",
            timeframe="1h",
            open=o, high=h, low=l, close=c,
            volume=vol,
        ))
    return candles


class TestIndicatorPipeline:
    def test_compute_returns_indicator_values(self):
        pipeline = IndicatorPipeline()
        candles = _make_candles(60)
        result = pipeline.compute(candles)
        assert isinstance(result, IndicatorValues)
        assert result.symbol == "BTC/USDT"
        assert result.timeframe == "1h"

    def test_compute_ema_values_populated(self):
        pipeline = IndicatorPipeline()
        candles = _make_candles(60)
        result = pipeline.compute(candles)
        assert result.ema_9 is not None
        assert result.ema_21 is not None
        assert result.ema_55 is not None
        # ema_200 needs 200 candles, should be None with 60
        assert result.ema_200 is None

    def test_compute_macd_populated(self):
        pipeline = IndicatorPipeline()
        candles = _make_candles(60)
        result = pipeline.compute(candles)
        assert result.macd is not None
        assert result.macd_signal is not None
        assert result.macd_histogram is not None

    def test_compute_rsi_populated(self):
        pipeline = IndicatorPipeline()
        candles = _make_candles(60)
        result = pipeline.compute(candles)
        assert result.rsi_14 is not None
        assert 0 <= result.rsi_14 <= 100

    def test_compute_stochastic_populated(self):
        pipeline = IndicatorPipeline()
        candles = _make_candles(60)
        result = pipeline.compute(candles)
        assert result.stoch_k is not None
        assert result.stoch_d is not None

    def test_compute_atr_populated(self):
        pipeline = IndicatorPipeline()
        candles = _make_candles(60)
        result = pipeline.compute(candles)
        assert result.atr_14 is not None
        assert result.atr_14 > 0

    def test_compute_bollinger_populated(self):
        pipeline = IndicatorPipeline()
        candles = _make_candles(60)
        result = pipeline.compute(candles)
        assert result.bb_upper is not None
        assert result.bb_middle is not None
        assert result.bb_lower is not None
        assert result.bb_width is not None
        assert result.bb_upper >= result.bb_middle >= result.bb_lower

    def test_compute_volume_indicators_populated(self):
        pipeline = IndicatorPipeline()
        candles = _make_candles(60)
        result = pipeline.compute(candles)
        assert result.vwap is not None
        assert result.obv is not None
        assert result.volume_sma_20 is not None

    def test_compute_empty_raises(self):
        pipeline = IndicatorPipeline()
        with pytest.raises(ValueError, match="empty"):
            pipeline.compute([])

    def test_compute_small_candle_set(self):
        """With very few candles, most indicators should be None."""
        pipeline = IndicatorPipeline()
        candles = _make_candles(5)
        result = pipeline.compute(candles)
        assert result.ema_9 is None  # Need 9 candles
        assert result.rsi_14 is None  # Need 15 candles
        assert result.vwap is not None  # VWAP works with any count

    def test_compute_uses_last_candle_metadata(self):
        pipeline = IndicatorPipeline()
        candles = _make_candles(60)
        result = pipeline.compute(candles)
        assert result.timestamp == candles[-1].time

    def test_compute_bb_width_calculation(self):
        pipeline = IndicatorPipeline()
        candles = _make_candles(60)
        result = pipeline.compute(candles)
        if result.bb_upper and result.bb_lower and result.bb_middle:
            expected_width = (result.bb_upper - result.bb_lower) / result.bb_middle
            assert result.bb_width == pytest.approx(expected_width)
