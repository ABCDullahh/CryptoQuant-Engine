"""Unit tests for BaseStrategy ABC."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.config.constants import Direction
from app.core.models import Candle, IndicatorValues, MarketContext, RawSignal
from app.strategies.base import BaseStrategy


def _make_candle(close: float = 43000.0) -> Candle:
    return Candle(
        time=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        symbol="BTC/USDT", timeframe="1h",
        open=43000.0, high=43500.0, low=42900.0, close=close,
        volume=100.0,
    )


def _make_indicators() -> IndicatorValues:
    return IndicatorValues(
        symbol="BTC/USDT", timeframe="1h",
        timestamp=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        ema_9=43200.0, ema_21=43100.0, ema_55=43000.0,
        rsi_14=55.0, macd_histogram=10.0, adx=30.0,
    )


class ConcreteStrategy(BaseStrategy):
    """Concrete implementation for testing."""
    name = "test_strategy"
    weight = 0.10
    min_candles = 10

    def evaluate(self, candles, indicators, context=None):
        return self._create_signal(
            direction=Direction.LONG,
            strength=0.75,
            entry_price=candles[-1].close,
            symbol=candles[-1].symbol,
            timeframe=candles[-1].timeframe,
            conditions=["TEST_CONDITION"],
        )


class TestBaseStrategy:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            BaseStrategy()

    def test_concrete_strategy_instantiates(self):
        strategy = ConcreteStrategy()
        assert strategy.name == "test_strategy"
        assert strategy.weight == 0.10
        assert strategy.min_candles == 10

    def test_evaluate_returns_signal(self):
        strategy = ConcreteStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators()
        result = strategy.evaluate(candles, indicators)
        assert isinstance(result, RawSignal)
        assert result.direction == Direction.LONG

    def test_create_signal_basic(self):
        strategy = ConcreteStrategy()
        signal = strategy._create_signal(
            direction=Direction.SHORT,
            strength=-0.8,
            entry_price=43000.0,
            symbol="BTC/USDT",
            timeframe="1h",
            conditions=["COND_A", "COND_B"],
            metadata={"key": "val"},
        )
        assert signal.strategy_name == "test_strategy"
        assert signal.direction == Direction.SHORT
        assert signal.strength == -0.8
        assert signal.entry_price == 43000.0
        assert "COND_A" in signal.conditions
        assert signal.metadata["key"] == "val"

    def test_create_signal_clamps_strength(self):
        strategy = ConcreteStrategy()
        signal = strategy._create_signal(
            direction=Direction.LONG, strength=1.5,
            entry_price=100.0, symbol="X", timeframe="1h",
        )
        assert signal.strength == 1.0

        signal2 = strategy._create_signal(
            direction=Direction.SHORT, strength=-1.5,
            entry_price=100.0, symbol="X", timeframe="1h",
        )
        assert signal2.strength == -1.0

    def test_create_signal_defaults(self):
        strategy = ConcreteStrategy()
        signal = strategy._create_signal(
            direction=Direction.LONG, strength=0.5,
            entry_price=100.0, symbol="X", timeframe="1h",
        )
        assert signal.conditions == []
        assert signal.metadata == {}

    def test_pipeline_attribute(self):
        strategy = ConcreteStrategy()
        assert strategy._pipeline is not None

    async def test_analyze_calls_evaluate(self):
        strategy = ConcreteStrategy()
        mock_collector = AsyncMock()
        candles = [_make_candle() for _ in range(20)]
        mock_collector.get_candles = AsyncMock(return_value=candles)

        result = await strategy.analyze(mock_collector, "BTC/USDT", "1h")
        assert isinstance(result, RawSignal)
        mock_collector.get_candles.assert_called_once()

    async def test_analyze_insufficient_candles_returns_none(self):
        strategy = ConcreteStrategy()
        mock_collector = AsyncMock()
        mock_collector.get_candles = AsyncMock(return_value=[_make_candle()])

        result = await strategy.analyze(mock_collector, "BTC/USDT", "1h")
        assert result is None

    async def test_analyze_requests_enough_candles(self):
        strategy = ConcreteStrategy()
        strategy.min_candles = 100
        mock_collector = AsyncMock()
        mock_collector.get_candles = AsyncMock(return_value=[])

        await strategy.analyze(mock_collector, "BTC/USDT", "1h")
        call_args = mock_collector.get_candles.call_args
        assert call_args[1]["limit"] >= 200

    def test_evaluate_with_context(self):
        strategy = ConcreteStrategy()
        candles = [_make_candle()]
        indicators = _make_indicators()
        context = MarketContext()
        result = strategy.evaluate(candles, indicators, context)
        assert result is not None
