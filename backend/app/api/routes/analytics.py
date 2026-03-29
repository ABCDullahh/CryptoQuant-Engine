"""Live performance analytics — real metrics from closed positions."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user, get_db
from app.config.constants import PositionStatus

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/live-performance")
async def get_live_performance(
    days: int = Query(default=30, ge=1, le=365),
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Calculate real performance metrics from closed positions.

    Returns comprehensive analytics including equity curve, monthly returns,
    risk-adjusted ratios (Sharpe, Sortino), drawdown, and trade statistics.
    """
    from sqlalchemy import select
    from app.db.models import PositionModel

    cutoff = datetime.now(tz=UTC) - timedelta(days=days)

    result = await db.execute(
        select(PositionModel)
        .where(
            PositionModel.status == PositionStatus.CLOSED,
            PositionModel.closed_at >= cutoff,
        )
        .order_by(PositionModel.closed_at.asc())
    )
    positions = result.scalars().all()

    if not positions:
        return {
            "has_data": False,
            "message": "No closed trades in the selected period",
            "days": days,
        }

    # --- Extract trade P&Ls and metadata ---
    trade_pnls: list[float] = []
    total_fees = 0.0
    holding_hours: list[float] = []
    monthly_pnl: dict[str, float] = defaultdict(float)

    for pos in positions:
        pnl = float(pos.realized_pnl or 0)
        trade_pnls.append(pnl)
        total_fees += float(pos.total_fees or 0)

        # Holding time
        if pos.opened_at and pos.closed_at:
            delta = pos.closed_at - pos.opened_at
            holding_hours.append(delta.total_seconds() / 3600.0)

        # Monthly aggregation
        if pos.closed_at:
            month_key = pos.closed_at.strftime("%Y-%m")
            monthly_pnl[month_key] += pnl

    # --- Win/Loss stats ---
    wins = [p for p in trade_pnls if p > 0]
    losses = [p for p in trade_pnls if p <= 0]
    win_count = len(wins)
    loss_count = len(losses)
    total_trades = len(trade_pnls)
    win_rate = win_count / total_trades if total_trades > 0 else 0.0

    gross_wins = sum(wins) if wins else 0.0
    gross_losses = abs(sum(losses)) if losses else 0.0
    avg_win = gross_wins / win_count if win_count > 0 else 0.0
    avg_loss = gross_losses / loss_count if loss_count > 0 else 0.0

    # Profit factor
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else (
        float("inf") if gross_wins > 0 else 0.0
    )

    # Expectancy (mean P&L per trade)
    expectancy = sum(trade_pnls) / total_trades if total_trades > 0 else 0.0

    # --- Equity curve ---
    initial_balance = 10000.0  # Reference starting balance
    equity_curve: list[dict] = []
    running_balance = initial_balance
    for i, pos in enumerate(positions):
        pnl = trade_pnls[i]
        running_balance += pnl
        equity_curve.append({
            "date": pos.closed_at.isoformat() if pos.closed_at else None,
            "balance": round(running_balance, 2),
            "trade_pnl": round(pnl, 2),
        })

    # --- Max drawdown from equity curve ---
    peak = initial_balance
    max_dd = 0.0
    for point in equity_curve:
        bal = point["balance"]
        if bal > peak:
            peak = bal
        dd = (peak - bal) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # --- Sharpe ratio (annualized) ---
    sharpe_ratio = 0.0
    if total_trades >= 2:
        mean_ret = sum(trade_pnls) / total_trades
        variance = sum((p - mean_ret) ** 2 for p in trade_pnls) / (total_trades - 1)
        std_ret = math.sqrt(variance) if variance > 0 else 0.0
        if std_ret > 0:
            sharpe_ratio = (mean_ret / std_ret) * math.sqrt(252)

    # --- Sortino ratio (annualized, downside deviation only) ---
    sortino_ratio = 0.0
    if total_trades >= 2:
        mean_ret = sum(trade_pnls) / total_trades
        downside_sq = [p ** 2 for p in trade_pnls if p < 0]
        if downside_sq:
            downside_dev = math.sqrt(sum(downside_sq) / (total_trades - 1))
            if downside_dev > 0:
                sortino_ratio = (mean_ret / downside_dev) * math.sqrt(252)

    # --- Best / worst trade ---
    best_trade = max(trade_pnls)
    worst_trade = min(trade_pnls)

    # --- Average holding time ---
    avg_holding_hours = (
        sum(holding_hours) / len(holding_hours) if holding_hours else 0.0
    )

    # --- Monthly returns ---
    monthly_returns = [
        {"month": month, "pnl": round(pnl, 2)}
        for month, pnl in sorted(monthly_pnl.items())
    ]

    return {
        "has_data": True,
        "days": days,
        "total_trades": total_trades,
        "wins": win_count,
        "losses": loss_count,
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else None,
        "expectancy": round(expectancy, 2),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "sortino_ratio": round(sortino_ratio, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "avg_holding_hours": round(avg_holding_hours, 2),
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2),
        "total_fees": round(total_fees, 2),
        "total_pnl": round(sum(trade_pnls), 2),
        "equity_curve": equity_curve,
        "monthly_returns": monthly_returns,
        "trade_pnls": [round(p, 2) for p in trade_pnls],
    }
