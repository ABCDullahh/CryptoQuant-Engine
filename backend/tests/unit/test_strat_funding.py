"""Unit tests for FundingArbStrategy."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.config.constants import Direction
from app.core.models import Candle, FundingRate, IndicatorValues
from app.strategies.funding import FundingArbStrategy


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
        rsi_14=50.0, adx=25.0,
    )
    defaults.update(overrides)
    return IndicatorValues(**defaults)


class TestFundingArbStrategy:
    def test_attributes(self):
        s = FundingArbStrategy()
        assert s.name == "funding_arb"
        assert s.weight == 0.05
        assert s.min_candles == 20

    def test_no_funding_returns_none(self):
        s = FundingArbStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators()
        # _last_funding_rate defaults to None
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_extreme_negative_funding_long(self):
        """Very negative funding → LONG signal."""
        s = FundingArbStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(rsi_14=35.0, adx=20.0)
        s._last_funding_rate = -0.0006
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.LONG
        assert "VERY_EXTREME_NEGATIVE_FUNDING" in result.conditions

    def test_moderate_negative_funding_long(self):
        s = FundingArbStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(rsi_14=35.0, adx=20.0)
        s._last_funding_rate = -0.0002
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.LONG
        assert "EXTREME_NEGATIVE_FUNDING" in result.conditions

    def test_extreme_positive_funding_short(self):
        """Very positive funding → SHORT signal."""
        s = FundingArbStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(rsi_14=65.0, adx=20.0)
        s._last_funding_rate = 0.0015
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.SHORT
        assert "VERY_EXTREME_POSITIVE_FUNDING" in result.conditions

    def test_moderate_positive_funding_short(self):
        s = FundingArbStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(rsi_14=65.0, adx=20.0)
        s._last_funding_rate = 0.0004
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.direction == Direction.SHORT
        assert "EXTREME_POSITIVE_FUNDING" in result.conditions

    def test_normal_funding_no_signal(self):
        """Normal funding rate → no signal."""
        s = FundingArbStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators()
        s._last_funding_rate = 0.0001
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_rsi_confirmation_long(self):
        s = FundingArbStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(rsi_14=35.0)
        s._last_funding_rate = -0.0006
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "RSI_SUPPORTS_LONG" in result.conditions

    def test_rsi_confirmation_short(self):
        s = FundingArbStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(rsi_14=65.0)
        s._last_funding_rate = 0.0015
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "RSI_SUPPORTS_SHORT" in result.conditions

    def test_metadata_has_funding_rate(self):
        s = FundingArbStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(rsi_14=35.0, adx=20.0)
        s._last_funding_rate = -0.0006
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert result.metadata["funding_rate"] == -0.0006

    def test_no_strong_trend_condition(self):
        s = FundingArbStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators(adx=20.0)
        s._last_funding_rate = -0.0006
        result = s.evaluate(candles, indicators)
        assert result is not None
        assert "NO_STRONG_TREND" in result.conditions

    async def test_analyze_fetches_funding(self):
        s = FundingArbStrategy()
        mock_collector = AsyncMock()
        mock_collector.get_candles = AsyncMock(
            return_value=[_make_candle() for _ in range(30)]
        )
        mock_collector.get_funding_rate = AsyncMock(
            return_value=FundingRate(
                symbol="BTC/USDT",
                timestamp=datetime(2024, 1, 15, tzinfo=UTC),
                rate=-0.0006,
            )
        )
        result = await s.analyze(mock_collector, "BTC/USDT", "1h")
        mock_collector.get_funding_rate.assert_called_once_with("BTC/USDT")

    async def test_analyze_no_funding_data(self):
        s = FundingArbStrategy()
        mock_collector = AsyncMock()
        mock_collector.get_candles = AsyncMock(
            return_value=[_make_candle() for _ in range(30)]
        )
        mock_collector.get_funding_rate = AsyncMock(return_value=None)
        result = await s.analyze(mock_collector, "BTC/USDT", "1h")
        assert result is None
