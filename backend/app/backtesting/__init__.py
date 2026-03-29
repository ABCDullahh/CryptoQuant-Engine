"""Backtesting module — engine, simulator, metrics, optimization, reports."""

from app.backtesting.data_loader import generate_synthetic_candles, load_candles, normalize_symbol
from app.backtesting.engine import BacktestEngine
from app.backtesting.job_runner import BacktestJobRunner, job_runner
from app.backtesting.metrics import PerformanceMetrics, compute_all_metrics
from app.backtesting.monte_carlo import MonteCarloResult, MonteCarloSimulator
from app.backtesting.optimizer import (
    OptimizationResult,
    ParamSpace,
    StrategyOptimizer,
)
from app.backtesting.report import BacktestReport
from app.backtesting.simulator import SimTrade, TradeSimulator
from app.backtesting.strategy_factory import create_strategies
from app.backtesting.walk_forward import WalkForwardAnalyzer, WalkForwardResult

__all__ = [
    "BacktestEngine",
    "BacktestJobRunner",
    "BacktestReport",
    "MonteCarloResult",
    "MonteCarloSimulator",
    "OptimizationResult",
    "ParamSpace",
    "PerformanceMetrics",
    "SimTrade",
    "StrategyOptimizer",
    "TradeSimulator",
    "WalkForwardAnalyzer",
    "WalkForwardResult",
    "compute_all_metrics",
    "create_strategies",
    "generate_synthetic_candles",
    "job_runner",
    "load_candles",
    "normalize_symbol",
]
