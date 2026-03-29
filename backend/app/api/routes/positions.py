"""Position endpoints — list, detail, close, update SL/TP."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_current_user, get_db
from app.api.schemas import (
    ClosePositionRequest,
    PaginatedResponse,
    UpdateStopLossRequest,
    UpdateTakeProfitRequest,
)
from app.config.constants import CloseReason, Direction, PositionStatus

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/exchange-positions")
async def get_exchange_positions(user: str = Depends(get_current_user)):
    """Fetch real positions from Binance Futures exchange."""
    try:
        from app.data.providers.exchange_factory import create_exchange

        exchange = await create_exchange(auth=True)
        try:
            positions = await exchange.fetch_positions()
            # Filter to only positions with non-zero amount
            active = []
            for p in positions:
                amt = abs(float(p.get("contracts", 0) or 0))
                if amt > 0:
                    active.append({
                        "symbol": p.get("symbol", ""),
                        "direction": "LONG" if float(p.get("contracts", 0) or 0) > 0 else "SHORT",
                        "entry_price": float(p.get("entryPrice", 0) or 0),
                        "current_price": float(p.get("markPrice", 0) or 0),
                        "quantity": amt,
                        "leverage": int(p.get("leverage", 1) or 1),
                        "unrealized_pnl": float(p.get("unrealizedPnl", 0) or 0),
                        "margin": float(p.get("initialMargin", 0) or 0),
                        "liquidation_price": float(p.get("liquidationPrice", 0) or 0),
                        "notional": float(p.get("notional", 0) or 0),
                    })
            return {"positions": active, "count": len(active), "source": "binance"}
        finally:
            await exchange.close()
    except Exception as exc:
        logger.warning("exchange_positions.failed", error=str(exc))
        return {"positions": [], "count": 0, "source": "error", "error": "Exchange positions unavailable"}


@router.get("", response_model=PaginatedResponse)
async def list_positions(
    symbol: str | None = Query(default=None),
    status: str | None = Query(default="OPEN"),
    mode: str | None = Query(default=None, description="Filter by trading_mode: paper or live"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """List all positions with optional filters."""
    from sqlalchemy import select, func
    from app.db.models import PositionModel

    query = select(PositionModel).order_by(PositionModel.opened_at.desc())
    if symbol:
        query = query.where(PositionModel.symbol == symbol)
    if status:
        query = query.where(PositionModel.status == status)
    if mode and mode in ("paper", "live"):
        query = query.where(PositionModel.trading_mode == mode)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.scalars().all()

    items = [_position_to_dict(row) for row in rows]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{position_id}")
async def get_position(
    position_id: str,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Get position details with current P&L."""
    from sqlalchemy import select
    from app.db.models import PositionModel

    result = await db.execute(
        select(PositionModel).where(PositionModel.id == position_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return _position_to_dict(row)


@router.post("/{position_id}/close")
async def close_position(
    position_id: str,
    request: ClosePositionRequest | None = None,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Close a position at market price."""
    from datetime import UTC, datetime
    from sqlalchemy import select
    from app.db.models import PositionModel

    result = await db.execute(
        select(PositionModel).where(PositionModel.id == position_id)
    )
    pos = result.scalar_one_or_none()
    if pos is None:
        raise HTTPException(status_code=404, detail="Position not found")
    if pos.status == PositionStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Position already closed")

    close_pct = request.close_pct if request else 100.0
    total_qty = float(pos.remaining_qty or pos.quantity)
    closed_qty = total_qty * (close_pct / 100.0)

    # Calculate realized PnL
    entry_price = float(pos.entry_price)
    current_price = float(pos.current_price) if pos.current_price else entry_price
    direction_multiplier = 1.0 if pos.direction == Direction.LONG else -1.0
    realized_pnl = (current_price - entry_price) * closed_qty * direction_multiplier
    pos.realized_pnl = float(pos.realized_pnl or 0) + realized_pnl

    if close_pct >= 100.0:
        pos.status = PositionStatus.CLOSED
        pos.close_reason = CloseReason.MANUAL_CLOSE
        pos.closed_at = datetime.now(tz=UTC)
        pos.remaining_qty = 0
    else:
        pos.remaining_qty = total_qty - closed_qty
        pos.status = PositionStatus.REDUCING

    await db.commit()

    # Notify in-memory executor so PositionTracker stops monitoring this position
    from app.bot.service import bot_service
    if bot_service.executor is not None and close_pct >= 100.0:
        try:
            bot_service.executor.close_position(
                position_id, close_price=current_price, reason=CloseReason.MANUAL_CLOSE
            )
        except Exception as exc:
            logger.debug("positions.executor_close_failed", error=str(exc))

    return {
        "position_id": position_id,
        "status": pos.status,
        "close_reason": pos.close_reason,
        "close_pct": close_pct,
        "closed_qty": closed_qty,
        "realized_pnl": round(realized_pnl, 8),
        "remaining_qty": float(pos.remaining_qty) if pos.remaining_qty else 0,
    }


@router.put("/{position_id}/sl")
async def update_stop_loss(
    position_id: str,
    request: UpdateStopLossRequest,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Update position stop loss."""
    from sqlalchemy import select
    from app.db.models import PositionModel

    result = await db.execute(
        select(PositionModel).where(PositionModel.id == position_id)
    )
    pos = result.scalar_one_or_none()
    if pos is None:
        raise HTTPException(status_code=404, detail="Position not found")
    if pos.status == PositionStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Cannot update closed position")

    pos.stop_loss = request.new_sl
    await db.commit()

    return {"position_id": position_id, "stop_loss": request.new_sl}


@router.put("/{position_id}/tp")
async def update_take_profit(
    position_id: str,
    request: UpdateTakeProfitRequest,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Update position take profit levels."""
    from sqlalchemy import select
    from app.db.models import PositionModel

    result = await db.execute(
        select(PositionModel).where(PositionModel.id == position_id)
    )
    pos = result.scalar_one_or_none()
    if pos is None:
        raise HTTPException(status_code=404, detail="Position not found")
    if pos.status == PositionStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Cannot update closed position")

    # Update TP prices from request
    for tp in request.take_profits:
        level = tp.get("level", "")
        price = tp.get("price")
        if level == "TP1" and price:
            pos.tp1_price = price
        elif level == "TP2" and price:
            pos.tp2_price = price
        elif level == "TP3" and price:
            pos.tp3_price = price

    await db.commit()

    return {
        "position_id": position_id,
        "tp1_price": float(pos.tp1_price) if pos.tp1_price else None,
        "tp2_price": float(pos.tp2_price) if pos.tp2_price else None,
        "tp3_price": float(pos.tp3_price) if pos.tp3_price else None,
    }


def _position_to_dict(row) -> dict:
    """Convert PositionModel to API response dict."""
    return {
        "id": row.id,
        "signal_id": row.signal_id,
        "opened_at": row.opened_at.isoformat() if row.opened_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "symbol": row.symbol,
        "direction": row.direction,
        "entry_price": float(row.entry_price) if row.entry_price else None,
        "current_price": float(row.current_price) if row.current_price else None,
        "quantity": float(row.quantity) if row.quantity else None,
        "remaining_qty": float(row.remaining_qty) if row.remaining_qty else None,
        "leverage": row.leverage,
        "stop_loss": float(row.stop_loss) if row.stop_loss else None,
        "tp1_price": float(row.tp1_price) if row.tp1_price else None,
        "tp2_price": float(row.tp2_price) if row.tp2_price else None,
        "tp3_price": float(row.tp3_price) if row.tp3_price else None,
        "unrealized_pnl": float(row.unrealized_pnl) if row.unrealized_pnl else 0,
        "realized_pnl": float(row.realized_pnl) if row.realized_pnl else 0,
        "total_fees": float(row.total_fees) if row.total_fees else 0,
        "status": row.status,
        "close_reason": row.close_reason,
        "trading_mode": getattr(row, "trading_mode", "paper") or "paper",
        "exchange_order_id": getattr(row, "exchange_order_id", None),
        "strategy_name": getattr(row, "strategy_name", None),
    }
