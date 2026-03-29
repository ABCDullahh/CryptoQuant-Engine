"""Phase 3 Integration Tests - IndicatorPipeline → Strategy → SignalAggregator."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from app.config.constants import Direction, MarketRegime, SignalGrade
from app.core.models import Candle, CompositeSignal, IndicatorValues, MarketContext
from app.indicators import IndicatorPipeline
from app.signals.aggregator import SignalAggregator
from app.signals.regime import MarketRegimeDetector
from app.strategies import STRATEGY_REGISTRY
from app.strategies.momentum import MomentumStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.smc import SmartMoneyStrategy
from app.strategies.volume import VolumeAnalysisStrategy
from app.strategies.funding import FundingArbStrategy


def _make_uptrend_candles(n: int = 200) -> list[Candle]:
    """Generate strong uptrend with realistic OHLCV."""
    np.random.seed(42)
    candles = []
    price = 42000.0
    for i in range(n):
        price += abs(np.random.randn()) * 10 + 2  # Bias upward
        noise = np.random.randn() * 5
        candles.append(Candle(
            time=datetime(2024, 1, 1, i % 24, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=price - 10, high=price + 20 + abs(noise),
            low=price - 20 - abs(noise), close=price,
            volume=100 + abs(np.random.randn() * 50),
        ))
    return candles


class TestPipelineToStrategy:
    def test_pipeline_output_feeds_momentum(self):
        """IndicatorPipeline → MomentumStrategy works end-to-end."""
        pipeline = IndicatorPipeline()
        strategy = MomentumStrategy()

        candles = _make_uptrend_candles(100)
        indicators = pipeline.compute(candles)

        # Should not crash; may or may not produce signal
        result = strategy.evaluate(candles, indicators)
        if result is not None:
            assert result.strategy_name == "momentum"
            assert -1 <= result.strength <= 1

    def test_pipeline_output_feeds_mean_reversion(self):
        pipeline = IndicatorPipeline()
        strategy = MeanReversionStrategy()
        candles = _make_uptrend_candles(60)
        indicators = pipeline.compute(candles)
        result = strategy.evaluate(candles, indicators)
        # In uptrend, mean_reversion unlikely to signal (price not at extremes)
        if result is not None:
            assert result.strategy_name == "mean_reversion"

    def test_pipeline_output_feeds_volume(self):
        pipeline = IndicatorPipeline()
        strategy = VolumeAnalysisStrategy()
        candles = _make_uptrend_candles(60)
        indicators = pipeline.compute(candles)
        result = strategy.evaluate(candles, indicators)
        if result is not None:
            assert result.strategy_name == "volume_analysis"

    def test_pipeline_output_feeds_smc(self):
        pipeline = IndicatorPipeline()
        strategy = SmartMoneyStrategy()
        candles = _make_uptrend_candles(120)
        indicators = pipeline.compute(candles)
        result = strategy.evaluate(candles, indicators)
        if result is not None:
            assert result.strategy_name == "smart_money"


class TestRegimeDetection:
    def test_regime_from_pipeline_output(self):
        pipeline = IndicatorPipeline()
        detector = MarketRegimeDetector()
        candles = _make_uptrend_candles(60)
        indicators = pipeline.compute(candles)
        context = detector.detect(candles, indicators)
        assert isinstance(context, MarketContext)
        assert context.regime in list(MarketRegime)


class TestStrategyRegistry:
    def test_all_strategies_registered(self):
        assert "momentum" in STRATEGY_REGISTRY
        assert "mean_reversion" in STRATEGY_REGISTRY
        assert "smart_money" in STRATEGY_REGISTRY
        assert "volume_analysis" in STRATEGY_REGISTRY
        assert "funding_arb" in STRATEGY_REGISTRY

    def test_registry_instantiation(self):
        # Alias keys map to same class as canonical key, so instance.name
        # equals the canonical name, not necessarily the alias key.
        for name, cls in STRATEGY_REGISTRY.items():
            instance = cls()
            assert instance.name  # has a name
            assert instance.weight > 0


class TestEndToEndAggregation:
    @patch("app.signals.aggregator.event_bus")
    async def test_full_pipeline_aggregation(self, mock_event_bus):
        """Complete flow: Candles → Indicators → Strategies → CompositeSignal."""
        mock_event_bus.publish = AsyncMock()

        strategies = [
            MomentumStrategy(),
            MeanReversionStrategy(),
            VolumeAnalysisStrategy(),
        ]
        agg = SignalAggregator(strategies)

        collector = AsyncMock()
        candles = _make_uptrend_candles(200)
        collector.get_candles = AsyncMock(return_value=candles)

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        # Result depends on actual indicator values
        # Just verify it doesn't crash and returns correct type
        if result is not None:
            assert isinstance(result, CompositeSignal)
            assert result.symbol == "BTC/USDT"
            assert len(result.take_profits) == 3
            assert result.position_size.quantity > 0
            assert result.market_context is not None

    @patch("app.signals.aggregator.event_bus")
    async def test_phase1_models_populated_correctly(self, mock_event_bus):
        """Verify Phase 1 model fields are populated in aggregation."""
        mock_event_bus.publish = AsyncMock()

        strategies = [
            MomentumStrategy(),
            MeanReversionStrategy(),
            VolumeAnalysisStrategy(),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_uptrend_candles(200))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        if result is not None:
            # CompositeSignal fields from Phase 1 models
            assert result.grade in list(SignalGrade)
            assert result.direction in (Direction.LONG, Direction.SHORT)
            assert 0 <= result.strength <= 1
            assert result.stop_loss > 0
            assert result.risk_reward.weighted_rr > 0
            assert result.position_size.risk_pct == 0.02

    @patch("app.signals.aggregator.event_bus")
    async def test_event_channel_integration(self, mock_event_bus):
        """Verify signal is published to correct EventChannel."""
        mock_event_bus.publish = AsyncMock()

        strategies = [
            MomentumStrategy(),
            MeanReversionStrategy(),
            VolumeAnalysisStrategy(),
        ]
        agg = SignalAggregator(strategies)
        collector = AsyncMock()
        collector.get_candles = AsyncMock(return_value=_make_uptrend_candles(200))

        result = await agg.aggregate(collector, "BTC/USDT", "1h")
        if result is not None:
            mock_event_bus.publish.assert_called_once()
            channel = mock_event_bus.publish.call_args[0][0]
            assert channel == "signal.composite"
