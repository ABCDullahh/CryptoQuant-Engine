"""Order endpoints — execute, cancel, list, detail, manual."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_current_user, get_db
from app.api.schemas import ExecuteOrderRequest, ManualOrderRequest, PaginatedResponse
from app.config.constants import (
    DEFAULT_LEVERAGE,
    ENTRY_ZONE_PCT,
    MAX_RISK_PER_TRADE,
    OrderStatus,
    SignalStatus,
    TP1_CLOSE_PCT,
    TP1_RR_RATIO,
    TP2_CLOSE_PCT,
    TP3_CLOSE_PCT,
)
from app.data.providers.exchange_factory import create_exchange

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/execute", status_code=201)
async def execute_order(
    request: ExecuteOrderRequest,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Execute an order from a signal via the bot service executor."""
    from sqlalchemy import select
    from app.db.models import SignalModel, OrderModel
    from app.bot.service import bot_service

    # Check if bot executor is available before proceeding
    if bot_service.executor is None:
        raise HTTPException(
            status_code=409,
            detail="Bot must be running to execute orders",
        )

    # Verify signal exists
    result = await db.execute(
        select(SignalModel).where(SignalModel.id == request.signal_id)
    )
    signal = result.scalar_one_or_none()
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    if signal.status != SignalStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Signal is not active")

    # Calculate and validate quantity
    quantity = request.position_size or float(signal.position_size_qty or 0)
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Position size must be greater than 0")

    entry_price = request.entry_price or float(signal.entry_price)

    # Create order record
    order = OrderModel(
        signal_id=request.signal_id,
        symbol=signal.symbol,
        side="BUY" if signal.direction == "LONG" else "SELL",
        order_type=request.order_type,
        price=entry_price,
        quantity=quantity,
        status=OrderStatus.SUBMITTED,
    )
    db.add(order)

    # Update signal status
    signal.status = SignalStatus.EXECUTING
    await db.commit()
    await db.refresh(order)

    # Execute through the bot service executor (paper or live)
    exec_result = None
    if bot_service.executor is not None:
        try:
            from app.core.models import (
                CompositeSignal, TakeProfit, RiskReward,
                PositionSize, MarketContext,
            )
            # Use signal values — reject if SL is missing (no fabricated defaults)
            if not signal.stop_loss:
                raise HTTPException(status_code=400, detail="Signal has no stop_loss — cannot execute safely")
            sl = float(signal.stop_loss)
            if not signal.tp1_price:
                raise HTTPException(status_code=400, detail="Signal has no TP1 — cannot execute safely")
            tp1 = float(signal.tp1_price)
            tp2 = float(signal.tp2_price) if signal.tp2_price else None
            tp3 = float(signal.tp3_price) if signal.tp3_price else None
            rr1 = abs(tp1 - entry_price) / abs(entry_price - sl) if abs(entry_price - sl) > 0 else TP1_RR_RATIO

            # Use constants for TP close percentages (from constants.py)
            take_profits = [TakeProfit(level="TP1", price=tp1, close_pct=signal.tp1_pct or TP1_CLOSE_PCT, rr_ratio=rr1)]
            if tp2:
                rr2 = abs(tp2 - entry_price) / abs(entry_price - sl) if abs(entry_price - sl) > 0 else rr1 * 1.5
                take_profits.append(TakeProfit(level="TP2", price=tp2, close_pct=signal.tp2_pct or TP2_CLOSE_PCT, rr_ratio=rr2))
            if tp3:
                rr3 = abs(tp3 - entry_price) / abs(entry_price - sl) if abs(entry_price - sl) > 0 else rr1 * 2
                take_profits.append(TakeProfit(level="TP3", price=tp3, close_pct=signal.tp3_pct or TP3_CLOSE_PCT, rr_ratio=rr3))

            # Use signal leverage → configurable default from constants
            leverage = signal.leverage if signal.leverage and signal.leverage > 0 else DEFAULT_LEVERAGE

            composite = CompositeSignal(
                symbol=signal.symbol,
                direction=signal.direction,
                entry_price=entry_price,
                entry_zone=(entry_price * (1 - ENTRY_ZONE_PCT), entry_price * (1 + ENTRY_ZONE_PCT)),
                stop_loss=sl,
                sl_type="FIXED",
                take_profits=take_profits,
                risk_reward=RiskReward(rr_tp1=rr1, weighted_rr=rr1),
                position_size=PositionSize(
                    quantity=quantity, notional=quantity * entry_price,
                    margin=quantity * entry_price / max(leverage, 1),
                    risk_amount=abs(entry_price - sl) * quantity,
                    risk_pct=MAX_RISK_PER_TRADE, leverage=leverage,
                ),
                strength=float(signal.signal_strength) if signal.signal_strength else 0.5,
                grade=signal.signal_grade or "B",
                strategy_scores={},
                market_context=MarketContext(),
            )
            exec_result = await bot_service.executor.execute_signal_and_publish(
                composite, current_price=entry_price, use_market=True
            )
            if exec_result and exec_result.success:
                order.status = OrderStatus.FILLED
                order.filled_qty = quantity
                order.avg_fill_price = entry_price
                signal.status = SignalStatus.EXECUTED
            else:
                order.status = OrderStatus.REJECTED
                signal.status = SignalStatus.REJECTED
            await db.commit()
        except Exception as exc:
            logger.error("order.execution_failed", error=str(exc))
            order.status = OrderStatus.REJECTED
            signal.status = SignalStatus.REJECTED
            await db.commit()
    else:
        logger.warning("order.no_executor", detail="Bot service executor not available")

    return {
        "order_id": order.id,
        "signal_id": request.signal_id,
        "symbol": order.symbol,
        "side": order.side,
        "order_type": order.order_type,
        "price": float(order.price) if order.price else None,
        "quantity": float(order.quantity),
        "status": order.status,
        "executed": exec_result.success if exec_result else False,
    }


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Cancel a pending order."""
    from sqlalchemy import select
    from app.db.models import OrderModel

    result = await db.execute(
        select(OrderModel).where(OrderModel.id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.NEW):
        raise HTTPException(status_code=409, detail=f"Cannot cancel order with status {order.status}")

    order.status = OrderStatus.CANCELLED
    await db.commit()

    return {"order_id": order_id, "status": OrderStatus.CANCELLED}


@router.get("", response_model=PaginatedResponse)
async def list_orders(
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """List all orders with optional filters."""
    from sqlalchemy import select, func
    from app.db.models import OrderModel

    query = select(OrderModel).order_by(OrderModel.created_at.desc())
    if symbol:
        query = query.where(OrderModel.symbol == symbol)
    if status:
        query = query.where(OrderModel.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.scalars().all()

    items = [_order_to_dict(row) for row in rows]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Get order details by ID."""
    from sqlalchemy import select
    from app.db.models import OrderModel

    result = await db.execute(
        select(OrderModel).where(OrderModel.id == order_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_dict(row)


@router.post("/manual", status_code=201)
async def manual_order(
    request: ManualOrderRequest,
    user: str = Depends(get_current_user),
):
    """Place a manual order directly on Binance (no signal required)."""
    symbol = request.symbol  # e.g. "BTC/USDT"
    direction = request.direction  # "LONG" or "SHORT"
    order_type = request.order_type
    quantity = request.quantity
    price = request.price  # for LIMIT, STOP_LIMIT
    stop_price = request.stop_price  # for STOP_MARKET, STOP_LIMIT
    leverage = request.leverage
    stop_loss = request.stop_loss
    take_profit = request.take_profit
    reduce_only = request.reduce_only
    time_in_force = request.time_in_force

    # Validation (Pydantic handles type/range; these are business rules)
    if direction not in ("LONG", "SHORT"):
        raise HTTPException(
            status_code=400, detail="Direction must be LONG or SHORT"
        )
    if order_type not in ("MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT"):
        raise HTTPException(status_code=400, detail="Invalid order type")
    if order_type in ("LIMIT", "STOP_LIMIT") and not price:
        raise HTTPException(
            status_code=400, detail=f"Price required for {order_type}"
        )
    if order_type in ("STOP_MARKET", "STOP_LIMIT") and not stop_price:
        raise HTTPException(
            status_code=400, detail=f"Stop price required for {order_type}"
        )

    exchange_symbol = f"{symbol}:USDT" if ":USDT" not in symbol else symbol
    side = "buy" if direction == "LONG" else "sell"

    # Map order types to CCXT
    ccxt_type_map = {
        "MARKET": "market",
        "LIMIT": "limit",
        "STOP_MARKET": "STOP_MARKET",
        "STOP_LIMIT": "STOP",
    }
    ccxt_type = ccxt_type_map.get(order_type, "market")

    exchange = await create_exchange(auth=True)
    try:
        await exchange.load_markets()

        # Set leverage
        try:
            await exchange.set_leverage(leverage, exchange_symbol)
        except Exception as exc:
            logger.warning("manual_order.set_leverage_failed", error=str(exc))

        # Build params
        params: dict = {}
        if stop_price:
            params["stopPrice"] = float(stop_price)
        if reduce_only:
            params["reduceOnly"] = True
        if time_in_force and order_type != "MARKET":
            params["timeInForce"] = time_in_force

        # Place main order
        order = await exchange.create_order(
            symbol=exchange_symbol,
            type=ccxt_type,
            side=side,
            amount=quantity,
            price=float(price) if price else None,
            params=params,
        )

        # Place SL order if provided
        sl_order = None
        if stop_loss:
            sl_side = "sell" if direction == "LONG" else "buy"
            try:
                sl_order = await exchange.create_order(
                    symbol=exchange_symbol,
                    type="STOP_MARKET",
                    side=sl_side,
                    amount=quantity,
                    params={"stopPrice": float(stop_loss), "reduceOnly": True},
                )
            except Exception as exc:
                logger.warning("manual_order.sl_failed", error=str(exc))

        # Place TP order if provided
        tp_order = None
        if take_profit:
            tp_side = "sell" if direction == "LONG" else "buy"
            try:
                tp_order = await exchange.create_order(
                    symbol=exchange_symbol,
                    type="TAKE_PROFIT_MARKET",
                    side=tp_side,
                    amount=quantity,
                    params={
                        "stopPrice": float(take_profit),
                        "reduceOnly": True,
                    },
                )
            except Exception as exc:
                logger.warning("manual_order.tp_failed", error=str(exc))

        return {
            "order_id": order.get("id", ""),
            "symbol": symbol,
            "side": side.upper(),
            "order_type": order_type,
            "quantity": quantity,
            "price": float(price) if price else None,
            "stop_price": float(stop_price) if stop_price else None,
            "status": order.get("status", ""),
            "executed_price": float(order.get("average", 0) or 0),
            "executed_qty": float(order.get("filled", 0) or 0),
            "leverage": leverage,
            "sl_order_id": sl_order.get("id") if sl_order else None,
            "tp_order_id": tp_order.get("id") if tp_order else None,
            "timestamp": order.get("datetime", ""),
        }
    except Exception as exc:
        logger.error("manual_order.failed", symbol=symbol, error=str(exc))
        raise HTTPException(
            status_code=400, detail=f"Order failed: {str(exc)}"
        )
    finally:
        await exchange.close()


def _order_to_dict(row) -> dict:
    """Convert OrderModel to API response dict."""
    return {
        "id": row.id,
        "signal_id": row.signal_id,
        "exchange_order_id": row.exchange_order_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "symbol": row.symbol,
        "side": row.side,
        "order_type": row.order_type,
        "price": float(row.price) if row.price else None,
        "quantity": float(row.quantity) if row.quantity else None,
        "filled_qty": float(row.filled_qty) if row.filled_qty else 0,
        "avg_fill_price": float(row.avg_fill_price) if row.avg_fill_price else None,
        "status": row.status,
        "fees": float(row.fees) if row.fees else 0,
    }
