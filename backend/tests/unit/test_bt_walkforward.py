"""Tests for walk-forward analysis."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from app.backtesting.walk_forward import WalkForwardAnalyzer, WalkForwardResult, WFWindow
from app.config.constants import Direction
from app.core.models import BacktestConfig, Candle, IndicatorValues, MarketContext, RawSignal
from app.strategies.base import BaseStrategy


class AlwaysLongStrategy(BaseStrategy):
    name = "always_long"
    weight = 1.0
    min_candles = 10

    def evaluate(self, candles, indicators, context=None):
        c = candles[-1]
        return RawSignal(
            strategy_name=self.name, symbol=c.symbol,
            direction=Direction.LONG, strength=0.8,
            entry_price=c.close, timeframe=c.timeframe,
        )


def _make_candles(n: int, start_price: float = 40000.0) -> list[Candle]:
    candles = []
    price = start_price
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    np.random.seed(42)
    for i in range(n):
        change = np.random.normal(0.001, 0.01)
        price *= (1 + change)
        candles.append(Candle(
            time=base_time + timedelta(hours=i),
            symbol="BTC/USDT", timeframe="1h",
            open=price * 0.999, high=price * 1.005,
            low=price * 0.995, close=price,
            volume=np.random.uniform(100, 1000),
        ))
    return candles


@pytest.fixture
def config():
    return BacktestConfig(
        strategy_name="test", symbol="BTC/USDT", timeframe="1h",
        start_date=datetime(2024, 1, 1, tzinfo=UTC),
        end_date=datetime(2024, 6, 1, tzinfo=UTC),
        initial_capital=10000.0, slippage_bps=0, taker_fee=0,
    )


class TestWFInit:
    def test_defaults(self, config):
        wfa = WalkForwardAnalyzer([AlwaysLongStrategy()], config)
        assert wfa.in_sample_size == 500
        assert wfa.oos_size == 168
        assert wfa.step_size == 168

    def test_custom_sizes(self, config):
        wfa = WalkForwardAnalyzer(
            [AlwaysLongStrategy()], config,
            in_sample_size=200, oos_size=50, step_size=25,
        )
        assert wfa.in_sample_size == 200
        assert wfa.oos_size == 50
        assert wfa.step_size == 25


class TestWFAnalyze:
    def test_insufficient_data(self, config):
        wfa = WalkForwardAnalyzer(
            [AlwaysLongStrategy()], config,
            in_sample_size=100, oos_size=50,
        )
        candles = _make_candles(100)  # Not enough for 100 + 50
        result = wfa.analyze(candles)
        assert isinstance(result, WalkForwardResult)
        assert result.n_windows == 0

    def test_single_window(self, config):
        wfa = WalkForwardAnalyzer(
            [AlwaysLongStrategy()], config,
            in_sample_size=100, oos_size=50,
        )
        candles = _make_candles(160)  # Enough for 1 window (100 + 50)
        result = wfa.analyze(candles)
        assert result.n_windows == 1
        assert len(result.windows) == 1
        w = result.windows[0]
        assert w.in_sample_start == 0
        assert w.in_sample_end == 100
        assert w.oos_start == 100

    def test_multiple_windows(self, config):
        wfa = WalkForwardAnalyzer(
            [AlwaysLongStrategy()], config,
            in_sample_size=100, oos_size=50, step_size=50,
        )
        candles = _make_candles(300)  # Room for multiple windows
        result = wfa.analyze(candles)
        assert result.n_windows >= 2

    def test_oos_metrics_populated(self, config):
        strategies = [AlwaysLongStrategy(), AlwaysLongStrategy()]
        wfa = WalkForwardAnalyzer(
            strategies, config,
            in_sample_size=100, oos_size=80,
        )
        candles = _make_candles(200)
        result = wfa.analyze(candles)
        assert result.n_windows >= 1
        w = result.windows[0]
        assert w.oos_result is not None
        assert w.in_sample_result is not None


class TestWFAggregates:
    def test_consistency_score(self, config):
        strategies = [AlwaysLongStrategy(), AlwaysLongStrategy()]
        wfa = WalkForwardAnalyzer(
            strategies, config,
            in_sample_size=100, oos_size=50, step_size=50,
        )
        candles = _make_candles(350)
        result = wfa.analyze(candles)
        assert 0.0 <= result.consistency_score <= 1.0

    def test_avg_metrics(self, config):
        strategies = [AlwaysLongStrategy(), AlwaysLongStrategy()]
        wfa = WalkForwardAnalyzer(
            strategies, config,
            in_sample_size=100, oos_size=50, step_size=50,
        )
        candles = _make_candles(350)
        result = wfa.analyze(candles)
        assert isinstance(result.avg_oos_return, float)
        assert isinstance(result.avg_oos_sharpe, float)
        assert isinstance(result.avg_efficiency_ratio, float)


class TestWFWindow:
    def test_window_fields(self):
        w = WFWindow(
            window_id=0,
            in_sample_start=0, in_sample_end=100,
            oos_start=100, oos_end=150,
        )
        assert w.window_id == 0
        assert w.efficiency_ratio == 0.0
        assert w.oos_sharpe == 0.0
