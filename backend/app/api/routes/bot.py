"""Auto-Bot management endpoints."""

from __future__ import annotations

import structlog
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user, get_db
from app.api.schemas import BotPaperModeUpdate, BotStartRequest, BotStrategyUpdate
from app.bot.service import bot_service
from app.config.constants import BotStatus

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _get_bot_state(db):
    """Get or create bot state record."""
    from sqlalchemy import select
    from app.db.models import BotStateModel

    result = await db.execute(select(BotStateModel).limit(1))
    state = result.scalar_one_or_none()
    if state is None:
        state = BotStateModel(
            is_running=False,
            is_paper_mode=True,
            active_strategies=[],
            total_pnl=0,
            metadata_json={},
        )
        db.add(state)
        await db.flush()
    return state


def _get_bot_status_string(state) -> str:
    """Derive bot status string from state fields."""
    if state.is_running:
        return BotStatus.RUNNING
    meta = state.metadata_json or {}
    if meta.get("is_paused"):
        return BotStatus.PAUSED
    return BotStatus.STOPPED


@router.get("/status")
async def get_bot_status(
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Get bot status including trading balance."""
    state = await _get_bot_state(db)

    # Get live balance from bot service if running
    current_balance = bot_service.get_current_balance()
    paper_equity = None
    if bot_service.executor and bot_service.executor.paper_equity is not None:
        paper_equity = bot_service.executor.paper_equity

    return {
        "status": _get_bot_status_string(state),
        "paper_mode": state.is_paper_mode,
        "active_strategies": state.active_strategies or [],
        "started_at": state.started_at.isoformat() if state.started_at else None,
        "total_pnl": float(state.total_pnl) if state.total_pnl else 0,
        "current_balance": current_balance,
        "current_equity": paper_equity if state.is_paper_mode else current_balance,
        "paper_initial_balance": float(state.paper_initial_balance) if state.paper_initial_balance else None,
        "paper_saved_balance": float(state.paper_balance) if state.paper_balance else None,
    }


@router.post("/start")
async def start_bot(
    config: BotStartRequest | None = None,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Start the trading bot with optional configuration."""
    state = await _get_bot_state(db)
    if state.is_running:
        raise HTTPException(status_code=409, detail="Bot is already running")

    # Apply config if provided
    if config:
        state.is_paper_mode = config.is_paper
        if config.strategies:
            state.active_strategies = config.strategies

    state.is_running = True
    state.started_at = datetime.now(tz=UTC)
    state.stopped_at = None
    meta = dict(state.metadata_json or {})
    meta.pop("is_paused", None)
    state.metadata_json = meta
    await db.commit()

    # Start the actual bot service pipeline
    try:
        bot_service.configure(
            symbols=config.symbols if config else None,
            timeframes=config.timeframes if config else None,
            strategies=config.strategies if config and config.strategies else state.active_strategies or None,
            balance=config.initial_balance if config else None,
            is_paper=state.is_paper_mode,
        )
        await bot_service.start()
    except Exception as exc:
        # Rollback DB state on service failure
        state.is_running = False
        state.stopped_at = state.started_at
        await db.commit()
        logger.error("bot.start_service_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Bot service failed to start")

    return {"status": BotStatus.RUNNING, "started_at": state.started_at.isoformat()}


@router.post("/pause")
async def pause_bot(
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Pause the bot (keeps monitoring positions)."""
    state = await _get_bot_state(db)
    if not state.is_running:
        raise HTTPException(status_code=409, detail="Bot is not running")

    state.is_running = False
    meta = dict(state.metadata_json or {})
    meta["is_paused"] = True
    state.metadata_json = meta
    await db.commit()

    # Pause the actual bot service
    try:
        await bot_service.pause()
    except Exception as exc:
        # Rollback DB state on failure
        state.is_running = True
        meta.pop("is_paused", None)
        state.metadata_json = meta
        await db.commit()
        logger.error("bot.pause_service_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Bot pause failed")

    return {"status": BotStatus.PAUSED}


@router.post("/stop")
async def stop_bot(
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Stop the bot completely."""
    state = await _get_bot_state(db)
    state.is_running = False
    state.stopped_at = datetime.now(tz=UTC)
    meta = dict(state.metadata_json or {})
    meta.pop("is_paused", None)
    state.metadata_json = meta
    await db.commit()

    # Stop the actual bot service
    try:
        await bot_service.stop()
    except Exception as exc:
        logger.error("bot.stop_service_failed", error=str(exc))
        # Still return stopped - stopping should be best-effort

    return {"status": BotStatus.STOPPED, "stopped_at": state.stopped_at.isoformat()}


@router.put("/paper-mode")
async def toggle_paper_mode(
    request: BotPaperModeUpdate,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Toggle paper trading mode.

    When switching FROM paper mode, saves current paper balance for resumption.
    """
    state = await _get_bot_state(db)
    if state.is_running:
        raise HTTPException(status_code=409, detail="Cannot change mode while bot is running")

    old_mode = state.is_paper_mode
    state.is_paper_mode = request.paper_mode

    # If switching away from paper, preserve paper balance for later resume
    if old_mode and not request.paper_mode:
        logger.info("bot.mode_switch_paper_to_live", saved_balance=state.paper_balance)

    await db.commit()

    return {
        "paper_mode": state.is_paper_mode,
        "paper_saved_balance": float(state.paper_balance) if state.paper_balance else None,
    }


@router.put("/strategies")
async def update_strategies(
    request: BotStrategyUpdate,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Enable/disable specific strategies."""
    state = await _get_bot_state(db)
    active = [name for name, enabled in request.strategies.items() if enabled]
    state.active_strategies = active
    await db.commit()

    return {"active_strategies": active}


@router.get("/live-status")
async def get_live_status(
    user: str = Depends(get_current_user),
):
    """Get real-time bot service status (in-memory, not DB)."""
    return {
        "service_status": bot_service.status,
        "has_collector": bot_service.collector is not None,
        "has_executor": bot_service.executor is not None,
    }


@router.get("/performance")
async def get_performance(
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Get bot performance metrics."""
    from sqlalchemy import select, func
    from app.db.models import PositionModel
    from app.config.constants import PositionStatus

    # Count trades
    total_result = await db.execute(
        select(func.count()).select_from(PositionModel).where(
            PositionModel.status == PositionStatus.CLOSED
        )
    )
    total_trades = total_result.scalar() or 0

    # Sum realized PnL
    pnl_result = await db.execute(
        select(func.sum(PositionModel.realized_pnl)).where(
            PositionModel.status == PositionStatus.CLOSED
        )
    )
    total_pnl = float(pnl_result.scalar() or 0)

    # Win count
    win_result = await db.execute(
        select(func.count()).select_from(PositionModel).where(
            PositionModel.status == PositionStatus.CLOSED,
            PositionModel.realized_pnl > 0,
        )
    )
    wins = win_result.scalar() or 0

    win_rate = wins / total_trades if total_trades > 0 else 0

    return {
        "total_trades": total_trades,
        "total_pnl": total_pnl,
        "win_rate": round(win_rate, 4),
        "wins": wins,
        "losses": total_trades - wins,
    }
