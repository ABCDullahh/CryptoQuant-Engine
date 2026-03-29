"""Paper Trader - simulated order execution for testing."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.config.constants import (
    DEFAULT_SLIPPAGE_BPS,
    Direction,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionStatus,
    TAKER_FEE,
)
from app.core.models import OrderIntent, OrderResult, Position


class PaperTrader:
    """Simulates order execution without real exchange.

    Features:
    - Configurable slippage model
    - Fee simulation (maker/taker)
    - Position tracking with P&L
    - Instant or realistic fill simulation
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
        fee_rate: float = TAKER_FEE,
    ) -> None:
        self._balance = initial_balance
        self._initial_balance = initial_balance
        self._slippage_bps = slippage_bps
        self._fee_rate = fee_rate
        self._positions: dict[str, Position] = {}
        self._closed_positions: list[Position] = []
        self._trade_count = 0

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def equity(self) -> float:
        unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        return self._balance + unrealized

    @property
    def open_positions(self) -> dict[str, Position]:
        return dict(self._positions)

    @property
    def closed_positions(self) -> list[Position]:
        return list(self._closed_positions)

    @property
    def trade_count(self) -> int:
        return self._trade_count

    def execute_order(
        self,
        order: OrderIntent,
        current_price: float | None = None,
    ) -> OrderResult:
        """Execute a paper order with simulated fill.

        Args:
            order: The order to execute.
            current_price: Current market price (used for market orders).

        Returns:
            OrderResult with simulated fill details.
        """
        # Determine fill price
        if order.order_type == OrderType.MARKET:
            if current_price is None:
                base_price = order.price or 0.0
            else:
                base_price = current_price
        else:
            base_price = order.price if order.price is not None else 0.0

        if base_price <= 0:
            return OrderResult(
                success=False,
                order_id=str(order.id),
                message="Invalid price for paper execution",
                status=OrderStatus.REJECTED,
            )

        # Apply slippage
        filled_price = self._apply_slippage(base_price, order.side)

        # Check margin
        notional = order.quantity * filled_price
        margin_required = notional / max(order.leverage, 1)
        if margin_required > self._balance:
            return OrderResult(
                success=False,
                order_id=str(order.id),
                message=f"Insufficient balance: need {margin_required:.2f}, have {self._balance:.2f}",
                status=OrderStatus.REJECTED,
            )

        # Calculate fees
        fees = notional * self._fee_rate

        # Deduct margin + fees
        margin = notional / max(order.leverage, 1)
        self._balance -= margin + fees

        # Create position
        direction = Direction.LONG if order.side == OrderSide.BUY else Direction.SHORT
        position = Position(
            signal_id=order.signal_id,
            symbol=order.symbol,
            direction=direction,
            entry_price=filled_price,
            current_price=filled_price,
            quantity=order.quantity,
            remaining_qty=order.quantity,
            leverage=order.leverage,
            stop_loss=order.stop_loss,
            take_profits=list(order.take_profits),
            total_fees=fees,
        )

        self._positions[str(position.id)] = position
        self._trade_count += 1

        return OrderResult(
            success=True,
            order_id=str(order.id),
            exchange_order_id=f"PAPER-{uuid4().hex[:8].upper()}",
            message="Paper order filled",
            filled_price=filled_price,
            filled_quantity=order.quantity,
            fees=fees,
            status=OrderStatus.FILLED,
        )

    def update_price(self, symbol: str, price: float) -> None:
        """Update current price for all positions of a symbol."""
        for pos in self._positions.values():
            if pos.symbol == symbol:
                pos.current_price = price
                pos.unrealized_pnl = self._calc_unrealized_pnl(pos)

    def close_position(
        self,
        position_id: str,
        close_price: float,
        close_qty: float | None = None,
        reason: str = "MANUAL_CLOSE",
    ) -> float:
        """Close (or partially close) a position.

        Args:
            position_id: Position ID to close.
            close_price: Price at which to close.
            close_qty: Quantity to close (None = close all remaining).
            reason: Close reason string.

        Returns:
            Realized P&L from this close.
        """
        pos = self._positions.get(position_id)
        if pos is None:
            return 0.0

        qty = close_qty if close_qty is not None else pos.remaining_qty
        qty = min(qty, pos.remaining_qty)

        # Calculate realized P&L
        if pos.direction == Direction.LONG:
            pnl = (close_price - pos.entry_price) * qty * pos.leverage
        else:
            pnl = (pos.entry_price - close_price) * qty * pos.leverage

        # Close fees
        close_fees = qty * close_price * self._fee_rate
        pnl -= close_fees

        # Update position
        pos.remaining_qty -= qty
        pos.realized_pnl += pnl
        pos.total_fees += close_fees

        # Return margin for closed portion + realized P&L (fees already deducted from pnl)
        close_fraction = qty / pos.quantity
        notional = pos.quantity * pos.entry_price
        margin_return = (notional / max(pos.leverage, 1)) * close_fraction
        self._balance += margin_return + pnl

        if pos.remaining_qty <= 1e-10:
            pos.remaining_qty = 0.0
            pos.status = PositionStatus.CLOSED
            pos.closed_at = datetime.now(tz=UTC)
            pos.close_reason = reason
            pos.unrealized_pnl = 0.0
            self._closed_positions.append(pos)
            del self._positions[position_id]
        else:
            pos.status = PositionStatus.REDUCING
            pos.unrealized_pnl = self._calc_unrealized_pnl(pos)

        return pnl

    def _apply_slippage(self, price: float, side: OrderSide) -> float:
        """Apply simulated slippage to fill price."""
        slippage_pct = self._slippage_bps / 10000.0
        if side == OrderSide.BUY:
            return price * (1 + slippage_pct)  # Buy slightly higher
        else:
            return price * (1 - slippage_pct)  # Sell slightly lower

    @staticmethod
    def _calc_unrealized_pnl(pos: Position) -> float:
        """Calculate unrealized P&L for a position."""
        if pos.direction == Direction.LONG:
            return (pos.current_price - pos.entry_price) * pos.remaining_qty * pos.leverage
        else:
            return (pos.entry_price - pos.current_price) * pos.remaining_qty * pos.leverage

    def get_total_pnl(self) -> float:
        """Total P&L (realized + unrealized)."""
        realized = sum(p.realized_pnl for p in self._closed_positions)
        realized += sum(p.realized_pnl for p in self._positions.values())
        unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        return realized + unrealized

    def reset(self) -> None:
        """Reset paper trader to initial state."""
        self._balance = self._initial_balance
        self._positions.clear()
        self._closed_positions.clear()
        self._trade_count = 0
