"""Executor - main execution orchestrator for trading signals."""

from __future__ import annotations

import structlog
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.config.constants import (
    CloseReason,
    Direction,
    EventChannel,
    OrderStatus,
    PositionStatus,
)
from app.core.events import event_bus
from app.core.models import (
    CompositeSignal,
    EventMessage,
    OrderIntent,
    OrderResult,
    Position,
)
from app.execution.order_manager import OrderManager, OrderValidationError
from app.execution.paper_trader import PaperTrader
from app.execution.position_tracker import PositionEvent, PositionTracker
from app.risk import CircuitBreaker, PortfolioRiskManager

if TYPE_CHECKING:
    from app.execution.live_trader import LiveTrader

logger = structlog.get_logger(__name__)


class ExecutionResult:
    """Result of executing a signal through the full pipeline."""

    __slots__ = ("success", "order_result", "position", "message")

    def __init__(
        self,
        success: bool,
        order_result: OrderResult | None = None,
        position: Position | None = None,
        message: str = "",
    ) -> None:
        self.success = success
        self.order_result = order_result
        self.position = position
        self.message = message

    def __repr__(self) -> str:
        return f"ExecutionResult(success={self.success}, msg={self.message!r})"


class Executor:
    """Main execution engine orchestrator.

    Flow:
    1. Receive approved signal
    2. Pre-execution checks (circuit breaker, portfolio limits)
    3. Convert signal → order
    4. Validate order
    5. Execute via paper trader (or live in future)
    6. Create position and register with tracker
    7. Publish events

    Supports paper trading and live trading via CCXT.
    """

    def __init__(
        self,
        portfolio: PortfolioRiskManager,
        circuit_breaker: CircuitBreaker | None = None,
        paper_trader: PaperTrader | None = None,
        live_trader: LiveTrader | None = None,
        is_paper: bool = True,
    ) -> None:
        self._portfolio = portfolio
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._is_paper = is_paper
        self._live_trader = live_trader
        self._paper_trader = paper_trader or PaperTrader(
            initial_balance=portfolio.get_state().balance,
        )
        self._order_manager = OrderManager(is_paper=is_paper)
        self._position_tracker = PositionTracker()

    @property
    def is_paper(self) -> bool:
        return self._is_paper

    @property
    def paper_balance(self) -> float | None:
        """Current paper trading balance, or None if not in paper mode."""
        if self._is_paper and self._paper_trader:
            return self._paper_trader.balance
        return None

    @property
    def paper_equity(self) -> float | None:
        """Current paper equity (balance + unrealized P&L)."""
        if self._is_paper and self._paper_trader:
            return self._paper_trader.equity
        return None

    @property
    def order_manager(self) -> OrderManager:
        return self._order_manager

    @property
    def position_tracker(self) -> PositionTracker:
        return self._position_tracker

    @property
    def paper_trader(self) -> PaperTrader:
        return self._paper_trader

    async def execute_signal(
        self,
        signal: CompositeSignal,
        current_price: float | None = None,
        use_market: bool = False,
    ) -> ExecutionResult:
        """Execute an approved signal through the full pipeline.

        Args:
            signal: Approved CompositeSignal from risk manager.
            current_price: Current market price (for market orders).
            use_market: Force market order.

        Returns:
            ExecutionResult with order and position details.
        """
        # 1. Pre-execution checks
        check_result = self._pre_execution_checks(signal)
        if check_result is not None:
            return check_result

        # 2. Convert signal → order
        try:
            order = self._order_manager.signal_to_order(signal, use_market=use_market)
        except OrderValidationError as e:
            return ExecutionResult(success=False, message=f"Order creation failed: {e}")

        # 3. Validate order
        errors = self._order_manager.validate_order(
            order,
            balance=self._paper_trader.balance if self._is_paper else self._portfolio.get_state().balance,
            open_positions=self._position_tracker.position_count,
            current_price=current_price or signal.entry_price,
        )
        if errors:
            result = self._order_manager.reject_order(str(order.id), "; ".join(errors))
            return ExecutionResult(
                success=False,
                order_result=result,
                message=f"Validation failed: {'; '.join(errors)}",
            )

        # 4. Execute order
        self._order_manager.register_pending(order)
        order_result = await self._execute_order(order, current_price)

        if not order_result.success:
            return ExecutionResult(
                success=False,
                order_result=order_result,
                message=f"Execution failed: {order_result.message}",
            )

        # 5. Complete order and create position
        self._order_manager.complete_order(
            str(order.id),
            filled_price=order_result.filled_price,
            filled_quantity=order_result.filled_quantity,
            exchange_order_id=order_result.exchange_order_id,
            fees=order_result.fees,
        )

        position = OrderManager.create_position_from_fill(
            order,
            filled_price=order_result.filled_price,
            filled_quantity=order_result.filled_quantity,
            fees=order_result.fees,
        )

        # 6. Register with tracker and portfolio
        self._position_tracker.add_position(position)
        self._portfolio.add_position(position)

        return ExecutionResult(
            success=True,
            order_result=order_result,
            position=position,
            message="Signal executed successfully",
        )

    async def execute_signal_and_publish(
        self,
        signal: CompositeSignal,
        current_price: float | None = None,
        use_market: bool = False,
    ) -> ExecutionResult:
        """Execute signal and publish events to EventBus."""
        result = await self.execute_signal(signal, current_price, use_market)

        if result.success:
            await event_bus.publish(
                EventChannel.ORDER_FILLED,
                EventMessage(
                    event_type="order.filled",
                    data={
                        "signal_id": str(signal.id),
                        "position_id": str(result.position.id) if result.position else None,
                        "filled_price": result.order_result.filled_price if result.order_result else None,
                    },
                ),
            )
            # Persist to DB (best-effort)
            await self._persist_fill(signal, result)
        else:
            await event_bus.publish(
                EventChannel.RISK_ALERT,
                EventMessage(
                    event_type="execution.failed",
                    data={"signal_id": str(signal.id), "reason": result.message},
                ),
            )

        return result

    async def process_price_update(
        self,
        symbol: str,
        price: float,
    ) -> list[PositionEvent]:
        """Process a price update and handle resulting events.

        Returns list of events that were processed.
        """
        events = self._position_tracker.check_price(symbol, price)

        for event in events:
            await self._handle_position_event(event)

        return events

    async def close_position(
        self,
        position_id: str,
        close_price: float,
        reason: str = CloseReason.MANUAL_CLOSE,
    ) -> float:
        """Manually close a position.

        Returns realized P&L.
        """
        if self._is_paper:
            pnl = self._paper_trader.close_position(
                position_id, close_price, reason=reason,
            )
        else:
            # Live: close via exchange
            pos = self._position_tracker.get_position(position_id)
            if pos and self._live_trader:
                result = await self._live_trader.close_position(
                    position_id=position_id,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    quantity=pos.remaining_qty,
                    close_price=close_price,
                    reason=reason,
                )
                if result.success:
                    pnl = self._calc_pnl(pos, result.filled_price or close_price)
                else:
                    pnl = 0.0
            else:
                pnl = 0.0

        # Update portfolio
        self._portfolio.record_trade_result(pnl)
        self._portfolio.remove_position(position_id)

        # Remove from tracker
        self._position_tracker.remove_position(position_id)

        # Persist to DB
        await self._persist_position_close(position_id, close_price, pnl, reason)

        return pnl

    def _pre_execution_checks(self, signal: CompositeSignal) -> ExecutionResult | None:
        """Run pre-execution checks. Returns ExecutionResult if blocked."""
        # Safety gate: TRADING_ENABLED must be true (live trading only)
        # Paper trading is always allowed regardless of the kill switch
        if not self._is_paper:
            from app.config.settings import get_settings
            settings = get_settings()
            if not settings.trading_enabled:
                return ExecutionResult(
                    success=False,
                    message="Trading disabled: TRADING_ENABLED=false (master kill switch)",
                )

        # Circuit breaker check
        if not self._circuit_breaker.is_trading_allowed():
            return ExecutionResult(
                success=False,
                message=f"Circuit breaker {self._circuit_breaker.state}: trading blocked",
            )

        # Portfolio limits check
        allowed, reason = self._portfolio.can_open_position()
        if not allowed:
            return ExecutionResult(
                success=False,
                message=f"Portfolio limits: {reason}",
            )

        return None

    async def _execute_order(
        self,
        order: OrderIntent,
        current_price: float | None = None,
    ) -> OrderResult:
        """Execute order via paper or live trader.

        Live orders include retry with exponential backoff on RateLimitError.
        """
        if self._is_paper:
            return self._paper_trader.execute_order(order, current_price)

        # Live trading via CCXT
        if self._live_trader is None:
            return OrderResult(
                success=False,
                order_id=str(order.id),
                message="Live trader not configured",
                status=OrderStatus.REJECTED,
            )

        # Retry with exponential backoff on rate limit errors
        import asyncio as _asyncio
        from app.core.exceptions import RateLimitError

        max_retries = 3
        base_delay = 1.0
        for attempt in range(max_retries):
            try:
                return await self._live_trader.execute_order(order, current_price)
            except RateLimitError:
                if attempt == max_retries - 1:
                    logger.error(
                        "executor.rate_limit_exhausted",
                        order_id=str(order.id),
                        attempts=max_retries,
                    )
                    return OrderResult(
                        success=False,
                        order_id=str(order.id),
                        message=f"Rate limit exceeded after {max_retries} retries",
                        status=OrderStatus.REJECTED,
                    )
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "executor.rate_limit_retry",
                    order_id=str(order.id),
                    attempt=attempt + 1,
                    delay=delay,
                )
                await _asyncio.sleep(delay)

        # Should not reach here, but safety fallback
        return OrderResult(
            success=False,
            order_id=str(order.id),
            message="Unexpected retry exhaustion",
            status=OrderStatus.REJECTED,
        )

    async def _handle_position_event(self, event: PositionEvent) -> None:
        """Handle a position event from the tracker."""
        if event.event_type == "close":
            # Full close
            if self._is_paper:
                pnl = self._paper_trader.close_position(
                    event.position_id, event.close_price, reason=event.reason,
                )
            else:
                pos = self._position_tracker.get_position(event.position_id)
                if pos and self._live_trader:
                    result = await self._live_trader.close_position(
                        position_id=event.position_id,
                        symbol=pos.symbol,
                        direction=pos.direction,
                        quantity=pos.remaining_qty,
                        close_price=event.close_price,
                        reason=event.reason,
                    )
                    pnl = self._calc_pnl(pos, result.filled_price or event.close_price) if result.success else 0.0
                else:
                    pnl = 0.0
            self._portfolio.record_trade_result(pnl)
            self._portfolio.remove_position(event.position_id)
            self._position_tracker.remove_position(event.position_id)
            await self._persist_position_close(event.position_id, event.close_price, pnl, event.reason)

        elif event.event_type == "partial_close":
            # Partial close
            if self._is_paper:
                partial_pnl = self._paper_trader.close_position(
                    event.position_id, event.close_price,
                    close_qty=event.close_qty, reason=event.reason,
                )
            else:
                pos = self._position_tracker.get_position(event.position_id)
                if pos and self._live_trader:
                    result = await self._live_trader.close_position(
                        position_id=event.position_id,
                        symbol=pos.symbol,
                        direction=pos.direction,
                        quantity=event.close_qty or pos.remaining_qty,
                        close_price=event.close_price,
                        reason=event.reason,
                    )
                    partial_pnl = self._calc_pnl(pos, result.filled_price or event.close_price, event.close_qty) if result.success else 0.0
                else:
                    partial_pnl = 0.0
            self._portfolio.record_trade_result(partial_pnl)

    @staticmethod
    def _calc_pnl(pos: Position, close_price: float, qty: float | None = None) -> float:
        """Calculate realized P&L for a position close."""
        q = qty if qty is not None else pos.remaining_qty
        if pos.direction == Direction.LONG:
            return (close_price - pos.entry_price) * q * pos.leverage
        else:
            return (pos.entry_price - close_price) * q * pos.leverage

    # ── DB persistence (best-effort) ───────────────────────────

    async def _persist_fill(
        self, signal: CompositeSignal, result: ExecutionResult,
    ) -> None:
        """Save order and position to DB after successful fill."""
        try:
            from app.db.session import get_session_factory
            from app.db.models import OrderModel, PositionModel

            factory = get_session_factory()
            async with factory() as session:
                # Save order
                order_result = result.order_result
                if order_result:
                    order_row = OrderModel(
                        id=order_result.order_id or str(signal.id),
                        signal_id=str(signal.id),
                        exchange_order_id=order_result.exchange_order_id,
                        symbol=signal.symbol,
                        side="BUY" if signal.direction == Direction.LONG else "SELL",
                        order_type="MARKET",
                        price=order_result.filled_price,
                        quantity=order_result.filled_quantity or signal.position_size.quantity,
                        filled_qty=order_result.filled_quantity or 0,
                        avg_fill_price=order_result.filled_price,
                        status=str(order_result.status),
                        fees=order_result.fees,
                    )
                    session.add(order_row)

                # Save position
                pos = result.position
                if pos:
                    tp_prices = {tp.level: tp.price for tp in pos.take_profits}
                    # Determine top strategy from signal scores
                    top_strategy = None
                    if signal.strategy_scores:
                        top_strategy = max(signal.strategy_scores, key=signal.strategy_scores.get)  # type: ignore[arg-type]

                    pos_row = PositionModel(
                        id=str(pos.id),
                        signal_id=str(pos.signal_id),
                        symbol=pos.symbol,
                        direction=str(pos.direction),
                        entry_price=pos.entry_price,
                        current_price=pos.current_price,
                        quantity=pos.quantity,
                        remaining_qty=pos.remaining_qty,
                        leverage=pos.leverage,
                        stop_loss=pos.stop_loss,
                        tp1_price=tp_prices.get("TP1"),
                        tp2_price=tp_prices.get("TP2"),
                        tp3_price=tp_prices.get("TP3"),
                        unrealized_pnl=pos.unrealized_pnl,
                        realized_pnl=pos.realized_pnl,
                        total_fees=pos.total_fees,
                        status=str(pos.status),
                        trading_mode="paper" if self._is_paper else "live",
                        exchange_order_id=order_result.exchange_order_id if order_result else None,
                        strategy_name=top_strategy,
                    )
                    session.add(pos_row)

                await session.commit()
                logger.info("executor.fill_persisted", signal_id=str(signal.id))
        except Exception as e:
            logger.warning("executor.persist_fill_failed", error=str(e))

    async def _persist_position_close(
        self, position_id: str, close_price: float, pnl: float, reason: str,
    ) -> None:
        """Update position in DB when closed."""
        try:
            from app.db.session import get_session_factory
            from app.db.models import PositionModel
            from sqlalchemy import update

            factory = get_session_factory()
            async with factory() as session:
                stmt = (
                    update(PositionModel)
                    .where(PositionModel.id == position_id)
                    .values(
                        current_price=close_price,
                        remaining_qty=0,
                        realized_pnl=pnl,
                        unrealized_pnl=0,
                        status="CLOSED",
                        close_reason=reason,
                        closed_at=datetime.now(tz=UTC),
                    )
                )
                await session.execute(stmt)
                await session.commit()
                logger.info("executor.close_persisted", position_id=position_id)
        except Exception as e:
            logger.warning("executor.persist_close_failed", error=str(e))
