"""Unit tests for SmartMoneyStrategy - evaluate() with market conditions."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config.constants import Direction
from app.core.models import Candle, IndicatorValues
from app.strategies.smc import SmartMoneyStrategy


def _make_indicators(**overrides) -> IndicatorValues:
    defaults = dict(
        symbol="BTC/USDT", timeframe="1h",
        timestamp=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        atr_14=200.0, adx=30.0,
    )
    defaults.update(overrides)
    return IndicatorValues(**defaults)


def _make_candles_uptrend(n: int = 120) -> list[Candle]:
    """Strong uptrend with clear swing highs/lows."""
    candles = []
    price = 42000.0
    for i in range(n):
        price += 15 if i % 5 < 3 else -5
        o = price - 10
        h = price + 50
        l = price - 40
        # Add large bullish candle at position n-15
        if i == n - 15:
            body = 400
            candles.append(Candle(
                time=datetime(2024, 1, 1, i % 24, 0, tzinfo=UTC),
                symbol="BTC/USDT", timeframe="1h",
                open=price - body / 2, high=price + body / 2 + 20,
                low=price - body / 2 - 20, close=price + body / 2,
                volume=500.0,
            ))
        else:
            candles.append(Candle(
                time=datetime(2024, 1, 1, i % 24, 0, tzinfo=UTC),
                symbol="BTC/USDT", timeframe="1h",
                open=o, high=h, low=l, close=price, volume=100.0,
            ))
    return candles


def _make_candles_downtrend(n: int = 120) -> list[Candle]:
    """Strong downtrend."""
    candles = []
    price = 45000.0
    for i in range(n):
        price -= 15 if i % 5 < 3 else -5
        o = price + 10
        h = price + 40
        l = price - 50
        if i == n - 15:
            body = 400
            candles.append(Candle(
                time=datetime(2024, 1, 1, i % 24, 0, tzinfo=UTC),
                symbol="BTC/USDT", timeframe="1h",
                open=price + body / 2, high=price + body / 2 + 20,
                low=price - body / 2 - 20, close=price - body / 2,
                volume=500.0,
            ))
        else:
            candles.append(Candle(
                time=datetime(2024, 1, 1, i % 24, 0, tzinfo=UTC),
                symbol="BTC/USDT", timeframe="1h",
                open=o, high=h, low=l, close=price, volume=100.0,
            ))
    return candles


def _make_candles_flat(n: int = 120) -> list[Candle]:
    """Flat/ranging market."""
    candles = []
    for i in range(n):
        candles.append(Candle(
            time=datetime(2024, 1, 1, i % 24, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=43000.0, high=43100.0, low=42900.0, close=43000.0,
            volume=100.0,
        ))
    return candles


class TestSmartMoneyStrategyEval:
    def test_attributes(self):
        s = SmartMoneyStrategy()
        assert s.name == "smart_money"
        assert s.weight == 0.25
        assert s.min_candles == 100

    def test_insufficient_candles_returns_none(self):
        s = SmartMoneyStrategy()
        candles = [Candle(
            time=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=43000.0, high=43100.0, low=42900.0, close=43050.0,
            volume=100.0,
        )] * 50
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_missing_atr_returns_none(self):
        s = SmartMoneyStrategy()
        candles = _make_candles_uptrend()
        indicators = _make_indicators(atr_14=None)
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_uptrend_may_produce_long(self):
        s = SmartMoneyStrategy()
        candles = _make_candles_uptrend(120)
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        # In uptrend with order blocks, may produce LONG or None
        if result is not None:
            assert result.direction == Direction.LONG

    def test_downtrend_may_produce_short(self):
        s = SmartMoneyStrategy()
        candles = _make_candles_downtrend(120)
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        if result is not None:
            assert result.direction == Direction.SHORT

    def test_flat_market_no_signal(self):
        """Flat market → no structure breaks, no order blocks."""
        s = SmartMoneyStrategy()
        candles = _make_candles_flat()
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_signal_has_metadata(self):
        s = SmartMoneyStrategy()
        candles = _make_candles_uptrend(120)
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        if result is not None:
            assert "price_zone" in result.metadata
            assert "structure" in result.metadata
            assert "order_blocks" in result.metadata

    def test_signal_symbol_and_timeframe(self):
        s = SmartMoneyStrategy()
        candles = _make_candles_uptrend(120)
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        if result is not None:
            assert result.symbol == "BTC/USDT"
            assert result.timeframe == "1h"

    def test_strength_clamped(self):
        s = SmartMoneyStrategy()
        candles = _make_candles_uptrend(120)
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        if result is not None:
            assert -1.0 <= result.strength <= 1.0

    def test_zero_range_returns_none(self):
        """All candles at same price → range_size = 0 → None."""
        s = SmartMoneyStrategy()
        candles = []
        for i in range(120):
            candles.append(Candle(
                time=datetime(2024, 1, 1, i % 24, 0, tzinfo=UTC),
                symbol="BTC/USDT", timeframe="1h",
                open=43000.0, high=43000.0, low=43000.0, close=43000.0,
                volume=100.0,
            ))
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        assert result is None

    def test_discount_zone_detected(self):
        """Price in bottom 40% of range → discount zone."""
        s = SmartMoneyStrategy()
        candles = _make_candles_uptrend(120)
        # Override last candle to be at bottom of range
        recent = candles[-50:]
        range_low = min(c.low for c in recent)
        candles[-1] = Candle(
            time=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=range_low + 10, high=range_low + 20,
            low=range_low - 10, close=range_low + 5,
            volume=100.0,
        )
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        if result is not None and result.direction == Direction.LONG:
            assert "DISCOUNT_ZONE" in result.conditions

    def test_premium_zone_detected(self):
        """Price in top 40% of range → premium zone."""
        s = SmartMoneyStrategy()
        candles = _make_candles_downtrend(120)
        recent = candles[-50:]
        range_high = max(c.high for c in recent)
        candles[-1] = Candle(
            time=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=range_high - 10, high=range_high + 10,
            low=range_high - 20, close=range_high - 5,
            volume=100.0,
        )
        indicators = _make_indicators()
        result = s.evaluate(candles, indicators)
        if result is not None and result.direction == Direction.SHORT:
            assert "PREMIUM_ZONE" in result.conditions
