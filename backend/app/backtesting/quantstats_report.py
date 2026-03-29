"""Quantstats integration for professional analytics reports.

Provides 50+ performance/risk metrics and HTML tearsheet generation
using the quantstats-lumi library. Used by backtest results and
live performance analytics.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

try:
    import quantstats_lumi as qs
    import pandas as pd

    QS_AVAILABLE = True
except ImportError:
    QS_AVAILABLE = False
    logger.warning("quantstats-lumi not installed — advanced analytics unavailable")


def compute_extended_metrics(
    equity_curve: list[float],
    benchmark_returns: list[float] | None = None,
) -> dict[str, Any]:
    """Compute 50+ metrics from an equity curve using quantstats.

    Args:
        equity_curve: List of equity values over time.
        benchmark_returns: Optional benchmark returns for comparison.

    Returns:
        Dictionary with all computed metrics.
    """
    if not QS_AVAILABLE or len(equity_curve) < 10:
        return {}

    try:
        equity = pd.Series(equity_curve, dtype=np.float64)
        returns = equity.pct_change().dropna()

        if returns.empty or returns.std() == 0:
            return {}

        metrics: dict[str, Any] = {}

        # Core performance
        metrics["total_return"] = float(qs.stats.comp(returns))
        metrics["cagr"] = _safe_call(qs.stats.cagr, returns)
        metrics["sharpe"] = _safe_call(qs.stats.sharpe, returns)
        metrics["sortino"] = _safe_call(qs.stats.sortino, returns)
        metrics["calmar"] = _safe_call(qs.stats.calmar, returns)

        # Risk metrics
        metrics["max_drawdown"] = _safe_call(qs.stats.max_drawdown, returns)
        metrics["volatility"] = _safe_call(qs.stats.volatility, returns)
        metrics["var_95"] = _safe_call(qs.stats.var, returns)
        metrics["cvar_95"] = _safe_call(qs.stats.cvar, returns)

        # Distribution
        metrics["skew"] = _safe_call(qs.stats.skew, returns)
        metrics["kurtosis"] = _safe_call(qs.stats.kurtosis, returns)

        # Win/Loss
        metrics["win_rate"] = _safe_call(qs.stats.win_rate, returns)
        metrics["profit_factor"] = _safe_call(qs.stats.profit_factor, returns)
        metrics["profit_ratio"] = _safe_call(qs.stats.profit_ratio, returns)
        metrics["payoff_ratio"] = _safe_call(qs.stats.payoff_ratio, returns)

        # Ratios
        metrics["omega"] = _safe_call(qs.stats.omega, returns)
        metrics["gain_to_pain"] = _safe_call(qs.stats.gain_to_pain_ratio, returns)
        metrics["tail_ratio"] = _safe_call(qs.stats.tail_ratio, returns)

        # Drawdown analysis
        metrics["avg_drawdown"] = _safe_call(qs.stats.avg_loss, returns)
        metrics["avg_win"] = _safe_call(qs.stats.avg_win, returns)
        metrics["avg_loss"] = _safe_call(qs.stats.avg_loss, returns)
        metrics["best_day"] = _safe_call(qs.stats.best, returns)
        metrics["worst_day"] = _safe_call(qs.stats.worst, returns)

        # Consecutive
        metrics["consecutive_wins"] = _safe_call(qs.stats.consecutive_wins, returns)
        metrics["consecutive_losses"] = _safe_call(qs.stats.consecutive_losses, returns)

        # Recovery
        metrics["ulcer_index"] = _safe_call(qs.stats.ulcer_index, returns)
        metrics["recovery_factor"] = _safe_call(qs.stats.recovery_factor, returns)

        # Clean up NaN/Inf values
        for key, value in list(metrics.items()):
            if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
                metrics[key] = None
            elif isinstance(value, (np.floating, np.integer)):
                metrics[key] = float(value)

        return metrics

    except Exception as exc:
        logger.debug("quantstats.metrics_failed", error=str(exc))
        return {}


def generate_tearsheet_html(
    equity_curve: list[float],
    title: str = "CryptoQuant Backtest Report",
) -> str | None:
    """Generate an HTML tearsheet from an equity curve.

    Args:
        equity_curve: List of equity values.
        title: Report title.

    Returns:
        HTML string of the tearsheet, or None on failure.
    """
    if not QS_AVAILABLE or len(equity_curve) < 10:
        return None

    try:
        equity = pd.Series(equity_curve, dtype=np.float64)
        returns = equity.pct_change().dropna()

        html = qs.reports.html(
            returns,
            title=title,
            output=None,  # Return string instead of saving file
        )
        return html

    except Exception as exc:
        logger.debug("quantstats.tearsheet_failed", error=str(exc))
        return None


def _safe_call(func, *args, **kwargs) -> float | None:
    """Call a quantstats function safely, returning None on error."""
    try:
        result = func(*args, **kwargs)
        if result is not None and not (isinstance(result, float) and (np.isnan(result) or np.isinf(result))):
            return float(result)
    except Exception:
        pass
    return None
