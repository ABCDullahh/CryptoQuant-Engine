"""Unit tests for MeanReversionStrategy."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config.constants import Direction
from app.core.models import Candle, IndicatorValues
from app.strategies.mean_reversion import MeanReversionStrategy


def _make_candle(close: float = 43200.0, volume: float = 200.0) -> Candle:
    return Candle(
        time=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        symbol="BTC/USDT", timeframe="1h",
        open=43000.0, high=43500.0, low=42900.0, close=close,
        volume=volume,
    )


def _make_indicators(**overrides) -> IndicatorValues:
    defaults = dict(
        symbol="BTC/USDT", timeframe="1h",
        timestamp=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        bb_upper=44000.0, bb_middle=43000.0, bb_lower=42000.0,
        rsi_14=50.0, volume_sma_20=100.0,
    )
    defaults.update(overrides)
    return IndicatorValues(**defaults)


class TestMeanReversionStrategy:
    def test_attributes(self):
        s = MeanReversionStrategy()
        assert s.name == "mean_reversion"
        assert s.weight == 0.10
        assert s.min_candles == 30

    def test_strong_long_oversold(self):
        """Price below lower BB + RSI extreme oversold + volume."""
        s = MeanReversionStrategy()
        candles = [_make_candle(close=41900.0, volume=150.0)]  # below lower BB
        indicators = _make_indicators(rsi_14=22.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.LONG
        assert "BELOW_LOWER_BB" in result.conditions
        assert "RSI_EXTREME_OVERSOLD" in result.conditions

    def test_strong_short_overbought(self):
        """Price above upper BB + RSI extreme overbought + volume."""
        s = MeanReversionStrategy()
        candles = [_make_candle(close=44100.0, volume=150.0)]
        indicators = _make_indicators(rsi_14=78.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.SHORT
        assert "ABOVE_UPPER_BB" in result.conditions
        assert "RSI_EXTREME_OVERBOUGHT" in result.conditions

    def test_no_signal_neutral_zone(self):
        """Price in middle of BB, normal RSI → no signal."""
        s = MeanReversionStrategy()
        candles = [_make_candle(close=43000.0)]
        indicators = _make_indicators(rsi_14=50.0)
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_missing_bb_upper_returns_none(self):
        s = MeanReversionStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(bb_upper=None)
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_missing_rsi_returns_none(self):
        s = MeanReversionStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(rsi_14=None)
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_zero_bb_width_returns_none(self):
        s = MeanReversionStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(bb_upper=43000.0, bb_lower=43000.0)
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_near_lower_bb_with_rsi_oversold(self):
        s = MeanReversionStrategy()
        # Close near lower BB (within 25% of BB range from bottom)
        candles = [_make_candle(close=42400.0, volume=150.0)]
        indicators = _make_indicators(rsi_14=28.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.LONG

    def test_near_upper_bb_with_rsi_overbought(self):
        s = MeanReversionStrategy()
        candles = [_make_candle(close=43700.0, volume=150.0)]
        indicators = _make_indicators(rsi_14=72.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.SHORT

    def test_volume_confirmation(self):
        """Volume above SMA adds to score."""
        s = MeanReversionStrategy()
        candles = [_make_candle(close=41900.0, volume=150.0)]
        indicators = _make_indicators(rsi_14=22.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "VOLUME_CONFIRMED" in result.conditions

    def test_no_volume_confirmation(self):
        """Volume below SMA doesn't add volume condition."""
        s = MeanReversionStrategy()
        candles = [_make_candle(close=41900.0, volume=50.0)]
        indicators = _make_indicators(rsi_14=22.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "VOLUME_CONFIRMED" not in result.conditions

    def test_metadata_contains_bb_position(self):
        s = MeanReversionStrategy()
        candles = [_make_candle(close=41900.0, volume=150.0)]
        indicators = _make_indicators(rsi_14=22.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "bb_position" in result.metadata
        assert "volume_ratio" in result.metadata

    def test_no_volume_sma_uses_default_ratio(self):
        """When volume_sma_20 is None, vol_ratio defaults to 1.0 → volume confirmed."""
        s = MeanReversionStrategy()
        candles = [_make_candle(close=41900.0)]
        indicators = _make_indicators(rsi_14=22.0, volume_sma_20=None)
        result = s.evaluate(candles, indicators)
        # vol_sma is None but not in the "required" check (only bb/rsi are),
        # so it uses default ratio 1.0 and still produces a signal
        assert result is not None
        assert result.direction == Direction.LONG

    def test_long_score_beats_short(self):
        """When both have scores, higher wins."""
        s = MeanReversionStrategy()
        candles = [_make_candle(close=41900.0, volume=150.0)]
        indicators = _make_indicators(rsi_14=22.0, volume_sma_20=100.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.LONG
