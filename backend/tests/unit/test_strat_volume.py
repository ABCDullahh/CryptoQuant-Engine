"""Unit tests for VolumeAnalysisStrategy."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config.constants import Direction
from app.core.models import Candle, IndicatorValues
from app.strategies.volume import VolumeAnalysisStrategy


def _make_candle(close: float = 43200.0, volume: float = 200.0) -> Candle:
    return Candle(
        time=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        symbol="BTC/USDT", timeframe="1h",
        open=43000.0, high=43500.0, low=42900.0, close=close,
        volume=volume,
    )


def _make_candles(closes: list[float], volumes: list[float] | None = None) -> list[Candle]:
    if volumes is None:
        volumes = [200.0] * len(closes)
    return [
        Candle(
            time=datetime(2024, 1, 15, i, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=c - 50, high=c + 100, low=c - 100, close=c,
            volume=v,
        )
        for i, (c, v) in enumerate(zip(closes, volumes))
    ]


def _make_indicators(**overrides) -> IndicatorValues:
    defaults = dict(
        symbol="BTC/USDT", timeframe="1h",
        timestamp=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        obv=50000.0, vwap=43000.0, volume_sma_20=100.0,
    )
    defaults.update(overrides)
    return IndicatorValues(**defaults)


class TestVolumeAnalysisStrategy:
    def test_attributes(self):
        s = VolumeAnalysisStrategy()
        assert s.name == "volume_analysis"
        assert s.weight == 0.15
        assert s.min_candles == 30

    def test_strong_long_signal(self):
        """OBV rising + volume spike + above VWAP + price momentum."""
        s = VolumeAnalysisStrategy()
        candles = _make_candles(
            closes=[42800.0, 42900.0, 43000.0, 43200.0],
            volumes=[100.0, 100.0, 100.0, 200.0],
        )
        indicators = _make_indicators(vwap=43000.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.LONG
        assert "OBV_RISING" in result.conditions
        assert "VOLUME_SPIKE" in result.conditions
        assert "ABOVE_VWAP" in result.conditions

    def test_strong_short_signal(self):
        """OBV falling + volume spike + below VWAP + price momentum down."""
        s = VolumeAnalysisStrategy()
        candles = _make_candles(
            closes=[43500.0, 43400.0, 43300.0, 43100.0],
            volumes=[100.0, 100.0, 100.0, 200.0],
        )
        indicators = _make_indicators(vwap=43200.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.SHORT
        assert "OBV_FALLING" in result.conditions

    def test_no_signal_low_volume(self):
        """Low volume → no volume spike → weaker signal."""
        s = VolumeAnalysisStrategy()
        candles = _make_candles(
            closes=[43000.0, 43100.0],
            volumes=[50.0, 50.0],
        )
        indicators = _make_indicators(vwap=43000.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        # Without volume spike (0.30), hard to reach 0.50
        # OBV_RISING(0.25) + ABOVE_VWAP(0.25) = 0.50, might signal
        if result is not None:
            assert "VOLUME_SPIKE" not in result.conditions

    def test_missing_obv_returns_none(self):
        s = VolumeAnalysisStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(obv=None)
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_missing_vwap_returns_none(self):
        s = VolumeAnalysisStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(vwap=None)
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_missing_volume_sma_returns_none(self):
        s = VolumeAnalysisStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(volume_sma_20=None)
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_volume_spike_threshold(self):
        """Exact 1.5x volume_sma triggers spike."""
        s = VolumeAnalysisStrategy()
        candles = _make_candles(
            closes=[43000.0, 43100.0, 43200.0, 43300.0],
            volumes=[100.0, 100.0, 100.0, 150.0],
        )
        indicators = _make_indicators(vwap=43000.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "VOLUME_SPIKE" in result.conditions

    def test_below_volume_spike_threshold(self):
        """Volume at 1.4x → no spike."""
        s = VolumeAnalysisStrategy()
        candles = _make_candles(
            closes=[43000.0, 43100.0, 43200.0, 43300.0],
            volumes=[100.0, 100.0, 100.0, 140.0],
        )
        indicators = _make_indicators(vwap=43000.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        if result is not None:
            assert "VOLUME_SPIKE" not in result.conditions

    def test_metadata_populated(self):
        s = VolumeAnalysisStrategy()
        candles = _make_candles(
            closes=[42800.0, 42900.0, 43000.0, 43200.0],
            volumes=[100.0, 100.0, 100.0, 200.0],
        )
        indicators = _make_indicators(vwap=43000.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "obv" in result.metadata
        assert "vwap" in result.metadata
        assert "volume_ratio" in result.metadata

    def test_single_candle_no_obv_trend(self):
        """Single candle → can't determine OBV trend."""
        s = VolumeAnalysisStrategy()
        candles = [_make_candle(close=43200.0, volume=200.0)]
        indicators = _make_indicators(vwap=43000.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        if result is not None:
            assert "OBV_RISING" not in result.conditions
            assert "OBV_FALLING" not in result.conditions

    def test_price_momentum_up(self):
        """Close > close[3 bars ago] adds PRICE_MOMENTUM_UP."""
        s = VolumeAnalysisStrategy()
        candles = _make_candles(
            closes=[43000.0, 43100.0, 43200.0, 43400.0],
            volumes=[100.0, 100.0, 100.0, 200.0],
        )
        indicators = _make_indicators(vwap=43000.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "PRICE_MOMENTUM_UP" in result.conditions

    def test_price_momentum_down(self):
        s = VolumeAnalysisStrategy()
        candles = _make_candles(
            closes=[43500.0, 43400.0, 43300.0, 43100.0],
            volumes=[100.0, 100.0, 100.0, 200.0],
        )
        indicators = _make_indicators(vwap=43200.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "PRICE_MOMENTUM_DOWN" in result.conditions

    def test_zero_volume_sma_no_crash(self):
        s = VolumeAnalysisStrategy()
        candles = _make_candles(
            closes=[43000.0, 43100.0],
            volumes=[100.0, 200.0],
        )
        indicators = _make_indicators(volume_sma_20=0.0)
        result = s.evaluate(candles, indicators)
        # Should not crash even with zero vol_sma (division guarded)
        # May or may not produce signal
