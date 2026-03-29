"""Backtest endpoints — run, status, history, optimize, walk-forward, verify."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_current_user, get_db
from app.api.schemas import (
    BacktestJobResponse,
    BacktestRunRequest,
    OptimizeRequest,
    PaginatedResponse,
    WalkForwardRequest,
)
from app.backtesting.job_runner import job_runner

router = APIRouter()


@router.post("/run", response_model=BacktestJobResponse, status_code=202)
async def run_backtest(
    request: BacktestRunRequest,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Run a backtest (async, returns job_id)."""
    from app.db.models import BacktestRunModel

    job_id = str(uuid4())

    # Persist backtest run record
    run = BacktestRunModel(
        id=job_id,
        strategy_name=request.strategy_name,
        symbol=request.symbol,
        timeframe=request.timeframe,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        parameters=request.parameters,
        status="QUEUED",
    )
    db.add(run)
    await db.commit()

    # Register and launch job
    job_runner.register_job(job_id, "backtest")

    # Get DB session factory for background task
    from app.db.session import get_session_factory
    db_factory = get_session_factory()

    asyncio.create_task(job_runner.run_backtest(job_id, request, db_factory))

    return BacktestJobResponse(job_id=job_id, status="QUEUED", progress=0)


@router.get("/history", response_model=PaginatedResponse)
async def backtest_history(
    strategy: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """List all past backtests."""
    from sqlalchemy import select, func
    from app.db.models import BacktestRunModel

    query = select(BacktestRunModel).order_by(BacktestRunModel.created_at.desc())
    if strategy:
        query = query.where(BacktestRunModel.strategy_name == strategy)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.scalars().all()

    items = [_backtest_to_dict(row) for row in rows]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/optimize", status_code=202)
async def run_optimization(
    request: OptimizeRequest,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Run parameter optimization."""
    job_id = str(uuid4())
    job_runner.register_job(job_id, "optimization")

    from app.db.session import get_session_factory
    db_factory = get_session_factory()

    asyncio.create_task(job_runner.run_optimization(job_id, request, db_factory))

    return BacktestJobResponse(job_id=job_id, status="QUEUED", progress=0)


@router.post("/walkforward", status_code=202)
async def run_walk_forward(
    request: WalkForwardRequest,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Run walk-forward analysis."""
    job_id = str(uuid4())
    job_runner.register_job(job_id, "walk_forward")

    from app.db.session import get_session_factory
    db_factory = get_session_factory()

    asyncio.create_task(job_runner.run_walk_forward(job_id, request, db_factory))

    return BacktestJobResponse(job_id=job_id, status="QUEUED", progress=0)


# --- Static path routes MUST be registered before /{job_id} catch-all ---


@router.get("/verify/{job_id}")
async def verify_backtest(
    job_id: str,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Verify backtest integrity -- cross-checks trade P&Ls, quantities, and SL levels."""
    from sqlalchemy import select
    from app.db.models import BacktestRunModel

    result = await db.execute(
        select(BacktestRunModel).where(BacktestRunModel.id == job_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Backtest not found")

    equity_curve = row.equity_curve or []
    trade_list = row.trades or []
    initial_capital = float(row.initial_capital) if row.initial_capital else 10000.0

    checks = []

    # Check 1: P&L cross-validation (trade sum vs equity delta)
    trade_pnl_sum = sum(t.get("pnl", 0) for t in trade_list)
    final_eq = 0.0
    if equity_curve:
        last_point = equity_curve[-1]
        final_eq = last_point.get("equity", 0) if isinstance(last_point, dict) else float(last_point)
    expected_delta = final_eq - initial_capital if final_eq else 0.0
    diff = abs(trade_pnl_sum - expected_delta)
    checks.append({
        "name": "pnl_cross_validation",
        "passed": diff < 1.0,
        "detail": {
            "trade_pnl_sum": round(trade_pnl_sum, 2),
            "equity_delta": round(expected_delta, 2),
            "difference": round(diff, 2),
            "tolerance": 1.0,
        },
    })

    # Check 2: No negative quantities in trades
    negative_qty_trades = [
        t.get("id", "unknown")
        for t in trade_list
        if t.get("quantity", 0) < 0
    ]
    checks.append({
        "name": "no_negative_quantities",
        "passed": len(negative_qty_trades) == 0,
        "detail": {
            "total_trades": len(trade_list),
            "negative_qty_trades": negative_qty_trades,
        },
    })

    # Check 3: SL placement -- SL below entry for LONG, above entry for SHORT
    sl_violations = []
    for t in trade_list:
        sl = t.get("stop_loss")
        entry = t.get("entry_price", 0)
        direction = (t.get("direction") or "").upper()
        if sl is not None and entry:
            if "LONG" in direction and sl >= entry:
                sl_violations.append({
                    "trade_id": t.get("id", "unknown"),
                    "direction": direction,
                    "entry_price": entry,
                    "stop_loss": sl,
                })
            elif "SHORT" in direction and sl <= entry:
                sl_violations.append({
                    "trade_id": t.get("id", "unknown"),
                    "direction": direction,
                    "entry_price": entry,
                    "stop_loss": sl,
                })
    checks.append({
        "name": "sl_placement_valid",
        "passed": len(sl_violations) == 0,
        "detail": {
            "total_with_sl": sum(1 for t in trade_list if t.get("stop_loss") is not None),
            "violations": sl_violations,
        },
    })

    all_passed = all(c["passed"] for c in checks)
    return {
        "backtest_id": job_id,
        "overall": "PASS" if all_passed else "FAIL",
        "checks": checks,
    }


# --- Dynamic path routes (catch-all patterns) ---


@router.get("/{job_id}")
async def get_backtest(
    job_id: str,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Get backtest status and results."""
    from sqlalchemy import select
    from app.db.models import BacktestRunModel

    result = await db.execute(
        select(BacktestRunModel).where(BacktestRunModel.id == job_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Backtest not found")

    data = _backtest_to_dict(row)

    # Overlay in-memory job status (more current than DB for running jobs)
    job = job_runner.get_job_status(job_id)
    if job:
        data["status"] = job.get("status", data.get("status", "COMPLETED"))
        data["progress"] = job.get("progress", 100)
        if job.get("error"):
            data["error_message"] = job["error"]
        # For optimization/walkforward, include result data
        if job.get("result"):
            data["optimization_result"] = job["result"]
    else:
        # Job not in memory -> already completed and cleaned up, use DB status
        data["status"] = getattr(row, "status", None) or "COMPLETED"
        data["progress"] = 100

    return data


@router.get("/{job_id}/analytics")
async def get_backtest_analytics(
    job_id: str,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Get extended analytics (50+ metrics) for a backtest using quantstats."""
    from sqlalchemy import select
    from app.db.models import BacktestRunModel
    from app.backtesting.quantstats_report import compute_extended_metrics

    result = await db.execute(
        select(BacktestRunModel).where(BacktestRunModel.id == job_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Backtest not found")

    equity_curve = row.equity_curve or []
    if not equity_curve:
        return {"metrics": {}, "message": "No equity curve data available"}

    # Extract equity values from curve points
    equity_values = [p["equity"] if isinstance(p, dict) else p for p in equity_curve]

    metrics = compute_extended_metrics(equity_values)
    return {
        "backtest_id": job_id,
        "metrics": metrics,
        "metric_count": len([v for v in metrics.values() if v is not None]),
    }


def _backtest_to_dict(row) -> dict:
    """Convert BacktestRunModel to API response dict.

    Includes full equity curve, trade list, metrics summary, monthly returns,
    and a verification cross-check of trade P&Ls vs equity delta.
    """
    equity_curve = row.equity_curve or []
    trade_list = row.trades or []
    config = row.parameters or {}
    initial_capital = float(row.initial_capital) if row.initial_capital else 10000.0

    # Build metrics dict from stored column values
    metrics = {
        "total_return": float(row.total_return) if row.total_return else None,
        "sharpe_ratio": float(row.sharpe_ratio) if row.sharpe_ratio else None,
        "sortino_ratio": float(row.sortino_ratio) if row.sortino_ratio else None,
        "max_drawdown": float(row.max_drawdown) if row.max_drawdown else None,
        "win_rate": float(row.win_rate) if row.win_rate else None,
        "profit_factor": float(row.profit_factor) if row.profit_factor else None,
        "total_trades": row.total_trades,
        "final_capital": float(row.final_capital) if row.final_capital else None,
        "annual_return": float(row.annual_return) if row.annual_return else None,
        "expectancy": float(row.expectancy) if row.expectancy else None,
        "avg_win": float(row.avg_win) if row.avg_win else None,
        "avg_loss": float(row.avg_loss) if row.avg_loss else None,
        "calmar_ratio": float(row.calmar_ratio) if row.calmar_ratio else None,
        "avg_holding_period": float(row.avg_holding_period) if row.avg_holding_period else None,
    }

    # Extract monthly returns from trade list metadata if available
    monthly_returns = {}
    if trade_list:
        # Aggregate monthly P&L from trades (by exit date if available)
        for t in trade_list:
            exit_date = t.get("exit_date") or t.get("date")
            if exit_date and isinstance(exit_date, str) and len(exit_date) >= 7:
                month_key = exit_date[:7]  # "YYYY-MM"
                monthly_returns[month_key] = monthly_returns.get(month_key, 0) + t.get("pnl", 0)

    # Verification: cross-check trade P&Ls vs equity delta
    trade_pnl_sum = sum(t.get("pnl", 0) for t in trade_list)
    final_eq = 0.0
    if equity_curve:
        last_point = equity_curve[-1]
        final_eq = last_point.get("equity", 0) if isinstance(last_point, dict) else float(last_point)
    expected_delta = final_eq - initial_capital if final_eq else 0.0
    diff = abs(trade_pnl_sum - expected_delta)
    verification = {
        "valid": diff < 1.0,  # Allow $1 rounding tolerance
        "trade_pnl_sum": round(trade_pnl_sum, 2),
        "equity_delta": round(expected_delta, 2),
        "difference": round(diff, 2),
    }

    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "strategy_name": row.strategy_name,
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "initial_capital": initial_capital,
        "final_capital": float(row.final_capital) if row.final_capital else None,
        "total_return": float(row.total_return) if row.total_return else None,
        "sharpe_ratio": float(row.sharpe_ratio) if row.sharpe_ratio else None,
        "sortino_ratio": float(row.sortino_ratio) if row.sortino_ratio else None,
        "max_drawdown": float(row.max_drawdown) if row.max_drawdown else None,
        "win_rate": float(row.win_rate) if row.win_rate else None,
        "profit_factor": float(row.profit_factor) if row.profit_factor else None,
        "annual_return": float(row.annual_return) if row.annual_return else None,
        "expectancy": float(row.expectancy) if row.expectancy else None,
        "avg_holding_period": float(row.avg_holding_period) if row.avg_holding_period else None,
        "total_trades": row.total_trades,
        "parameters": row.parameters,
        "equity_curve": equity_curve,
        "trade_list": trade_list,
        "trades": row.trades,  # Keep backward compat
        "metrics": metrics,
        "monthly_returns": monthly_returns,
        "verification": verification,
        "status": getattr(row, "status", None) or "COMPLETED",
        "error_message": getattr(row, "error_message", None),
    }
