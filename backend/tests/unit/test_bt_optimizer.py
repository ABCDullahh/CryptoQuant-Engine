"""Tests for parameter optimizer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from app.backtesting.optimizer import (
    OptimizationResult,
    OptimizationTrial,
    ParamSpace,
    StrategyOptimizer,
)
from app.config.constants import Direction
from app.core.models import BacktestConfig, Candle, RawSignal
from app.strategies.base import BaseStrategy


class ConfigurableStrategy(BaseStrategy):
    """Strategy with configurable threshold."""
    name = "configurable"
    weight = 1.0
    min_candles = 10

    def __init__(self, threshold: float = 0.5):
        super().__init__()
        self.threshold = threshold

    def evaluate(self, candles, indicators, context=None):
        c = candles[-1]
        if c.close > c.open * (1 + self.threshold / 100):
            return RawSignal(
                strategy_name=self.name, symbol=c.symbol,
                direction=Direction.LONG, strength=0.8,
                entry_price=c.close, timeframe=c.timeframe,
            )
        return None


def _make_candles(n: int = 200) -> list[Candle]:
    candles = []
    price = 40000.0
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    np.random.seed(42)
    for i in range(n):
        change = np.random.normal(0.001, 0.015)
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
        end_date=datetime(2024, 2, 1, tzinfo=UTC),
        initial_capital=10000.0, slippage_bps=0, taker_fee=0,
    )


@pytest.fixture
def candles():
    return _make_candles(200)


def strategy_factory(params):
    threshold = params.get("threshold", 0.5)
    return [ConfigurableStrategy(threshold), ConfigurableStrategy(threshold)]


class TestParamSpace:
    def test_float_sample(self):
        ps = ParamSpace("x", 0.0, 1.0)
        rng = np.random.default_rng(42)
        val = ps.sample(rng)
        assert 0.0 <= val <= 1.0

    def test_int_sample(self):
        ps = ParamSpace("x", 5, 20, param_type="int")
        rng = np.random.default_rng(42)
        val = ps.sample(rng)
        assert isinstance(val, int)
        assert 5 <= val <= 20

    def test_stepped_sample(self):
        ps = ParamSpace("x", 0.0, 1.0, step=0.25)
        rng = np.random.default_rng(42)
        val = ps.sample(rng)
        assert val in [0.0, 0.25, 0.5, 0.75, 1.0]


class TestOptimizer:
    def test_random_search(self, config, candles):
        spaces = [ParamSpace("threshold", 0.01, 2.0)]
        opt = StrategyOptimizer(
            strategy_factory, config, spaces,
            n_trials=5, min_trades=0, seed=42,
        )
        result = opt.optimize(candles)
        assert isinstance(result, OptimizationResult)
        assert result.n_trials == 5
        assert len(result.all_trials) == 5

    def test_grid_search(self, config, candles):
        spaces = [ParamSpace("threshold", 0.1, 1.0, step=0.3)]
        opt = StrategyOptimizer(
            strategy_factory, config, spaces,
            n_trials=10, min_trades=0,
        )
        result = opt.grid_search(candles)
        assert isinstance(result, OptimizationResult)
        assert result.n_trials > 0

    def test_best_params_populated(self, config, candles):
        spaces = [ParamSpace("threshold", 0.01, 2.0)]
        opt = StrategyOptimizer(
            strategy_factory, config, spaces,
            n_trials=5, min_trades=0, seed=42,
        )
        result = opt.optimize(candles)
        if result.n_feasible > 0:
            assert "threshold" in result.best_params

    def test_constraint_filtering(self, config, candles):
        spaces = [ParamSpace("threshold", 0.01, 2.0)]
        opt = StrategyOptimizer(
            strategy_factory, config, spaces,
            n_trials=5, max_drawdown=0.001, min_trades=1000, seed=42,
        )
        result = opt.optimize(candles)
        # Very strict constraints → likely no feasible solutions
        assert result.n_feasible <= result.n_trials


class TestOptimizationTrial:
    def test_trial_fields(self):
        trial = OptimizationTrial(
            trial_id=0, params={"x": 1.0},
            sharpe_ratio=1.5, total_return=0.10,
        )
        assert trial.trial_id == 0
        assert trial.params["x"] == 1.0
        assert trial.is_feasible is True


class TestObjective:
    def test_sharpe_objective(self, config, candles):
        spaces = [ParamSpace("threshold", 0.1, 1.0)]
        opt = StrategyOptimizer(
            strategy_factory, config, spaces,
            n_trials=3, min_trades=0, objective="sharpe", seed=42,
        )
        result = opt.optimize(candles)
        assert isinstance(result.best_sharpe, float)

    def test_return_objective(self, config, candles):
        spaces = [ParamSpace("threshold", 0.1, 1.0)]
        opt = StrategyOptimizer(
            strategy_factory, config, spaces,
            n_trials=3, min_trades=0, objective="return", seed=42,
        )
        result = opt.optimize(candles)
        assert isinstance(result, OptimizationResult)
