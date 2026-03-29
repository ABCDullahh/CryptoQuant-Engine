"""Signal endpoints — list, detail, history, execute."""

from __future__ import annotations

import structlog

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_current_user, get_db
from app.api.schemas import PaginatedResponse
from app.config.constants import (
    DEFAULT_LEVERAGE,
    ENTRY_ZONE_PCT,
    MAX_RISK_PER_TRADE,
    Direction,
    SignalGrade,
    SignalStatus,
    StopLossType,
    TP1_CLOSE_PCT,
    TP1_RR_RATIO,
    TP2_CLOSE_PCT,
    TP2_RR_RATIO,
    TP3_CLOSE_PCT,
    TP3_RR_RATIO,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_signals(
    symbol: str | None = Query(default=None, description="Filter by symbol"),
    grade: str | None = Query(default=None, description="Filter by grade (A,B,C,D)"),
    direction: str | None = Query(default=None, description="Filter by direction"),
    status: str | None = Query(default=None, description="Filter by status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """List active signals with optional filters."""
    from sqlalchemy import select
    from app.db.models import SignalModel

    query = select(SignalModel).order_by(SignalModel.created_at.desc())

    if symbol:
        query = query.where(SignalModel.symbol == symbol)
    if grade:
        query = query.where(SignalModel.signal_grade == grade)
    if direction:
        query = query.where(SignalModel.direction == direction)
    if status and status != "ALL":
        query = query.where(SignalModel.status == status)

    # Count total
    from sqlalchemy import func
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.scalars().all()

    items = [_signal_to_dict(row) for row in rows]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/history", response_model=PaginatedResponse)
async def signal_history(
    symbol: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Signal history with outcomes."""
    from sqlalchemy import select, func
    from app.db.models import SignalModel

    query = select(SignalModel).where(
        SignalModel.status.in_([SignalStatus.EXECUTED, SignalStatus.EXPIRED, SignalStatus.REJECTED])
    ).order_by(SignalModel.created_at.desc())

    if symbol:
        query = query.where(SignalModel.symbol == symbol)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.scalars().all()

    items = [_signal_to_dict(row) for row in rows]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{signal_id}")
async def get_signal(
    signal_id: str,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Get signal details by ID."""
    from sqlalchemy import select
    from app.db.models import SignalModel

    result = await db.execute(
        select(SignalModel).where(SignalModel.id == signal_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    return _signal_to_dict(row)


@router.post("/{signal_id}/execute")
async def execute_signal(
    signal_id: str,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Execute a signal — place order on exchange (paper or live)."""
    from sqlalchemy import select
    from app.db.models import SignalModel
    from app.bot.service import bot_service
    from app.core.models import (
        CompositeSignal,
        TakeProfit,
        RiskReward,
        PositionSize,
        MarketContext,
    )
    from uuid import UUID

    # Fetch signal from DB
    result = await db.execute(select(SignalModel).where(SignalModel.id == signal_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    if row.status != SignalStatus.ACTIVE:
        raise HTTPException(status_code=400, detail=f"Signal status is {row.status}, must be ACTIVE")

    # Build CompositeSignal from DB row — use constants.py defaults (not magic numbers)
    entry_price = float(row.entry_price)
    stop_loss = float(row.stop_loss)
    take_profits = []
    if row.tp1_price:
        take_profits.append(TakeProfit(level="TP1", price=float(row.tp1_price), close_pct=row.tp1_pct or TP1_CLOSE_PCT, rr_ratio=float(row.rr_tp1 or TP1_RR_RATIO)))
    if row.tp2_price:
        take_profits.append(TakeProfit(level="TP2", price=float(row.tp2_price), close_pct=row.tp2_pct or TP2_CLOSE_PCT, rr_ratio=float(row.rr_tp2 or TP2_RR_RATIO)))
    if row.tp3_price:
        take_profits.append(TakeProfit(level="TP3", price=float(row.tp3_price), close_pct=row.tp3_pct or TP3_CLOSE_PCT, rr_ratio=float(row.rr_tp3 or TP3_RR_RATIO)))

    qty = float(row.position_size_qty or 0.001)
    leverage = row.leverage if row.leverage and row.leverage > 0 else DEFAULT_LEVERAGE

    signal = CompositeSignal(
        id=UUID(row.id),
        symbol=row.symbol,
        direction=Direction(row.direction),
        grade=SignalGrade(row.signal_grade),
        strength=float(row.signal_strength),
        entry_price=entry_price,
        entry_zone=(entry_price * (1 - ENTRY_ZONE_PCT), entry_price * (1 + ENTRY_ZONE_PCT)),
        stop_loss=stop_loss,
        sl_type=StopLossType(row.sl_type) if row.sl_type else StopLossType.ATR_BASED,
        take_profits=take_profits,
        risk_reward=RiskReward(
            rr_tp1=float(row.rr_tp1 or TP1_RR_RATIO),
            rr_tp2=float(row.rr_tp2) if row.rr_tp2 else None,
            rr_tp3=float(row.rr_tp3) if row.rr_tp3 else None,
            weighted_rr=float(row.weighted_rr or TP1_RR_RATIO * 1.33),
        ),
        position_size=PositionSize(
            quantity=qty,
            notional=qty * entry_price,
            margin=qty * entry_price / max(leverage, 1),
            risk_amount=abs(entry_price - stop_loss) * qty,
            risk_pct=MAX_RISK_PER_TRADE,
            leverage=leverage,
        ),
        strategy_scores=row.strategy_scores or {},
        market_context=MarketContext(**(row.market_context or {})),
        ml_confidence=float(row.ml_confidence) if row.ml_confidence else None,
    )

    # Get executor from bot service if running, otherwise reject
    executor = bot_service.executor
    if executor is None:
        raise HTTPException(status_code=400, detail="Bot is not running. Start the bot first to execute signals.")

    # Execute
    exec_result = await executor.execute_signal_and_publish(
        signal, current_price=entry_price, use_market=True,
    )

    # Update signal status in DB
    row.status = SignalStatus.EXECUTED if exec_result.success else SignalStatus.REJECTED
    if exec_result.success and exec_result.position:
        row.outcome = "OPEN"
    await db.commit()

    return {
        "success": exec_result.success,
        "message": exec_result.message,
        "position_id": str(exec_result.position.id) if exec_result.success and exec_result.position else None,
    }


def _signal_to_dict(row) -> dict:
    """Convert a SignalModel row to API response dict."""
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "symbol": row.symbol,
        "direction": row.direction,
        "signal_grade": row.signal_grade,
        "signal_strength": float(row.signal_strength) if row.signal_strength else None,
        "entry_price": float(row.entry_price) if row.entry_price else None,
        "stop_loss": float(row.stop_loss) if row.stop_loss else None,
        "sl_type": row.sl_type,
        "tp1_price": float(row.tp1_price) if row.tp1_price else None,
        "tp2_price": float(row.tp2_price) if row.tp2_price else None,
        "tp3_price": float(row.tp3_price) if row.tp3_price else None,
        "leverage": row.leverage,
        "strategy_scores": row.strategy_scores,
        "market_context": row.market_context,
        "ml_confidence": float(row.ml_confidence) if row.ml_confidence else None,
        "status": row.status,
        "outcome": row.outcome,
    }
