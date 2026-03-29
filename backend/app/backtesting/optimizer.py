"""Parameter optimizer for strategy backtesting.

Uses random search (lightweight, no Optuna dependency) to find optimal
strategy parameters by maximizing Sharpe ratio subject to constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from app.backtesting.engine import BacktestEngine
from app.core.models import BacktestConfig, BacktestResult, Candle
from app.strategies.base import BaseStrategy


@dataclass
class ParamSpace:
    """Defines a parameter search space."""

    name: str
    low: float
    high: float
    step: float | None = None  # If set, restricts to discrete steps
    param_type: str = "float"  # "float" or "int"

    def sample(self, rng: np.random.Generator) -> float | int:
        """Sample a random value from this parameter space."""
        if self.param_type == "int":
            return int(rng.integers(int(self.low), int(self.high) + 1))
        if self.step:
            n_steps = int((self.high - self.low) / self.step)
            step_idx = rng.integers(0, n_steps + 1)
            return self.low + step_idx * self.step
        return float(rng.uniform(self.low, self.high))


@dataclass
class OptimizationTrial:
    """Result of a single optimization trial."""

    trial_id: int
    params: dict[str, Any]
    sharpe_ratio: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    profit_factor: float = 0.0
    is_feasible: bool = True  # Met all constraints


@dataclass
class OptimizationResult:
    """Complete optimization result."""

    best_params: dict[str, Any] = field(default_factory=dict)
    best_sharpe: float = 0.0
    best_result: BacktestResult | None = None
    all_trials: list[OptimizationTrial] = field(default_factory=list)
    n_trials: int = 0
    n_feasible: int = 0


class StrategyOptimizer:
    """Random search optimizer for strategy parameters.

    Evaluates different parameter combinations by running backtests
    and selecting the combination that maximizes the objective (Sharpe ratio)
    while satisfying constraints (max drawdown, min trades).

    Args:
        strategy_factory: Callable that takes a params dict and returns
            a list of BaseStrategy instances configured with those params.
        config: Backtest configuration.
        param_spaces: List of ParamSpace defining the search space.
        n_trials: Number of random trials to run.
        max_drawdown: Maximum allowed drawdown (constraint).
        min_trades: Minimum number of trades required (constraint).
        objective: Metric to optimize ("sharpe", "return", "calmar").
        seed: Random seed for reproducibility.
    """

    def __init__(
        self,
        strategy_factory: Callable[[dict[str, Any]], list[BaseStrategy]],
        config: BacktestConfig,
        param_spaces: list[ParamSpace],
        n_trials: int = 50,
        max_drawdown: float = 0.15,
        min_trades: int = 10,
        objective: str = "sharpe",
        seed: int | None = None,
    ):
        self.strategy_factory = strategy_factory
        self.config = config
        self.param_spaces = param_spaces
        self.n_trials = n_trials
        self.max_drawdown = max_drawdown
        self.min_trades = min_trades
        self.objective = objective
        self._rng = np.random.default_rng(seed)

    def optimize(self, candles: list[Candle]) -> OptimizationResult:
        """Run optimization over parameter space.

        Args:
            candles: Historical candle data for backtesting.

        Returns:
            OptimizationResult with best parameters and all trials.
        """
        trials: list[OptimizationTrial] = []
        best_score = -np.inf
        best_params: dict[str, Any] = {}
        best_bt_result: BacktestResult | None = None
        n_feasible = 0

        for i in range(self.n_trials):
            # Sample parameters
            params = {ps.name: ps.sample(self._rng) for ps in self.param_spaces}

            # Create strategies with these params
            try:
                strategies = self.strategy_factory(params)
            except Exception:
                continue

            # Run backtest
            engine = BacktestEngine(strategies, self.config)
            result = engine.run(candles)

            # Check constraints
            feasible = (
                result.max_drawdown <= self.max_drawdown
                and result.total_trades >= self.min_trades
            )

            trial = OptimizationTrial(
                trial_id=i,
                params=params,
                sharpe_ratio=result.sharpe_ratio,
                total_return=result.total_return,
                max_drawdown=result.max_drawdown,
                total_trades=result.total_trades,
                profit_factor=result.profit_factor,
                is_feasible=feasible,
            )
            trials.append(trial)

            if feasible:
                n_feasible += 1
                score = self._get_objective_score(result)
                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    best_bt_result = result

        return OptimizationResult(
            best_params=best_params,
            best_sharpe=best_score if best_score != -np.inf else 0.0,
            best_result=best_bt_result,
            all_trials=trials,
            n_trials=len(trials),
            n_feasible=n_feasible,
        )

    def _get_objective_score(self, result: BacktestResult) -> float:
        """Get the objective score from a backtest result."""
        if self.objective == "sharpe":
            return result.sharpe_ratio
        elif self.objective == "return":
            return result.total_return
        elif self.objective == "calmar":
            if result.max_drawdown > 0:
                return result.annual_return / result.max_drawdown
            return 0.0
        return result.sharpe_ratio

    def grid_search(self, candles: list[Candle]) -> OptimizationResult:
        """Exhaustive grid search over discrete parameter space.

        Only works with ParamSpace that have `step` defined.
        Falls back to random search for continuous params.

        Args:
            candles: Historical candle data.

        Returns:
            OptimizationResult.
        """
        import itertools

        grids = {}
        for ps in self.param_spaces:
            if ps.step:
                n_steps = int((ps.high - ps.low) / ps.step) + 1
                values = [ps.low + i * ps.step for i in range(n_steps)]
                if ps.param_type == "int":
                    values = [int(v) for v in values]
                grids[ps.name] = values
            elif ps.param_type == "int":
                grids[ps.name] = list(range(int(ps.low), int(ps.high) + 1))
            else:
                # Can't grid-search continuous params, sample 5 points
                grids[ps.name] = np.linspace(ps.low, ps.high, 5).tolist()

        keys = list(grids.keys())
        combos = list(itertools.product(*[grids[k] for k in keys]))

        trials: list[OptimizationTrial] = []
        best_score = -np.inf
        best_params: dict[str, Any] = {}
        best_bt_result: BacktestResult | None = None
        n_feasible = 0

        for i, combo in enumerate(combos):
            params = dict(zip(keys, combo))

            try:
                strategies = self.strategy_factory(params)
            except Exception:
                continue

            engine = BacktestEngine(strategies, self.config)
            result = engine.run(candles)

            feasible = (
                result.max_drawdown <= self.max_drawdown
                and result.total_trades >= self.min_trades
            )

            trial = OptimizationTrial(
                trial_id=i,
                params=params,
                sharpe_ratio=result.sharpe_ratio,
                total_return=result.total_return,
                max_drawdown=result.max_drawdown,
                total_trades=result.total_trades,
                profit_factor=result.profit_factor,
                is_feasible=feasible,
            )
            trials.append(trial)

            if feasible:
                n_feasible += 1
                score = self._get_objective_score(result)
                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    best_bt_result = result

        return OptimizationResult(
            best_params=best_params,
            best_sharpe=best_score if best_score != -np.inf else 0.0,
            best_result=best_bt_result,
            all_trials=trials,
            n_trials=len(trials),
            n_feasible=n_feasible,
        )
