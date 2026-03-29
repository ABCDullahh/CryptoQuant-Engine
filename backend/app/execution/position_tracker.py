"""Position Tracker - monitors open positions and manages SL/TP lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime

from app.config.constants import (
    CloseReason,
    Direction,
    PositionStatus,
    TRAILING_STOP_CALLBACK_PCT,
)
from app.core.models import Position, TakeProfit


class PositionEvent:
    """Event emitted by PositionTracker when something happens."""

    __slots__ = ("event_type", "position_id", "symbol", "close_qty", "close_price", "reason", "data")

    def __init__(
        self,
        event_type: str,
        position_id: str,
        symbol: str,
        close_qty: float = 0.0,
        close_price: float = 0.0,
        reason: str = "",
        data: dict | None = None,
    ) -> None:
        self.event_type = event_type
        self.position_id = position_id
        self.symbol = symbol
        self.close_qty = close_qty
        self.close_price = close_price
        self.reason = reason
        self.data = data or {}

    def __repr__(self) -> str:
        return f"PositionEvent({self.event_type}, {self.symbol}, reason={self.reason})"


class PositionTracker:
    """Monitors open positions, checks SL/TP hits, manages partial closes.

    Lifecycle:
    1. Entry Fill → position opened
    2. SL Hit → close 100%
    3. TP1 Hit → close 50%, move SL to breakeven
    4. TP2 Hit → close 30%, activate trailing stop
    5. TP3 Hit → close remaining 20%
    """

    def __init__(self) -> None:
        self._positions: dict[str, Position] = {}
        self._tp_hit: dict[str, set[str]] = {}  # pos_id → set of hit TP levels
        self._trailing_active: dict[str, bool] = {}
        self._highest_since_entry: dict[str, float] = {}
        self._lowest_since_entry: dict[str, float] = {}

    @property
    def positions(self) -> dict[str, Position]:
        return dict(self._positions)

    @property
    def position_count(self) -> int:
        return len(self._positions)

    def get_position(self, position_id: str) -> Position | None:
        """Get a position by ID."""
        return self._positions.get(position_id)

    def get_positions_by_symbol(self, symbol: str) -> list[Position]:
        """Get all open positions for a given symbol."""
        return [p for p in self._positions.values() if p.symbol == symbol]

    def add_position(self, position: Position) -> None:
        """Register a new open position for tracking."""
        pid = str(position.id)
        self._positions[pid] = position
        self._tp_hit[pid] = set()
        self._trailing_active[pid] = False
        self._highest_since_entry[pid] = position.entry_price
        self._lowest_since_entry[pid] = position.entry_price

    def remove_position(self, position_id: str) -> Position | None:
        """Remove a position from tracking."""
        pos = self._positions.pop(position_id, None)
        self._tp_hit.pop(position_id, None)
        self._trailing_active.pop(position_id, None)
        self._highest_since_entry.pop(position_id, None)
        self._lowest_since_entry.pop(position_id, None)
        return pos

    def check_price(self, symbol: str, current_price: float) -> list[PositionEvent]:
        """Check all positions for a symbol against current price.

        Returns list of events (SL hit, TP hit, trailing stop) that need action.
        """
        events: list[PositionEvent] = []

        for pid, pos in list(self._positions.items()):
            if pos.symbol != symbol:
                continue

            # Update tracking
            pos.current_price = current_price
            self._highest_since_entry[pid] = max(
                self._highest_since_entry.get(pid, current_price), current_price
            )
            self._lowest_since_entry[pid] = min(
                self._lowest_since_entry.get(pid, current_price), current_price
            )

            # Update unrealized P&L
            pos.unrealized_pnl = self._calc_pnl(pos, current_price, pos.remaining_qty)

            # Check stop loss
            sl_event = self._check_stop_loss(pid, pos, current_price)
            if sl_event is not None:
                events.append(sl_event)
                continue  # SL closes everything, skip TP checks

            # Check trailing stop (if active)
            ts_event = self._check_trailing_stop(pid, pos, current_price)
            if ts_event is not None:
                events.append(ts_event)
                continue

            # Check take profits
            tp_events = self._check_take_profits(pid, pos, current_price)
            events.extend(tp_events)

        return events

    def is_trailing_active(self, position_id: str) -> bool:
        """Check if trailing stop is active for a position."""
        return self._trailing_active.get(position_id, False)

    def get_tp_hit(self, position_id: str) -> set[str]:
        """Return set of hit TP levels for a position."""
        return set(self._tp_hit.get(position_id, set()))

    def _check_stop_loss(
        self, pid: str, pos: Position, price: float,
    ) -> PositionEvent | None:
        """Check if stop loss was hit."""
        hit = False
        if pos.direction == Direction.LONG and price <= pos.stop_loss:
            hit = True
        elif pos.direction == Direction.SHORT and price >= pos.stop_loss:
            hit = True

        if hit:
            return PositionEvent(
                event_type="close",
                position_id=pid,
                symbol=pos.symbol,
                close_qty=pos.remaining_qty,
                close_price=pos.stop_loss,
                reason=CloseReason.SL_HIT,
            )
        return None

    def _check_trailing_stop(
        self, pid: str, pos: Position, price: float,
    ) -> PositionEvent | None:
        """Check trailing stop (only if active after TP2)."""
        if not self._trailing_active.get(pid, False):
            return None

        callback = TRAILING_STOP_CALLBACK_PCT

        if pos.direction == Direction.LONG:
            highest = self._highest_since_entry[pid]
            trailing_sl = highest * (1 - callback)
            if price <= trailing_sl:
                return PositionEvent(
                    event_type="close",
                    position_id=pid,
                    symbol=pos.symbol,
                    close_qty=pos.remaining_qty,
                    close_price=price,
                    reason=CloseReason.TRAILING_STOP,
                    data={"trailing_sl": trailing_sl, "highest": highest},
                )
        else:
            lowest = self._lowest_since_entry[pid]
            trailing_sl = lowest * (1 + callback)
            if price >= trailing_sl:
                return PositionEvent(
                    event_type="close",
                    position_id=pid,
                    symbol=pos.symbol,
                    close_qty=pos.remaining_qty,
                    close_price=price,
                    reason=CloseReason.TRAILING_STOP,
                    data={"trailing_sl": trailing_sl, "lowest": lowest},
                )

        return None

    def _check_take_profits(
        self, pid: str, pos: Position, price: float,
    ) -> list[PositionEvent]:
        """Check take profit levels and return events for hits."""
        events: list[PositionEvent] = []
        hit_set = self._tp_hit.get(pid, set())

        for tp in pos.take_profits:
            if tp.level in hit_set:
                continue

            tp_hit = False
            if pos.direction == Direction.LONG and price >= tp.price:
                tp_hit = True
            elif pos.direction == Direction.SHORT and price <= tp.price:
                tp_hit = True

            if not tp_hit:
                continue

            # Calculate close quantity
            close_qty = pos.remaining_qty * (tp.close_pct / 100.0)

            reason_map = {
                "TP1": CloseReason.TP1_HIT,
                "TP2": CloseReason.TP2_HIT,
                "TP3": CloseReason.TP3_HIT,
            }
            reason = reason_map.get(tp.level, CloseReason.TP1_HIT)

            events.append(PositionEvent(
                event_type="partial_close",
                position_id=pid,
                symbol=pos.symbol,
                close_qty=close_qty,
                close_price=tp.price,
                reason=reason,
            ))

            hit_set.add(tp.level)

            # TP1 hit → move SL to breakeven
            if tp.level == "TP1":
                pos.stop_loss = pos.entry_price

            # TP2 hit → activate trailing stop
            if tp.level == "TP2":
                self._trailing_active[pid] = True

        return events

    @staticmethod
    def _calc_pnl(pos: Position, price: float, qty: float) -> float:
        """Calculate P&L for given price and quantity."""
        if pos.direction == Direction.LONG:
            return (price - pos.entry_price) * qty * pos.leverage
        else:
            return (pos.entry_price - price) * qty * pos.leverage
