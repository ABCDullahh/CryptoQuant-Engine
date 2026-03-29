"""Report generator for backtest results.

Generates structured JSON reports with equity curve, drawdown analysis,
trade list, monthly returns heatmap data, and summary statistics.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.backtesting.metrics import (
    PerformanceMetrics,
    calc_drawdown_series,
    calc_returns_from_equity,
    compute_all_metrics,
)
from app.backtesting.monte_carlo import MonteCarloResult
from app.backtesting.walk_forward import WalkForwardResult
from app.core.models import BacktestResult


@dataclass
class ReportSection:
    """A named section of the report."""

    title: str
    data: dict | list


class BacktestReport:
    """Generates comprehensive backtest reports in JSON format.

    Sections:
    1. Summary - Key metrics at a glance
    2. Equity Curve - Equity values over time
    3. Drawdown Analysis - Drawdown series and stats
    4. Trade List - All trades with details
    5. Monthly Returns - Month-by-month breakdown
    6. Monte Carlo - MC simulation results (if provided)
    7. Walk-Forward - WF analysis results (if provided)
    """

    def __init__(
        self,
        backtest_result: BacktestResult,
        monte_carlo: MonteCarloResult | None = None,
        walk_forward: WalkForwardResult | None = None,
    ):
        self.bt = backtest_result
        self.mc = monte_carlo
        self.wf = walk_forward

    def generate(self) -> dict[str, Any]:
        """Generate full report as a dictionary."""
        report: dict[str, Any] = {
            "generated_at": datetime.now(tz=__import__("datetime").UTC).isoformat(),
            "config": self._config_section(),
            "summary": self._summary_section(),
            "equity_curve": self._equity_curve_section(),
            "drawdown": self._drawdown_section(),
            "trades": self._trades_section(),
            "monthly_returns": self._monthly_returns_section(),
        }

        if self.mc:
            report["monte_carlo"] = self._monte_carlo_section()

        if self.wf:
            report["walk_forward"] = self._walk_forward_section()

        return report

    def _config_section(self) -> dict:
        """Backtest configuration."""
        cfg = self.bt.config
        return {
            "strategy": cfg.strategy_name,
            "symbol": cfg.symbol,
            "timeframe": cfg.timeframe,
            "start_date": str(cfg.start_date),
            "end_date": str(cfg.end_date),
            "initial_capital": cfg.initial_capital,
            "risk_per_trade": cfg.risk_per_trade,
            "slippage_bps": cfg.slippage_bps,
            "taker_fee": cfg.taker_fee,
        }

    def _summary_section(self) -> dict:
        """Key performance metrics summary."""
        return {
            "total_return_pct": round(self.bt.total_return * 100, 2),
            "annual_return_pct": round(self.bt.annual_return * 100, 2),
            "sharpe_ratio": round(self.bt.sharpe_ratio, 2),
            "sortino_ratio": round(self.bt.sortino_ratio, 2),
            "max_drawdown_pct": round(self.bt.max_drawdown * 100, 2),
            "win_rate_pct": round(self.bt.win_rate * 100, 1),
            "profit_factor": round(self.bt.profit_factor, 2),
            "total_trades": self.bt.total_trades,
            "expectancy": round(self.bt.expectancy, 2),
            "avg_holding_period": self.bt.avg_holding_period,
        }

    def _equity_curve_section(self) -> list[dict]:
        """Equity curve data points."""
        return self.bt.equity_curve

    def _drawdown_section(self) -> dict:
        """Drawdown analysis."""
        equities = [p.get("equity", 0) for p in self.bt.equity_curve]
        if len(equities) < 2:
            return {"max_drawdown_pct": 0, "drawdown_series": []}

        eq_arr = np.array(equities)
        dd = calc_drawdown_series(eq_arr)

        # Find top 5 drawdown periods
        dd_list = dd.tolist()

        return {
            "max_drawdown_pct": round(self.bt.max_drawdown * 100, 2),
            "drawdown_series": [
                {"index": i, "drawdown_pct": round(v * 100, 4)}
                for i, v in enumerate(dd_list)
            ],
        }

    def _trades_section(self) -> dict:
        """Trade list with statistics."""
        trades = self.bt.trades
        if not trades:
            return {"count": 0, "trades": []}

        winners = [t for t in trades if t.get("pnl", 0) > 0]
        losers = [t for t in trades if t.get("pnl", 0) <= 0]

        return {
            "count": len(trades),
            "winners": len(winners),
            "losers": len(losers),
            "trades": trades,
        }

    def _monthly_returns_section(self) -> dict:
        """Monthly returns data for heatmap."""
        monthly = self.bt.monthly_returns
        if not monthly:
            return {"months": []}

        months = []
        for month_key, ret in sorted(monthly.items()):
            months.append({
                "month": month_key,
                "return_pct": round(ret * 100, 2),
            })

        return {"months": months}

    def _monte_carlo_section(self) -> dict:
        """Monte Carlo simulation results."""
        if not self.mc:
            return {}

        return {
            "n_simulations": self.mc.n_simulations,
            "n_trades": self.mc.n_trades,
            "return_distribution": {
                "mean_pct": round(self.mc.mean_return * 100, 2),
                "median_pct": round(self.mc.median_return * 100, 2),
                "ci_5_pct": round(self.mc.return_ci_5 * 100, 2),
                "ci_95_pct": round(self.mc.return_ci_95 * 100, 2),
            },
            "drawdown_distribution": {
                "mean_pct": round(self.mc.mean_max_drawdown * 100, 2),
                "worst_95_pct": round(self.mc.worst_drawdown_95 * 100, 2),
                "worst_99_pct": round(self.mc.worst_drawdown_99 * 100, 2),
            },
            "sharpe_distribution": {
                "mean": round(self.mc.mean_sharpe, 2),
                "ci_5": round(self.mc.sharpe_ci_5, 2),
                "ci_95": round(self.mc.sharpe_ci_95, 2),
            },
            "prob_of_profit_pct": round(self.mc.prob_of_profit * 100, 1),
            "prob_of_ruin_pct": round(self.mc.prob_of_ruin * 100, 1),
            "ruin_threshold_pct": round(self.mc.ruin_threshold * 100, 0),
        }

    def _walk_forward_section(self) -> dict:
        """Walk-forward analysis results."""
        if not self.wf:
            return {}

        windows = []
        for w in self.wf.windows:
            windows.append({
                "window_id": w.window_id,
                "is_sharpe": round(w.in_sample_sharpe, 2),
                "oos_sharpe": round(w.oos_sharpe, 2),
                "oos_return_pct": round(w.oos_return * 100, 2),
                "efficiency_ratio": round(w.efficiency_ratio, 2),
            })

        return {
            "n_windows": self.wf.n_windows,
            "avg_oos_return_pct": round(self.wf.avg_oos_return * 100, 2),
            "avg_oos_sharpe": round(self.wf.avg_oos_sharpe, 2),
            "avg_efficiency_ratio": round(self.wf.avg_efficiency_ratio, 2),
            "consistency_score_pct": round(self.wf.consistency_score * 100, 1),
            "windows": windows,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        report = self.generate()
        return json.dumps(report, indent=indent, default=str)

    def save(self, path: str | Path) -> Path:
        """Save report to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())
        return path
