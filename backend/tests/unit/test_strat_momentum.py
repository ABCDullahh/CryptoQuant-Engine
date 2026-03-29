"""Unit tests for MomentumStrategy."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config.constants import Direction
from app.core.models import Candle, IndicatorValues, MarketContext, RawSignal
from app.strategies.momentum import MomentumStrategy


def _make_candle(close: float = 43200.0) -> Candle:
    return Candle(
        time=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        symbol="BTC/USDT", timeframe="1h",
        open=43000.0, high=43500.0, low=42900.0, close=close,
        volume=100.0,
    )


def _make_indicators(**overrides) -> IndicatorValues:
    defaults = dict(
        symbol="BTC/USDT", timeframe="1h",
        timestamp=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        ema_9=43300.0, ema_21=43200.0, ema_55=43100.0,
        rsi_14=55.0, macd_histogram=15.0, adx=30.0,
    )
    defaults.update(overrides)
    return IndicatorValues(**defaults)


class TestMomentumStrategy:
    def test_attributes(self):
        s = MomentumStrategy()
        assert s.name == "momentum"
        assert s.weight == 0.15
        assert s.min_candles == 55

    def test_strong_long_signal(self):
        """All LONG conditions met → strong signal."""
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(
            ema_9=43300.0, ema_21=43200.0, ema_55=43100.0,
            rsi_14=55.0, macd_histogram=15.0, adx=30.0,
        )
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.LONG
        assert result.strength == pytest.approx(1.0)
        assert "EMA_ALIGNED_UP" in result.conditions
        assert "RSI_HEALTHY" in result.conditions
        assert "MACD_POSITIVE" in result.conditions
        assert "ADX_STRONG" in result.conditions

    def test_strong_short_signal(self):
        """All SHORT conditions met → strong signal."""
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(
            ema_9=43000.0, ema_21=43100.0, ema_55=43200.0,
            rsi_14=45.0, macd_histogram=-15.0, adx=30.0,
        )
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.SHORT
        assert result.strength == pytest.approx(-1.0)
        assert "EMA_ALIGNED_DOWN" in result.conditions

    def test_no_signal_neutral(self):
        """No EMA alignment → no signal."""
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(
            ema_9=43200.0, ema_21=43300.0, ema_55=43100.0,  # Mixed
            rsi_14=50.0, macd_histogram=5.0, adx=15.0,
        )
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_no_signal_rsi_overbought(self):
        """EMAs aligned up but RSI too high → weaker but may still signal."""
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(
            ema_9=43300.0, ema_21=43200.0, ema_55=43100.0,
            rsi_14=80.0,  # Overbought
            macd_histogram=15.0, adx=30.0,
        )
        result = s.evaluate(candles, indicators)
        # EMA(0.30) + MACD(0.25) + ADX(0.25) = 0.80, RSI not healthy
        assert result is not None
        assert "RSI_HEALTHY" not in result.conditions

    def test_weak_signal_low_adx(self):
        """EMA aligned + RSI ok + MACD ok but low ADX → still signals if >= 0.50."""
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(
            ema_9=43300.0, ema_21=43200.0, ema_55=43100.0,
            rsi_14=55.0, macd_histogram=15.0, adx=20.0,
        )
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "ADX_STRONG" not in result.conditions
        assert result.strength < 1.0

    def test_missing_indicators_returns_none(self):
        """Missing required indicators → None."""
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(ema_9=None)
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_missing_ema21_returns_none(self):
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(ema_21=None)
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_missing_rsi_returns_none(self):
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(rsi_14=None)
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_missing_macd_histogram_returns_none(self):
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(macd_histogram=None)
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_adx_none_still_works(self):
        """ADX is optional; signal possible without it."""
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(
            ema_9=43300.0, ema_21=43200.0, ema_55=43100.0,
            rsi_14=55.0, macd_histogram=15.0, adx=None,
        )
        result = s.evaluate(candles, indicators)
        # EMA(0.30) + RSI(0.20) + MACD(0.25) = 0.75 → should signal
        assert result is not None
        assert "ADX_STRONG" not in result.conditions

    def test_signal_metadata(self):
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "rsi" in result.metadata
        assert "adx" in result.metadata
        assert "macd_hist" in result.metadata

    def test_signal_entry_price_is_last_close(self):
        s = MomentumStrategy()
        candles = [_make_candle(close=44000.0)]
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.entry_price == 44000.0

    def test_signal_symbol_and_timeframe(self):
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.symbol == "BTC/USDT"
        assert result.timeframe == "1h"

    def test_long_preferred_over_short_when_both_weak(self):
        """When both have conditions, higher score wins."""
        s = MomentumStrategy()
        candles = [_make_candle()]
        # Slightly more long-biased
        indicators = _make_indicators(
            ema_9=43300.0, ema_21=43200.0, ema_55=43100.0,
            rsi_14=55.0, macd_histogram=0.1, adx=30.0,
        )
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.LONG

    def test_short_wins_when_stronger(self):
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(
            ema_9=43000.0, ema_21=43100.0, ema_55=43200.0,
            rsi_14=45.0, macd_histogram=-15.0, adx=30.0,
        )
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.SHORT

    def test_rsi_boundary_40_included_long(self):
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(rsi_14=40.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "RSI_HEALTHY" in result.conditions

    def test_rsi_boundary_70_included_long(self):
        s = MomentumStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(rsi_14=70.0)
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "RSI_HEALTHY" in result.conditions
