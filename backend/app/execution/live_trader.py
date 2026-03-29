"""Live Trader - real order execution via Binance CCXT provider."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import structlog

from app.config.constants import (
    Direction,
    OrderSide,
    OrderStatus,
    OrderType,
    TAKER_FEE,
)
from app.core.models import OrderIntent, OrderResult, Position, TakeProfit
from app.data.providers.binance import BinanceProvider

logger = structlog.get_logger(__name__)


class LiveTrader:
    """Executes real orders on Binance USDM Futures via CCXT.

    Mirrors PaperTrader interface so Executor can swap transparently.
    Uses an asyncio lock to prevent concurrent CCXT calls which can
    corrupt the internal HTTP session state.
    """

    def __init__(self, provider: BinanceProvider) -> None:
        self._provider = provider
        self._sl_order_ids: dict[str, str] = {}   # position_id -> SL order id
        self._tp_order_ids: dict[str, list[str]] = {}  # position_id -> [TP order ids]
        self._lock = asyncio.Lock()

    async def execute_order(
        self,
        order: OrderIntent,
        current_price: float | None = None,
    ) -> OrderResult:
        """Execute a real order on Binance.

        1. Set leverage
        2. Place main MARKET order
        3. Place STOP_MARKET for SL
        4. Place TAKE_PROFIT_MARKET for each TP level
        """
        async with self._lock:
            return await self._execute_order_inner(order, current_price)

    async def _execute_order_inner(
        self,
        order: OrderIntent,
        current_price: float | None = None,
    ) -> OrderResult:
        try:
            # 1. Set leverage
            await self._provider.set_leverage(order.symbol, order.leverage)
            logger.info(
                "live.leverage_set",
                symbol=order.symbol,
                leverage=order.leverage,
            )

            # 2. Place main order
            side = order.side.value.lower()  # "buy" or "sell"
            order_type = "market" if order.order_type == OrderType.MARKET else "limit"
            price = order.price if order.order_type != OrderType.MARKET else None
            amount = self._provider.amount_to_precision(order.symbol, order.quantity)

            exchange_order = await self._provider.create_order(
                symbol=order.symbol,
                side=side,
                order_type=order_type,
                amount=amount,
                price=price,
            )

            if exchange_order is None:
                return OrderResult(
                    success=False,
                    order_id=str(order.id),
                    message="Exchange returned empty response",
                    status=OrderStatus.REJECTED,
                )

            # Extract fill details from exchange response
            filled_price = float(exchange_order.get("average", 0) or exchange_order.get("price", 0) or 0)
            filled_qty = float(exchange_order.get("filled", 0) or order.quantity)
            exchange_order_id = str(exchange_order.get("id", ""))
            fee_info = exchange_order.get("fee") or {}
            fees = float(fee_info.get("cost", 0) or 0)

            if not fees:
                fees = filled_qty * filled_price * TAKER_FEE

            logger.info(
                "live.order_filled",
                symbol=order.symbol,
                side=side,
                filled_price=filled_price,
                filled_qty=filled_qty,
                exchange_order_id=exchange_order_id,
            )

            # 3. Place SL order (STOP_MARKET)
            sl_order_id = await self._place_stop_loss(
                order.symbol, order.side, order.stop_loss, filled_qty,
            )

            # 4. Place TP orders (TAKE_PROFIT_MARKET)
            tp_order_ids = await self._place_take_profits(
                order.symbol, order.side, order.take_profits, filled_qty,
            )

            # Track SL/TP order IDs for cancellation on close
            pos_key = str(order.id)
            if sl_order_id:
                self._sl_order_ids[pos_key] = sl_order_id
            if tp_order_ids:
                self._tp_order_ids[pos_key] = tp_order_ids

            return OrderResult(
                success=True,
                order_id=str(order.id),
                exchange_order_id=exchange_order_id,
                message="Live order filled on Binance",
                filled_price=filled_price,
                filled_quantity=filled_qty,
                fees=fees,
                status=OrderStatus.FILLED,
            )

        except Exception as e:
            logger.error("live.execution_failed", error=str(e), symbol=order.symbol)
            return OrderResult(
                success=False,
                order_id=str(order.id),
                message=f"Live execution failed: {e}",
                status=OrderStatus.REJECTED,
            )

    async def close_position(
        self,
        position_id: str,
        symbol: str,
        direction: Direction,
        quantity: float,
        close_price: float,
        reason: str = "MANUAL_CLOSE",
    ) -> OrderResult:
        """Close a position on Binance by placing opposite-side market order."""
        async with self._lock:
            return await self._close_position_inner(
                position_id, symbol, direction, quantity, close_price, reason,
            )

    async def _close_position_inner(
        self,
        position_id: str,
        symbol: str,
        direction: Direction,
        quantity: float,
        close_price: float,
        reason: str = "MANUAL_CLOSE",
    ) -> OrderResult:
        try:
            # Opposite side to close
            close_side = "sell" if direction == Direction.LONG else "buy"
            close_qty = self._provider.amount_to_precision(symbol, quantity)

            exchange_order = await self._provider.create_order(
                symbol=symbol,
                side=close_side,
                order_type="market",
                amount=close_qty,
                params={"reduceOnly": True},
            )

            filled_price = float(exchange_order.get("average", 0) or exchange_order.get("price", 0) or 0)
            filled_qty = float(exchange_order.get("filled", 0) or quantity)
            exchange_order_id = str(exchange_order.get("id", ""))
            fee_info = exchange_order.get("fee") or {}
            fees = float(fee_info.get("cost", 0) or 0)

            if not fees:
                fees = filled_qty * filled_price * TAKER_FEE

            # Cancel associated SL/TP orders
            await self._cancel_conditional_orders(position_id, symbol)

            logger.info(
                "live.position_closed",
                symbol=symbol,
                direction=direction,
                filled_price=filled_price,
                reason=reason,
            )

            return OrderResult(
                success=True,
                order_id=position_id,
                exchange_order_id=exchange_order_id,
                message=f"Position closed: {reason}",
                filled_price=filled_price,
                filled_quantity=filled_qty,
                fees=fees,
                status=OrderStatus.FILLED,
            )

        except Exception as e:
            logger.error(
                "live.close_failed",
                error=str(e),
                symbol=symbol,
                position_id=position_id,
            )
            return OrderResult(
                success=False,
                order_id=position_id,
                message=f"Close failed: {e}",
                status=OrderStatus.REJECTED,
            )

    async def _place_stop_loss(
        self,
        symbol: str,
        order_side: OrderSide,
        stop_price: float,
        quantity: float,
    ) -> str | None:
        """Place a STOP_MARKET order for SL. Returns exchange order ID."""
        try:
            sl_side = "sell" if order_side == OrderSide.BUY else "buy"
            sl_qty = self._provider.amount_to_precision(symbol, quantity)
            sl_px = self._provider.price_to_precision(symbol, stop_price)

            sl_order = await self._provider.create_order(
                symbol=symbol,
                side=sl_side,
                order_type="STOP_MARKET",
                amount=sl_qty,
                params={
                    "stopPrice": sl_px,
                    "reduceOnly": True,
                },
            )
            sl_id = str(sl_order.get("id", ""))
            logger.info("live.sl_placed", symbol=symbol, stop_price=sl_px, order_id=sl_id)
            return sl_id
        except Exception as e:
            logger.warning("live.sl_placement_failed", error=str(e), symbol=symbol)
            return None

    async def _place_take_profits(
        self,
        symbol: str,
        order_side: OrderSide,
        take_profits: list[TakeProfit],
        total_quantity: float,
    ) -> list[str]:
        """Place TAKE_PROFIT_MARKET orders for each TP level."""
        tp_ids: list[str] = []
        tp_side = "sell" if order_side == OrderSide.BUY else "buy"

        for tp in take_profits:
            try:
                raw_qty = total_quantity * (tp.close_pct / 100.0)
                tp_qty = self._provider.amount_to_precision(symbol, raw_qty)
                tp_px = self._provider.price_to_precision(symbol, tp.price)
                if tp_qty <= 0:
                    continue

                tp_order = await self._provider.create_order(
                    symbol=symbol,
                    side=tp_side,
                    order_type="TAKE_PROFIT_MARKET",
                    amount=tp_qty,
                    params={
                        "stopPrice": tp_px,
                        "reduceOnly": True,
                    },
                )
                tp_id = str(tp_order.get("id", ""))
                tp_ids.append(tp_id)
                logger.info(
                    "live.tp_placed",
                    symbol=symbol,
                    level=tp.level,
                    price=tp_px,
                    qty=tp_qty,
                    order_id=tp_id,
                )
            except Exception as e:
                logger.warning(
                    "live.tp_placement_failed",
                    error=str(e),
                    symbol=symbol,
                    level=tp.level,
                )

        return tp_ids

    async def _cancel_conditional_orders(self, position_id: str, symbol: str) -> None:
        """Cancel SL and TP orders for a position."""
        # Cancel SL
        sl_id = self._sl_order_ids.pop(position_id, None)
        if sl_id:
            try:
                await self._provider.cancel_order(sl_id, symbol)
                logger.info("live.sl_cancelled", order_id=sl_id, symbol=symbol)
            except Exception as e:
                logger.warning("live.sl_cancel_failed", error=str(e), order_id=sl_id)

        # Cancel TPs
        tp_ids = self._tp_order_ids.pop(position_id, [])
        for tp_id in tp_ids:
            try:
                await self._provider.cancel_order(tp_id, symbol)
                logger.info("live.tp_cancelled", order_id=tp_id, symbol=symbol)
            except Exception as e:
                logger.warning("live.tp_cancel_failed", error=str(e), order_id=tp_id)
