"""Walk-Forward Analysis — rolling window in-sample/out-of-sample validation.

Splits historical data into sequential windows:
  [---in-sample---][--out-of-sample--]
                   [---in-sample---][--out-of-sample--]
                                    [---in-sample---][--out-of-sample--]

Tracks out-of-sample consistency across all windows.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.backtesting.engine import BacktestEngine
from app.backtesting.metrics import PerformanceMetrics, compute_all_metrics
from app.core.models import BacktestConfig, BacktestResult, Candle
from app.strategies.base import BaseStrategy


@dataclass
class WFWindow:
    """A single walk-forward window result."""

    window_id: int
    in_sample_start: int  # Index into candle array
    in_sample_end: int
    oos_start: int  # Out-of-sample start
    oos_end: int
    in_sample_result: BacktestResult | None = None
    oos_result: BacktestResult | None = None
    in_sample_sharpe: float = 0.0
    oos_sharpe: float = 0.0
    oos_return: float = 0.0
    efficiency_ratio: float = 0.0  # OOS Sharpe / IS Sharpe


@dataclass
class WalkForwardResult:
    """Complete walk-forward analysis result."""

    windows: list[WFWindow] = field(default_factory=list)
    avg_oos_return: float = 0.0
    avg_oos_sharpe: float = 0.0
    avg_efficiency_ratio: float = 0.0
    consistency_score: float = 0.0  # % of OOS windows that are profitable
    total_candles: int = 0
    n_windows: int = 0


class WalkForwardAnalyzer:
    """Performs walk-forward validation on historical data.

    NOTE: This is a rolling window validation — it runs the same fixed-parameter
    strategies across all windows. It does NOT re-optimize parameters per window.
    For true adaptive walk-forward with per-window optimization, pass an
    ``optimizer`` callback (planned future enhancement).

    Args:
        strategies: List of strategies to evaluate (fixed parameters).
        config: Backtest configuration (capital, fees, etc.).
        in_sample_size: Number of candles for in-sample period.
        oos_size: Number of candles for out-of-sample period.
        step_size: Number of candles to roll forward each window.
            Defaults to oos_size (non-overlapping OOS).
    """

    def __init__(
        self,
        strategies: list[BaseStrategy],
        config: BacktestConfig,
        in_sample_size: int = 500,
        oos_size: int = 168,  # ~1 week of hourly candles
        step_size: int | None = None,
    ):
        self.strategies = strategies
        self.config = config
        self.in_sample_size = in_sample_size
        self.oos_size = oos_size
        self.step_size = step_size or oos_size

    def analyze(self, candles: list[Candle]) -> WalkForwardResult:
        """Run walk-forward analysis on historical candles.

        Args:
            candles: Full historical candle array (must be long enough
                     for at least one IS + OOS window).

        Returns:
            WalkForwardResult with per-window and aggregate metrics.
        """
        total = len(candles)
        min_required = self.in_sample_size + self.oos_size

        if total < min_required:
            return WalkForwardResult(total_candles=total)

        windows: list[WFWindow] = []
        window_id = 0
        start = 0

        while start + min_required <= total:
            is_start = start
            is_end = start + self.in_sample_size
            oos_start = is_end
            oos_end = min(oos_start + self.oos_size, total)

            is_candles = candles[is_start:is_end]
            oos_candles = candles[oos_start:oos_end]

            # Run in-sample backtest
            is_engine = BacktestEngine(self.strategies, self.config)
            is_result = is_engine.run(is_candles)

            # Run out-of-sample backtest
            oos_engine = BacktestEngine(self.strategies, self.config)
            oos_result = oos_engine.run(oos_candles)

            efficiency = 0.0
            if is_result.sharpe_ratio != 0:
                efficiency = oos_result.sharpe_ratio / is_result.sharpe_ratio

            wf = WFWindow(
                window_id=window_id,
                in_sample_start=is_start,
                in_sample_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
                in_sample_result=is_result,
                oos_result=oos_result,
                in_sample_sharpe=is_result.sharpe_ratio,
                oos_sharpe=oos_result.sharpe_ratio,
                oos_return=oos_result.total_return,
                efficiency_ratio=efficiency,
            )
            windows.append(wf)

            start += self.step_size
            window_id += 1

        return self._aggregate(windows, total)

    def _aggregate(self, windows: list[WFWindow], total_candles: int) -> WalkForwardResult:
        """Aggregate per-window results into summary."""
        if not windows:
            return WalkForwardResult(total_candles=total_candles)

        n = len(windows)
        avg_ret = sum(w.oos_return for w in windows) / n
        avg_sharpe = sum(w.oos_sharpe for w in windows) / n
        avg_eff = sum(w.efficiency_ratio for w in windows) / n

        profitable = sum(1 for w in windows if w.oos_return > 0)
        consistency = profitable / n

        return WalkForwardResult(
            windows=windows,
            avg_oos_return=avg_ret,
            avg_oos_sharpe=avg_sharpe,
            avg_efficiency_ratio=avg_eff,
            consistency_score=consistency,
            total_candles=total_candles,
            n_windows=n,
        )
