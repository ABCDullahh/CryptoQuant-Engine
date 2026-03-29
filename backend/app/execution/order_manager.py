"""Order Manager - order creation, validation, and lifecycle management."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.config.constants import (
    CloseReason,
    Direction,
    MAKER_FEE,
    MAX_LEVERAGE,
    MAX_OPEN_POSITIONS,
    OrderSide,
    OrderStatus,
    OrderType,
    SignalGrade,
    TAKER_FEE,
)
from app.core.models import (
    CompositeSignal,
    OrderIntent,
    OrderResult,
    Position,
    TakeProfit,
)


class OrderValidationError(Exception):
    """Raised when order validation fails."""


class OrderManager:
    """Manages order creation, validation, and lifecycle.

    Responsibilities:
    - Convert CompositeSignal → OrderIntent
    - Validate order parameters
    - Track order state transitions
    - Calculate fees
    """

    def __init__(self, is_paper: bool = True) -> None:
        self._is_paper = is_paper
        self._pending_orders: dict[str, OrderIntent] = {}
        self._order_history: list[OrderResult] = []

    @property
    def is_paper(self) -> bool:
        return self._is_paper

    @property
    def pending_count(self) -> int:
        return len(self._pending_orders)

    @property
    def order_history(self) -> list[OrderResult]:
        return list(self._order_history)

    def signal_to_order(
        self,
        signal: CompositeSignal,
        use_market: bool = False,
    ) -> OrderIntent:
        """Convert an approved CompositeSignal into an OrderIntent.

        Args:
            signal: Approved composite signal with position sizing.
            use_market: If True, use MARKET order; else LIMIT.

        Returns:
            OrderIntent ready for execution.
        """
        if signal.direction == Direction.LONG:
            side = OrderSide.BUY
        elif signal.direction == Direction.SHORT:
            side = OrderSide.SELL
        else:
            raise OrderValidationError("Cannot create order for NEUTRAL direction")

        # Grade A → market (fast entry), Grade B/C → limit
        if use_market or signal.grade == SignalGrade.A:
            order_type = OrderType.MARKET
            price = None
        else:
            order_type = OrderType.LIMIT
            price = signal.entry_price

        order = OrderIntent(
            signal_id=signal.id,
            symbol=signal.symbol,
            side=side,
            order_type=order_type,
            price=price,
            quantity=signal.position_size.quantity,
            stop_loss=signal.stop_loss,
            take_profits=list(signal.take_profits),
            leverage=signal.position_size.leverage,
            is_paper=self._is_paper,
        )

        return order

    def validate_order(
        self,
        order: OrderIntent,
        balance: float,
        open_positions: int = 0,
        current_price: float | None = None,
    ) -> list[str]:
        """Validate order before execution.

        Returns:
            List of validation errors (empty if valid).
        """
        errors: list[str] = []

        if order.quantity <= 0:
            errors.append("Quantity must be positive")

        if order.order_type == OrderType.LIMIT and (order.price is None or order.price <= 0):
            errors.append("Limit order requires a valid price")

        if order.leverage > MAX_LEVERAGE:
            errors.append(f"Leverage {order.leverage} exceeds max {MAX_LEVERAGE}")

        if order.leverage < 1:
            errors.append("Leverage must be >= 1")

        if open_positions >= MAX_OPEN_POSITIONS:
            errors.append(f"Max positions ({MAX_OPEN_POSITIONS}) reached")

        # Check margin requirement - use current_price for market orders
        price_for_margin = order.price or current_price
        if price_for_margin is not None and price_for_margin > 0:
            notional = order.quantity * price_for_margin
            margin_required = notional / order.leverage
            if margin_required > balance:
                errors.append(
                    f"Insufficient balance: need {margin_required:.2f}, have {balance:.2f}"
                )

        if order.stop_loss <= 0:
            errors.append("Stop loss must be positive")

        return errors

    def register_pending(self, order: OrderIntent) -> None:
        """Register an order as pending execution."""
        self._pending_orders[str(order.id)] = order

    def complete_order(
        self,
        order_id: str,
        filled_price: float,
        filled_quantity: float,
        exchange_order_id: str | None = None,
        fees: float = 0.0,
    ) -> OrderResult:
        """Mark an order as filled and record the result."""
        order = self._pending_orders.pop(order_id, None)

        result = OrderResult(
            success=True,
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            message="Order filled",
            filled_price=filled_price,
            filled_quantity=filled_quantity,
            fees=fees,
            status=OrderStatus.FILLED,
        )
        self._order_history.append(result)
        return result

    def cancel_order(self, order_id: str, reason: str = "User cancelled") -> OrderResult:
        """Cancel a pending order."""
        self._pending_orders.pop(order_id, None)

        result = OrderResult(
            success=False,
            order_id=order_id,
            message=reason,
            status=OrderStatus.CANCELLED,
        )
        self._order_history.append(result)
        return result

    def reject_order(self, order_id: str, reason: str) -> OrderResult:
        """Reject an order that failed validation."""
        self._pending_orders.pop(order_id, None)

        result = OrderResult(
            success=False,
            order_id=order_id,
            message=reason,
            status=OrderStatus.REJECTED,
        )
        self._order_history.append(result)
        return result

    @staticmethod
    def calculate_fees(
        quantity: float,
        price: float,
        is_maker: bool = False,
    ) -> float:
        """Calculate trading fees."""
        notional = quantity * price
        fee_rate = MAKER_FEE if is_maker else TAKER_FEE
        return notional * fee_rate

    @staticmethod
    def create_position_from_fill(
        order: OrderIntent,
        filled_price: float,
        filled_quantity: float,
        fees: float = 0.0,
    ) -> Position:
        """Create a Position model from a filled order."""
        direction = Direction.LONG if order.side == OrderSide.BUY else Direction.SHORT

        return Position(
            signal_id=order.signal_id,
            symbol=order.symbol,
            direction=direction,
            entry_price=filled_price,
            current_price=filled_price,
            quantity=filled_quantity,
            remaining_qty=filled_quantity,
            leverage=order.leverage,
            stop_loss=order.stop_loss,
            take_profits=list(order.take_profits),
            total_fees=fees,
        )
