"""Performance metrics calculator for backtesting results.

Pure numpy calculations — no external dependencies beyond numpy.
Computes: Sharpe, Sortino, Calmar, Max Drawdown, Win Rate, Profit Factor,
Expectancy, Recovery Factor, Ulcer Index, and more.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


TRADING_DAYS_PER_YEAR = 365  # Crypto trades 24/7
RISK_FREE_RATE = 0.0  # Default risk-free rate for crypto


@dataclass
class PerformanceMetrics:
    """Complete performance metrics for a backtest run."""

    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # In periods
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_holding_periods: float = 0.0
    recovery_factor: float = 0.0
    ulcer_index: float = 0.0
    tail_ratio: float = 0.0
    common_sense_ratio: float = 0.0
    # Equity curve stats
    peak_equity: float = 0.0
    final_equity: float = 0.0
    # Monthly data
    monthly_returns: dict = field(default_factory=dict)


def calc_total_return(equity_curve: np.ndarray) -> float:
    """Calculate total return percentage."""
    if len(equity_curve) < 2 or equity_curve[0] == 0:
        return 0.0
    return (equity_curve[-1] - equity_curve[0]) / equity_curve[0]


def calc_annual_return(total_return: float, n_periods: int, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """Annualize return based on number of periods."""
    if n_periods <= 0:
        return 0.0
    years = n_periods / periods_per_year
    if years <= 0:
        return 0.0
    if total_return <= -1.0:
        return -1.0
    return (1 + total_return) ** (1 / years) - 1


def calc_drawdown_series(equity_curve: np.ndarray) -> np.ndarray:
    """Calculate drawdown series from equity curve.

    Returns array of drawdown percentages (negative values).
    """
    if len(equity_curve) < 2:
        return np.zeros(len(equity_curve))
    running_max = np.maximum.accumulate(equity_curve)
    drawdowns = np.where(running_max > 0, (equity_curve - running_max) / running_max, 0.0)
    return drawdowns


def calc_max_drawdown(equity_curve: np.ndarray) -> float:
    """Calculate maximum drawdown (as positive fraction, e.g. 0.15 = 15%)."""
    if len(equity_curve) < 2:
        return 0.0
    dd = calc_drawdown_series(equity_curve)
    return abs(float(np.min(dd)))


def calc_max_drawdown_duration(equity_curve: np.ndarray) -> int:
    """Calculate the longest drawdown duration in periods."""
    if len(equity_curve) < 2:
        return 0
    running_max = np.maximum.accumulate(equity_curve)
    in_drawdown = equity_curve < running_max
    max_duration = 0
    current_duration = 0
    for is_dd in in_drawdown:
        if is_dd:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
        else:
            current_duration = 0
    return max_duration


def calc_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = RISK_FREE_RATE,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Calculate annualized Sharpe ratio."""
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free_rate / periods_per_year
    std = float(np.std(excess, ddof=1))
    if std < 1e-12:
        return 0.0
    mean_excess = float(np.mean(excess))
    return (mean_excess / std) * np.sqrt(periods_per_year)


def calc_sortino_ratio(
    returns: np.ndarray,
    risk_free_rate: float = RISK_FREE_RATE,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Calculate annualized Sortino ratio (downside deviation only)."""
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free_rate / periods_per_year
    downside = np.minimum(excess, 0)
    downside_std = float(np.sqrt(np.mean(downside**2)))
    if downside_std == 0:
        return 0.0
    mean_excess = float(np.mean(excess))
    return (mean_excess / downside_std) * np.sqrt(periods_per_year)


def calc_calmar_ratio(annual_return: float, max_drawdown: float) -> float:
    """Calculate Calmar ratio (annualized return / max drawdown)."""
    if max_drawdown == 0:
        return 0.0
    return annual_return / max_drawdown


def calc_win_rate(pnls: np.ndarray) -> float:
    """Calculate win rate from array of trade P&Ls."""
    if len(pnls) == 0:
        return 0.0
    wins = np.sum(pnls > 0)
    return float(wins / len(pnls))


def calc_profit_factor(pnls: np.ndarray) -> float:
    """Calculate profit factor (gross profit / gross loss)."""
    if len(pnls) == 0:
        return 0.0
    gross_profit = float(np.sum(pnls[pnls > 0]))
    gross_loss = float(np.abs(np.sum(pnls[pnls < 0])))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def calc_expectancy(pnls: np.ndarray) -> float:
    """Calculate average P&L per trade (expectancy)."""
    if len(pnls) == 0:
        return 0.0
    return float(np.mean(pnls))


def calc_recovery_factor(total_return_abs: float, max_drawdown_abs: float) -> float:
    """Calculate recovery factor (net profit / max drawdown in absolute terms)."""
    if max_drawdown_abs == 0:
        return 0.0
    return total_return_abs / max_drawdown_abs


def calc_ulcer_index(equity_curve: np.ndarray) -> float:
    """Calculate Ulcer Index — measures depth and duration of drawdowns.

    Lower is better. Considers squared drawdowns for severity weighting.
    """
    if len(equity_curve) < 2:
        return 0.0
    dd = calc_drawdown_series(equity_curve)
    dd_pct = dd * 100  # Convert to percentage
    return float(np.sqrt(np.mean(dd_pct**2)))


def calc_tail_ratio(returns: np.ndarray) -> float:
    """Calculate tail ratio (95th percentile / abs(5th percentile)).

    Values > 1.0 indicate fatter right tail (more large gains than losses).
    """
    if len(returns) < 20:
        return 0.0
    p95 = float(np.percentile(returns, 95))
    p5 = abs(float(np.percentile(returns, 5)))
    if p5 == 0:
        return 0.0
    return p95 / p5


def calc_common_sense_ratio(profit_factor: float, tail_ratio: float) -> float:
    """Common Sense Ratio = Profit Factor * Tail Ratio."""
    return profit_factor * tail_ratio


def calc_monthly_returns(
    equity_curve: np.ndarray, dates: list | np.ndarray,
) -> dict[str, float]:
    """Calculate monthly returns from equity curve and date array.

    Args:
        equity_curve: Array of equity values.
        dates: Array of date strings "YYYY-MM-DD" or datetime objects.

    Returns:
        Dict mapping "YYYY-MM" to monthly return percentage.
    """
    if len(equity_curve) < 2 or len(dates) != len(equity_curve):
        return {}

    monthly: dict[str, float] = {}
    prev_month = None
    month_start_equity = equity_curve[0]

    for i, date in enumerate(dates):
        date_str = str(date)[:7]  # "YYYY-MM"
        if date_str != prev_month:
            if prev_month is not None and month_start_equity > 0:
                monthly[prev_month] = (equity_curve[i - 1] - month_start_equity) / month_start_equity
            month_start_equity = equity_curve[i - 1] if i > 0 else equity_curve[0]
            prev_month = date_str

    # Last month
    if prev_month is not None and month_start_equity > 0:
        monthly[prev_month] = (equity_curve[-1] - month_start_equity) / month_start_equity

    return monthly


def calc_returns_from_equity(equity_curve: np.ndarray) -> np.ndarray:
    """Calculate period returns from equity curve."""
    if len(equity_curve) < 2:
        return np.array([])
    shifted = equity_curve[:-1]
    mask = shifted != 0
    returns = np.zeros(len(equity_curve) - 1)
    returns[mask] = (equity_curve[1:][mask] - shifted[mask]) / shifted[mask]
    return returns


def compute_all_metrics(
    equity_curve: np.ndarray,
    trade_pnls: np.ndarray,
    trade_durations: np.ndarray | None = None,
    dates: list | None = None,
    initial_capital: float = 10000.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> PerformanceMetrics:
    """Compute all performance metrics from equity curve and trades.

    Args:
        equity_curve: Array of equity values over time.
        trade_pnls: Array of P&L for each closed trade.
        trade_durations: Array of holding durations per trade (in periods).
        dates: List of date strings for monthly return calculation.
        initial_capital: Starting capital.
        periods_per_year: Trading periods per year (365 for crypto).

    Returns:
        PerformanceMetrics dataclass with all computed values.
    """
    equity_curve = np.asarray(equity_curve, dtype=np.float64)
    trade_pnls = np.asarray(trade_pnls, dtype=np.float64)

    total_ret = calc_total_return(equity_curve)
    n_periods = len(equity_curve) - 1 if len(equity_curve) > 1 else 0
    annual_ret = calc_annual_return(total_ret, n_periods, periods_per_year)
    max_dd = calc_max_drawdown(equity_curve)
    max_dd_dur = calc_max_drawdown_duration(equity_curve)

    returns = calc_returns_from_equity(equity_curve)
    sharpe = calc_sharpe_ratio(returns, periods_per_year=periods_per_year)
    sortino = calc_sortino_ratio(returns, periods_per_year=periods_per_year)
    calmar = calc_calmar_ratio(annual_ret, max_dd)

    win_rate = calc_win_rate(trade_pnls)
    pf = calc_profit_factor(trade_pnls)
    expect = calc_expectancy(trade_pnls)
    ulcer = calc_ulcer_index(equity_curve)
    tail = calc_tail_ratio(returns)
    csr = calc_common_sense_ratio(pf, tail)

    wins = trade_pnls[trade_pnls > 0]
    losses = trade_pnls[trade_pnls < 0]
    avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
    avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0

    total_profit_abs = float(equity_curve[-1] - equity_curve[0]) if len(equity_curve) > 1 else 0.0
    max_dd_abs = max_dd * (float(np.max(equity_curve)) if len(equity_curve) > 0 else 0.0)
    recovery = calc_recovery_factor(total_profit_abs, max_dd_abs)

    avg_hold = 0.0
    if trade_durations is not None and len(trade_durations) > 0:
        avg_hold = float(np.mean(trade_durations))

    monthly = {}
    if dates is not None:
        monthly = calc_monthly_returns(equity_curve, dates)

    return PerformanceMetrics(
        total_return=total_ret,
        annual_return=annual_ret,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        max_drawdown=max_dd,
        max_drawdown_duration=max_dd_dur,
        win_rate=win_rate,
        profit_factor=pf,
        expectancy=expect,
        avg_win=avg_win,
        avg_loss=avg_loss,
        total_trades=len(trade_pnls),
        winning_trades=int(len(wins)),
        losing_trades=int(len(losses)),
        avg_holding_periods=avg_hold,
        recovery_factor=recovery,
        ulcer_index=ulcer,
        tail_ratio=tail,
        common_sense_ratio=csr,
        peak_equity=float(np.max(equity_curve)) if len(equity_curve) > 0 else initial_capital,
        final_equity=float(equity_curve[-1]) if len(equity_curve) > 0 else initial_capital,
        monthly_returns=monthly,
    )
