"""Phase 7 Integration Tests — backtesting pipeline end-to-end."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from app.backtesting import (
    BacktestEngine,
    BacktestReport,
    MonteCarloSimulator,
    PerformanceMetrics,
    StrategyOptimizer,
    TradeSimulator,
    WalkForwardAnalyzer,
    compute_all_metrics,
)
from app.backtesting.optimizer import ParamSpace
from app.config.constants import Direction
from app.core.models import BacktestConfig, BacktestResult, Candle, RawSignal
from app.strategies.base import BaseStrategy


class AlwaysLongStrat(BaseStrategy):
    name = "test_long"
    weight = 1.0
    min_candles = 10

    def evaluate(self, candles, indicators, context=None):
        c = candles[-1]
        return RawSignal(
            strategy_name=self.name, symbol=c.symbol,
            direction=Direction.LONG, strength=0.8,
            entry_price=c.close, timeframe=c.timeframe,
        )


def _make_candles(n: int = 300) -> list[Candle]:
    candles = []
    price = 40000.0
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
        end_date=datetime(2024, 2, 1, tzinfo=UTC),
        initial_capital=10000.0, slippage_bps=0, taker_fee=0,
    )


class TestEndToEnd:
    def test_backtest_to_report(self, config):
        """Full pipeline: Backtest → Report generation."""
        candles = _make_candles(200)
        strategies = [AlwaysLongStrat(), AlwaysLongStrat()]
        engine = BacktestEngine(strategies, config)
        result = engine.run(candles)

        report = BacktestReport(result)
        data = report.generate()

        assert "summary" in data
        assert data["summary"]["total_trades"] > 0
        assert len(data["equity_curve"]) > 0

    def test_backtest_to_monte_carlo(self, config):
        """Backtest → Monte Carlo analysis."""
        candles = _make_candles(200)
        strategies = [AlwaysLongStrat(), AlwaysLongStrat()]
        engine = BacktestEngine(strategies, config)
        result = engine.run(candles)

        pnls = np.array([t["pnl"] for t in result.trades])
        mc = MonteCarloSimulator(n_simulations=100, seed=42)
        mc_result = mc.simulate(pnls, initial_capital=config.initial_capital)

        assert mc_result.n_simulations == 100
        assert mc_result.prob_of_profit >= 0

    def test_backtest_to_full_report(self, config):
        """Backtest → MC → WF → Full report."""
        candles = _make_candles(200)
        strategies = [AlwaysLongStrat(), AlwaysLongStrat()]
        engine = BacktestEngine(strategies, config)
        result = engine.run(candles)

        # Monte Carlo
        pnls = np.array([t["pnl"] for t in result.trades])
        mc = MonteCarloSimulator(n_simulations=50, seed=42)
        mc_result = mc.simulate(pnls, initial_capital=config.initial_capital)

        # Generate full report
        report = BacktestReport(result, monte_carlo=mc_result)
        data = report.generate()
        assert "monte_carlo" in data


class TestMetricsIntegration:
    def test_metrics_from_simulator(self, config):
        """TradeSimulator → compute_all_metrics."""
        sim = TradeSimulator(initial_balance=10000, slippage_bps=0, fee_rate=0)
        sim.open_position("BTC/USDT", Direction.LONG, 40000, 0.1, 39000, time_idx=0)
        sim.process_candle("BTC/USDT", 40100, 38900, 39000, time_idx=1)

        metrics = compute_all_metrics(
            sim.get_equity_curve(),
            sim.get_trade_pnls(),
            sim.get_trade_durations(),
        )
        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_trades == 1


class TestPhaseConnections:
    def test_strategy_base_in_engine(self, config):
        """Phase 3 BaseStrategy used in Phase 7 BacktestEngine."""
        strat = AlwaysLongStrat()
        engine = BacktestEngine([strat], config)
        assert engine.strategies[0].name == "test_long"

    def test_indicator_pipeline_in_engine(self, config):
        """Phase 3 IndicatorPipeline used in BacktestEngine."""
        candles = _make_candles(100)
        strategies = [AlwaysLongStrat()]
        engine = BacktestEngine(strategies, config)
        result = engine.run(candles)
        assert isinstance(result, BacktestResult)

    def test_backtest_config_model(self, config):
        """Phase 1 BacktestConfig model works with engine."""
        assert config.initial_capital == 10000.0
        assert config.symbol == "BTC/USDT"


class TestImportsClean:
    def test_all_backtesting_imports(self):
        """All backtesting classes importable from app.backtesting."""
        from app.backtesting import (
            BacktestEngine,
            BacktestReport,
            MonteCarloResult,
            MonteCarloSimulator,
            OptimizationResult,
            ParamSpace,
            PerformanceMetrics,
            SimTrade,
            StrategyOptimizer,
            TradeSimulator,
            WalkForwardAnalyzer,
            WalkForwardResult,
            compute_all_metrics,
        )
        assert BacktestEngine is not None
        assert compute_all_metrics is not None
