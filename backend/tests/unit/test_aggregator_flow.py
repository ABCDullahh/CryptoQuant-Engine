"""Unit tests for SignalAggregator - full aggregation flow."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.config.constants import Direction, SignalGrade
from app.core.models import (
    Candle,
    CompositeSignal,
    IndicatorValues,
    MarketContext,
    RawSignal,
)
from app.signals.aggregator import SignalAggregator
from app.signals.regime import MarketRegimeDetector
from app.strategies.base import BaseStrategy


# ---------------------------------------------------------------------------
# Mock strategy helpers
# ---------------------------------------------------------------------------

class MockStrategy(BaseStrategy):
    """Configurable mock strategy for testing."""
    def __init__(self, name: str, weight: float, direction: Direction,
                 strength: float):
        super().__init__()
        self.name = name
        self.weight = weight
        self._direction = direction
        self._strength = strength
        self.min_candles = 10

    def evaluate(self, candles, indicators, context=None):
        return self._create_signal(
            direction=self._direction,
            strength=self._strength,
            entry_price=candles[-1].close,
            symbol=candles[-1].symbol,
            timeframe=candles[-1].timeframe,
            conditions=[f"{self.name}_CONDITION"],
        )


class NoneStrategy(BaseStrategy):
    """Always returns None."""
    name = "none_strategy"
    weight = 0.10
    min_candles = 10

    def evaluate(self, candles, indicators, context=None):
        return None


class ErrorStrategy(BaseStrategy):
    """Raises an error."""
    name = "error_strategy"
    weight = 0.10
    min_candles = 10

    def evaluate(self, candles, indicators, context=None):
        raise RuntimeError("Strategy failed")


def _make_candles(n: int = 60) -> list[Candle]:
    np.random.seed(42)
    candles = []
    price = 43000.0
    for i in range(n):
        price += np.random.randn() * 50
        candles.append(Candle(
            time=datetime(2024, 1, 1, i % 24, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=price - 20, high=price + 30, low=price - 30, close=price,
            volume=100.0 + np.random.randn() * 20,
        ))
    return candles


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAggregatorFlow:
    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_with_3_long_signals(self, mock_event_bus):
        """3 strategies agreeing on LONG → CompositeSignal."""
        mock_event_bus.publish = AsyncMock()
        strategies = [
            MockStrategy("strat1", 0.15, Direction.LONG, 0.8),
            MockStrategy("strat2", 0.25, Direction.LONG, 0.7),
            MockStrategy("strat3", 0.10, Direction.LONG, 0.6),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_candles(60))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        assert result is not None
        assert isinstance(result, CompositeSignal)
        assert result.direction == Direction.LONG
        assert result.symbol == "BTC/USDT"
        assert len(result.take_profits) == 3
        assert result.strategy_scores is not None

    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_with_3_short_signals(self, mock_event_bus):
        mock_event_bus.publish = AsyncMock()
        strategies = [
            MockStrategy("s1", 0.15, Direction.SHORT, -0.8),
            MockStrategy("s2", 0.25, Direction.SHORT, -0.7),
            MockStrategy("s3", 0.10, Direction.SHORT, -0.6),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_candles(60))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        assert result is not None
        assert result.direction == Direction.SHORT

    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_all_neutral_returns_none(self, mock_event_bus):
        """All strategies return NEUTRAL → None."""
        mock_event_bus.publish = AsyncMock()
        strategies = [
            MockStrategy("s1", 0.15, Direction.NEUTRAL, 0.0),
            MockStrategy("s2", 0.25, Direction.NEUTRAL, 0.0),
            MockStrategy("s3", 0.10, Direction.NEUTRAL, 0.0),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_candles(60))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        assert result is None

    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_no_candles(self, mock_event_bus):
        mock_event_bus.publish = AsyncMock()
        strategies = [MockStrategy("s1", 0.15, Direction.LONG, 0.8)]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=[])

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        assert result is None

    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_all_strategies_return_none(self, mock_event_bus):
        mock_event_bus.publish = AsyncMock()
        strategies = [NoneStrategy(), NoneStrategy(), NoneStrategy()]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_candles(60))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        assert result is None

    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_strategy_error_continues(self, mock_event_bus):
        """A failing strategy doesn't break aggregation."""
        mock_event_bus.publish = AsyncMock()
        strategies = [
            ErrorStrategy(),
            MockStrategy("s1", 0.15, Direction.LONG, 0.8),
            MockStrategy("s2", 0.25, Direction.LONG, 0.7),
            MockStrategy("s3", 0.10, Direction.LONG, 0.6),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_candles(60))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        assert result is not None

    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_grade_assignment(self, mock_event_bus):
        mock_event_bus.publish = AsyncMock()
        strategies = [
            MockStrategy("s1", 0.15, Direction.LONG, 0.9),
            MockStrategy("s2", 0.25, Direction.LONG, 0.9),
            MockStrategy("s3", 0.10, Direction.LONG, 0.9),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_candles(60))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        assert result is not None
        assert result.grade in (SignalGrade.A, SignalGrade.B)

    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_publishes_event(self, mock_event_bus):
        mock_event_bus.publish = AsyncMock()
        strategies = [
            MockStrategy("s1", 0.15, Direction.LONG, 0.8),
            MockStrategy("s2", 0.25, Direction.LONG, 0.7),
            MockStrategy("s3", 0.10, Direction.LONG, 0.6),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_candles(60))

        await agg.aggregate(collector, "BTC/USDT", "1h")
        mock_event_bus.publish.assert_called_once()

    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_publish_failure_doesnt_crash(self, mock_event_bus):
        mock_event_bus.publish = AsyncMock(side_effect=RuntimeError("pub fail"))
        strategies = [
            MockStrategy("s1", 0.15, Direction.LONG, 0.8),
            MockStrategy("s2", 0.25, Direction.LONG, 0.7),
            MockStrategy("s3", 0.10, Direction.LONG, 0.6),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_candles(60))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        assert result is not None

    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_strategy_scores(self, mock_event_bus):
        mock_event_bus.publish = AsyncMock()
        strategies = [
            MockStrategy("momentum", 0.15, Direction.LONG, 0.8),
            MockStrategy("smart_money", 0.25, Direction.LONG, 0.9),
            MockStrategy("volume", 0.10, Direction.LONG, 0.6),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_candles(60))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        assert result is not None
        assert "momentum" in result.strategy_scores
        assert "smart_money" in result.strategy_scores
        assert result.strategy_scores["momentum"] == pytest.approx(0.8)

    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_entry_zone(self, mock_event_bus):
        mock_event_bus.publish = AsyncMock()
        strategies = [
            MockStrategy("s1", 0.15, Direction.LONG, 0.8),
            MockStrategy("s2", 0.25, Direction.LONG, 0.7),
            MockStrategy("s3", 0.10, Direction.LONG, 0.6),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_candles(60))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        assert result is not None
        low, high = result.entry_zone
        # LONG: entry_zone favors lower entry (low, entry_price)
        assert low < result.entry_price
        assert high == result.entry_price

    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_dominant_direction_wins(self, mock_event_bus):
        """4 LONG vs 1 SHORT → LONG wins."""
        mock_event_bus.publish = AsyncMock()
        strategies = [
            MockStrategy("s1", 0.15, Direction.LONG, 0.7),
            MockStrategy("s2", 0.25, Direction.LONG, 0.7),
            MockStrategy("s3", 0.10, Direction.LONG, 0.6),
            MockStrategy("s4", 0.10, Direction.LONG, 0.5),
            MockStrategy("s5", 0.05, Direction.SHORT, -0.9),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_candles(60))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        assert result is not None
        assert result.direction == Direction.LONG

    @patch("app.signals.aggregator.event_bus")
    async def test_aggregate_market_context_populated(self, mock_event_bus):
        mock_event_bus.publish = AsyncMock()
        strategies = [
            MockStrategy("s1", 0.15, Direction.LONG, 0.8),
            MockStrategy("s2", 0.25, Direction.LONG, 0.7),
            MockStrategy("s3", 0.10, Direction.LONG, 0.6),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_candles(60))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        assert result is not None
        assert result.market_context is not None
        assert result.market_context.regime is not None
