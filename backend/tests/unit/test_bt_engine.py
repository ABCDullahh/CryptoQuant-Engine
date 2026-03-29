"""Tests for backtesting engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from app.backtesting.engine import BacktestEngine
from app.backtesting.simulator import TradeSimulator
from app.config.constants import Direction
from app.core.models import (
    BacktestConfig,
    BacktestResult,
    Candle,
    IndicatorValues,
    MarketContext,
    RawSignal,
)
from app.strategies.base import BaseStrategy


class AlwaysLongStrategy(BaseStrategy):
    """Test strategy that always signals LONG."""
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


class AlwaysShortStrategy(BaseStrategy):
    """Test strategy that always signals SHORT."""
    name = "always_short"
    weight = 1.0
    min_candles = 10

    def evaluate(self, candles, indicators, context=None):
        c = candles[-1]
        return RawSignal(
            strategy_name=self.name, symbol=c.symbol,
            direction=Direction.SHORT, strength=0.8,
            entry_price=c.close, timeframe=c.timeframe,
        )


class NeverSignalStrategy(BaseStrategy):
    """Test strategy that never signals."""
    name = "never_signal"
    weight = 1.0
    min_candles = 10

    def evaluate(self, candles, indicators, context=None):
        return None


def _make_candles(n: int = 200, start_price: float = 40000.0, symbol: str = "BTC/USDT") -> list[Candle]:
    """Generate synthetic candles with upward trend."""
    candles = []
    price = start_price
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    np.random.seed(42)

    for i in range(n):
        change = np.random.normal(0.001, 0.01)  # Slight upward bias
        price *= (1 + change)
        high = price * (1 + abs(np.random.normal(0, 0.005)))
        low = price * (1 - abs(np.random.normal(0, 0.005)))
        candles.append(Candle(
            time=base_time + timedelta(hours=i),
            symbol=symbol,
            timeframe="1h",
            open=price * (1 - change / 2),
            high=high,
            low=low,
            close=price,
            volume=np.random.uniform(100, 1000),
        ))
    return candles


@pytest.fixture
def config():
    return BacktestConfig(
        strategy_name="test",
        symbol="BTC/USDT",
        timeframe="1h",
        start_date=datetime(2024, 1, 1, tzinfo=UTC),
        end_date=datetime(2024, 2, 1, tzinfo=UTC),
        initial_capital=10000.0,
        slippage_bps=0,
        taker_fee=0,
    )


@pytest.fixture
def candles():
    return _make_candles(200)


class TestEngineInit:
    def test_create_engine(self, config):
        engine = BacktestEngine([AlwaysLongStrategy()], config)
        assert len(engine.strategies) == 1
        assert engine.config.initial_capital == 10000.0

    def test_empty_candles(self, config):
        engine = BacktestEngine([AlwaysLongStrategy()], config)
        result = engine.run([])
        assert isinstance(result, BacktestResult)
        assert result.total_trades == 0


class TestEngineRun:
    def test_run_with_long_strategy(self, config, candles):
        """Two agreeing strategies → trades opened."""
        strategies = [AlwaysLongStrategy(), AlwaysLongStrategy()]
        engine = BacktestEngine(strategies, config)
        result = engine.run(candles)
        assert isinstance(result, BacktestResult)
        assert result.total_trades > 0

    def test_run_no_signal_strategy(self, config, candles):
        """No signals → no trades."""
        engine = BacktestEngine([NeverSignalStrategy()], config)
        result = engine.run(candles)
        assert result.total_trades == 0

    def test_run_single_strategy_needs_two(self, config, candles):
        """Single strategy can still trade with min_agree=1."""
        engine = BacktestEngine([AlwaysLongStrategy()], config)
        result = engine.run(candles)
        assert result.total_trades > 0  # min_agree = min(2, 1) = 1

    def test_equity_curve_populated(self, config, candles):
        strategies = [AlwaysLongStrategy(), AlwaysLongStrategy()]
        engine = BacktestEngine(strategies, config)
        result = engine.run(candles)
        assert len(result.equity_curve) > 0

    def test_trades_list_populated(self, config, candles):
        strategies = [AlwaysLongStrategy(), AlwaysLongStrategy()]
        engine = BacktestEngine(strategies, config)
        result = engine.run(candles)
        assert len(result.trades) > 0
        trade = result.trades[0]
        assert "entry_price" in trade
        assert "exit_price" in trade
        assert "pnl" in trade


class TestEngineMetrics:
    def test_metrics_computed(self, config, candles):
        strategies = [AlwaysLongStrategy(), AlwaysLongStrategy()]
        engine = BacktestEngine(strategies, config)
        result = engine.run(candles)
        # Metrics should be set (not default zeros for most)
        assert isinstance(result.sharpe_ratio, float)
        assert isinstance(result.max_drawdown, float)
        assert isinstance(result.win_rate, float)

    def test_short_strategy_metrics(self, config, candles):
        strategies = [AlwaysShortStrategy(), AlwaysShortStrategy()]
        engine = BacktestEngine(strategies, config)
        result = engine.run(candles)
        assert result.total_trades > 0


class TestForceClose:
    def test_remaining_positions_closed(self, config, candles):
        """All positions should be closed at end of backtest."""
        strategies = [AlwaysLongStrategy(), AlwaysLongStrategy()]
        engine = BacktestEngine(strategies, config)
        result = engine.run(candles)
        # After run, no open positions
        assert len(engine._simulator.positions) == 0


class TestBacktestResult:
    def test_result_fields(self, config, candles):
        strategies = [AlwaysLongStrategy(), AlwaysLongStrategy()]
        engine = BacktestEngine(strategies, config)
        result = engine.run(candles)
        assert result.config == config
        assert isinstance(result.total_return, float)
        assert isinstance(result.avg_holding_period, str)
        assert "candles" in result.avg_holding_period
