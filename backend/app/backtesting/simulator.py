"""Trade simulator for backtesting — handles order fills, fees, position lifecycle.

Simulates realistic trade execution during backtests with slippage,
commission/fee calculations, and position P&L tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import numpy as np

from app.config.constants import (
    CloseReason,
    Direction,
    OrderSide,
    TP1_CLOSE_PCT,
    TP2_CLOSE_PCT,
    TRAILING_STOP_CALLBACK_PCT,
)


@dataclass
class SimTrade:
    """A completed simulated trade."""

    id: str = ""
    symbol: str = ""
    direction: Direction = Direction.LONG
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: float = 0.0
    entry_time: int = 0  # Index into candle array
    exit_time: int = 0
    pnl: float = 0.0
    fees: float = 0.0
    net_pnl: float = 0.0
    close_reason: str = ""
    holding_periods: int = 0

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid4())[:8]


@dataclass
class SimPosition:
    """An open simulated position during backtest."""

    id: str = ""
    symbol: str = ""
    direction: Direction = Direction.LONG
    entry_price: float = 0.0
    quantity: float = 0.0
    remaining_qty: float = 0.0
    stop_loss: float = 0.0
    original_stop_loss: float = 0.0
    take_profits: list = field(default_factory=list)  # list of (price, close_pct)
    tp_hit: set = field(default_factory=set)
    entry_time: int = 0
    fees: float = 0.0
    trailing_active: bool = False
    trailing_high: float = 0.0
    trailing_low: float = float("inf")

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid4())[:8]
        if self.remaining_qty == 0:
            self.remaining_qty = self.quantity


class TradeSimulator:
    """Simulates trade execution with realistic slippage and fees.

    Handles:
    - Order filling with slippage
    - Fee calculation (taker fees for market orders)
    - Position lifecycle: entry → TP1/TP2/TP3 partial closes → SL/trailing exit
    - P&L tracking per position
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        slippage_bps: float = 5.0,
        fee_rate: float = 0.0004,
        trailing_callback_pct: float = TRAILING_STOP_CALLBACK_PCT,
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.slippage_bps = slippage_bps
        self.fee_rate = fee_rate
        self.trailing_callback_pct = trailing_callback_pct

        self.positions: dict[str, SimPosition] = {}
        self.closed_trades: list[SimTrade] = []
        self.equity_history: list[float] = [initial_balance]

    @property
    def equity(self) -> float:
        """Current equity including unrealized P&L."""
        unrealized = 0.0
        for pos in self.positions.values():
            if pos.direction == Direction.LONG:
                unrealized += (self.last_prices.get(pos.symbol, pos.entry_price) - pos.entry_price) * pos.remaining_qty
            else:
                unrealized += (pos.entry_price - self.last_prices.get(pos.symbol, pos.entry_price)) * pos.remaining_qty
        return self.balance + unrealized

    def reset(self) -> None:
        """Reset simulator to initial state."""
        self.balance = self.initial_balance
        self.positions.clear()
        self.closed_trades.clear()
        self.equity_history = [self.initial_balance]
        self.last_prices: dict[str, float] = {}

    def open_position(
        self,
        symbol: str,
        direction: Direction,
        price: float,
        quantity: float,
        stop_loss: float,
        take_profits: list[tuple[float, int]] | None = None,
        time_idx: int = 0,
    ) -> SimPosition | None:
        """Open a new simulated position.

        Args:
            symbol: Trading pair.
            direction: LONG or SHORT.
            price: Raw entry price (slippage applied internally).
            quantity: Position size.
            stop_loss: Stop loss price.
            take_profits: List of (price, close_pct) tuples.
            time_idx: Current candle index for timing.

        Returns:
            SimPosition if successful, None if insufficient balance.
        """
        fill_price = self._apply_slippage(price, direction)
        notional = fill_price * quantity
        fees = notional * self.fee_rate
        margin = notional  # Simplified: full notional

        if margin + fees > self.balance:
            return None

        self.balance -= fees
        tps = take_profits or []

        pos = SimPosition(
            symbol=symbol,
            direction=direction,
            entry_price=fill_price,
            quantity=quantity,
            remaining_qty=quantity,
            stop_loss=stop_loss,
            original_stop_loss=stop_loss,
            take_profits=tps,
            entry_time=time_idx,
            fees=fees,
        )
        self.positions[pos.id] = pos
        return pos

    def process_candle(
        self,
        symbol: str,
        high: float,
        low: float,
        close: float,
        time_idx: int = 0,
    ) -> list[SimTrade]:
        """Process a candle and check SL/TP for all positions on this symbol.

        Returns list of trades closed during this candle.
        """
        self.last_prices = getattr(self, "last_prices", {})
        self.last_prices[symbol] = close
        closed: list[SimTrade] = []

        positions_to_check = [
            p for p in self.positions.values() if p.symbol == symbol
        ]

        for pos in positions_to_check:
            trades = self._check_position(pos, high, low, close, time_idx)
            closed.extend(trades)

        # Update equity history
        self.equity_history.append(self.equity)
        return closed

    def _check_position(
        self,
        pos: SimPosition,
        high: float,
        low: float,
        close: float,
        time_idx: int,
    ) -> list[SimTrade]:
        """Check SL/TP hits for a single position."""
        closed: list[SimTrade] = []

        if pos.direction == Direction.LONG:
            # Check SL first (worst case)
            if low <= pos.stop_loss:
                trade = self._close_position(pos, pos.stop_loss, time_idx, CloseReason.SL_HIT)
                closed.append(trade)
                return closed

            # Check trailing stop
            if pos.trailing_active:
                pos.trailing_high = max(pos.trailing_high, high)
                trail_sl = pos.trailing_high * (1 - self.trailing_callback_pct)
                if low <= trail_sl:
                    trade = self._close_position(pos, trail_sl, time_idx, CloseReason.TRAILING_STOP)
                    closed.append(trade)
                    return closed

            # Check TPs
            for tp_price, tp_pct in pos.take_profits:
                tp_key = f"{tp_price}"
                if tp_key not in pos.tp_hit and high >= tp_price:
                    pos.tp_hit.add(tp_key)
                    close_qty = pos.quantity * tp_pct / 100
                    close_qty = min(close_qty, pos.remaining_qty)
                    if close_qty > 0:
                        trade = self._partial_close(pos, tp_price, close_qty, time_idx, tp_pct)
                        closed.append(trade)

                    # After TP1: move SL to breakeven
                    if tp_pct == TP1_CLOSE_PCT:
                        pos.stop_loss = pos.entry_price

                    # After TP2: activate trailing
                    if tp_pct == TP2_CLOSE_PCT:
                        pos.trailing_active = True
                        pos.trailing_high = high

        else:  # SHORT
            if high >= pos.stop_loss:
                trade = self._close_position(pos, pos.stop_loss, time_idx, CloseReason.SL_HIT)
                closed.append(trade)
                return closed

            if pos.trailing_active:
                pos.trailing_low = min(pos.trailing_low, low)
                trail_sl = pos.trailing_low * (1 + self.trailing_callback_pct)
                if high >= trail_sl:
                    trade = self._close_position(pos, trail_sl, time_idx, CloseReason.TRAILING_STOP)
                    closed.append(trade)
                    return closed

            for tp_price, tp_pct in pos.take_profits:
                tp_key = f"{tp_price}"
                if tp_key not in pos.tp_hit and low <= tp_price:
                    pos.tp_hit.add(tp_key)
                    close_qty = pos.quantity * tp_pct / 100
                    close_qty = min(close_qty, pos.remaining_qty)
                    if close_qty > 0:
                        trade = self._partial_close(pos, tp_price, close_qty, time_idx, tp_pct)
                        closed.append(trade)

                    if tp_pct == TP1_CLOSE_PCT:
                        pos.stop_loss = pos.entry_price
                    if tp_pct == TP2_CLOSE_PCT:
                        pos.trailing_active = True
                        pos.trailing_low = low

        # If remaining qty is zero, clean up
        if pos.remaining_qty <= 1e-10 and pos.id in self.positions:
            del self.positions[pos.id]

        return closed

    def _close_position(
        self,
        pos: SimPosition,
        exit_price: float,
        time_idx: int,
        reason: str,
    ) -> SimTrade:
        """Fully close a position."""
        exit_price = self._apply_slippage(exit_price, pos.direction, is_exit=True)
        qty = pos.remaining_qty
        fees = exit_price * qty * self.fee_rate

        if pos.direction == Direction.LONG:
            pnl = (exit_price - pos.entry_price) * qty
        else:
            pnl = (pos.entry_price - exit_price) * qty

        net_pnl = pnl - fees - pos.fees
        self.balance += pnl - fees

        trade = SimTrade(
            symbol=pos.symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            quantity=qty,
            entry_time=pos.entry_time,
            exit_time=time_idx,
            pnl=pnl,
            fees=fees + pos.fees,
            net_pnl=net_pnl,
            close_reason=reason,
            holding_periods=time_idx - pos.entry_time,
        )
        self.closed_trades.append(trade)
        pos.remaining_qty = 0

        if pos.id in self.positions:
            del self.positions[pos.id]

        return trade

    def _partial_close(
        self,
        pos: SimPosition,
        exit_price: float,
        close_qty: float,
        time_idx: int,
        tp_pct: int,
    ) -> SimTrade:
        """Partially close a position at TP level."""
        exit_price = self._apply_slippage(exit_price, pos.direction, is_exit=True)
        fees = exit_price * close_qty * self.fee_rate

        if pos.direction == Direction.LONG:
            pnl = (exit_price - pos.entry_price) * close_qty
        else:
            pnl = (pos.entry_price - exit_price) * close_qty

        # Proportional entry fees
        entry_fee_share = pos.fees * (close_qty / pos.quantity)
        net_pnl = pnl - fees - entry_fee_share
        self.balance += pnl - fees
        pos.remaining_qty -= close_qty

        reason = f"TP_{tp_pct}PCT"
        trade = SimTrade(
            symbol=pos.symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            quantity=close_qty,
            entry_time=pos.entry_time,
            exit_time=time_idx,
            pnl=pnl,
            fees=fees + entry_fee_share,
            net_pnl=net_pnl,
            close_reason=reason,
            holding_periods=time_idx - pos.entry_time,
        )
        self.closed_trades.append(trade)
        return trade

    def _apply_slippage(self, price: float, direction: Direction, is_exit: bool = False) -> float:
        """Apply slippage to fill price."""
        slip = price * self.slippage_bps / 10000

        if direction == Direction.LONG:
            return price + slip if not is_exit else price - slip
        else:  # SHORT
            return price - slip if not is_exit else price + slip

    def get_trade_pnls(self) -> np.ndarray:
        """Get array of net P&L for all closed trades."""
        return np.array([t.net_pnl for t in self.closed_trades])

    def get_trade_durations(self) -> np.ndarray:
        """Get array of holding durations for all closed trades."""
        return np.array([t.holding_periods for t in self.closed_trades])

    def get_equity_curve(self) -> np.ndarray:
        """Get equity curve as numpy array."""
        return np.array(self.equity_history)

    def get_summary(self) -> dict:
        """Get summary statistics."""
        pnls = self.get_trade_pnls()
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.balance,
            "total_trades": len(self.closed_trades),
            "open_positions": len(self.positions),
            "total_pnl": float(np.sum(pnls)) if len(pnls) > 0 else 0.0,
        }
