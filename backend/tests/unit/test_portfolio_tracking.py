"""Unit tests for PortfolioRiskManager - P&L tracking, position management."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.config.constants import Direction
from app.core.models import Position, PortfolioState
from app.risk.portfolio import PortfolioRiskManager


def _make_position(
    symbol: str = "BTC/USDT",
    direction: Direction = Direction.LONG,
    entry: float = 43200.0,
    stop_loss: float = 42900.0,
    quantity: float = 0.5,
    leverage: int = 3,
    unrealized_pnl: float = 0.0,
) -> Position:
    return Position(
        signal_id=uuid4(),
        symbol=symbol,
        direction=direction,
        entry_price=entry,
        current_price=entry,
        quantity=quantity,
        remaining_qty=quantity,
        leverage=leverage,
        stop_loss=stop_loss,
        unrealized_pnl=unrealized_pnl,
    )


class TestTradeRecording:
    def test_winning_trade_increases_balance(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(500.0)
        assert mgr.balance == 10500.0

    def test_losing_trade_decreases_balance(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(-300.0)
        assert mgr.balance == 9700.0

    def test_consecutive_losses_tracked(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(-100.0)
        assert mgr.consecutive_losses == 1
        mgr.record_trade_result(-200.0)
        assert mgr.consecutive_losses == 2
        mgr.record_trade_result(-50.0)
        assert mgr.consecutive_losses == 3

    def test_win_resets_consecutive_losses(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(-100.0)
        mgr.record_trade_result(-200.0)
        assert mgr.consecutive_losses == 2
        mgr.record_trade_result(50.0)
        assert mgr.consecutive_losses == 0

    def test_daily_pnl_accumulates(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(200.0)
        mgr.record_trade_result(-100.0)
        mgr.record_trade_result(300.0)
        # daily_pnl = 200 - 100 + 300 = 400
        assert mgr.daily_loss_pct() == 0.0  # Net positive

    def test_peak_equity_updates_on_profit(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(500.0)
        assert mgr.peak_equity == 10500.0
        mgr.record_trade_result(-200.0)
        assert mgr.peak_equity == 10500.0  # Doesn't decrease


class TestPositionManagement:
    def test_add_position(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        pos = _make_position()
        mgr.add_position(pos)
        assert len(mgr.open_positions) == 1

    def test_remove_position(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        pos = _make_position()
        mgr.add_position(pos)
        removed = mgr.remove_position(pos.id)
        assert removed is not None
        assert len(mgr.open_positions) == 0

    def test_remove_nonexistent_returns_none(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        result = mgr.remove_position(uuid4())
        assert result is None


class TestGetState:
    def test_state_snapshot(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        pos = _make_position(unrealized_pnl=150.0)
        mgr.add_position(pos)
        mgr.record_trade_result(-200.0)

        state = mgr.get_state()
        assert isinstance(state, PortfolioState)
        assert state.balance == 9800.0
        assert state.open_positions == 1
        assert state.unrealized_pnl == 150.0
        assert state.margin_used > 0
        assert state.consecutive_losses == 1

    def test_state_margin_calculation(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        pos = _make_position(entry=43200.0, quantity=0.5, leverage=3)
        mgr.add_position(pos)
        state = mgr.get_state()
        # margin = 0.5 * 43200 / 3 = 7200
        assert state.margin_used == pytest.approx(7200.0)
        assert state.margin_available == pytest.approx(10000.0 - 7200.0)


class TestUpdateEquity:
    def test_equity_increases_with_unrealized(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.update_equity(500.0)
        assert mgr.equity == 10500.0

    def test_peak_updates_via_equity(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.update_equity(1000.0)
        assert mgr.peak_equity == 11000.0

    def test_drawdown_via_equity(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.update_equity(1000.0)  # Peak = 11000
        mgr.update_equity(-500.0)  # Equity = 9500
        assert mgr.calculate_drawdown() == pytest.approx(1500.0 / 11000.0)


class TestRemainingHeatCapacity:
    def test_full_capacity_no_positions(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        assert mgr.remaining_heat_capacity() == pytest.approx(0.20)

    def test_reduced_capacity_with_positions(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.add_position(_make_position(entry=43200.0, stop_loss=42900.0, quantity=0.5))
        heat = mgr.calculate_heat()
        remaining = mgr.remaining_heat_capacity()
        assert remaining == pytest.approx(0.20 - heat)

    def test_zero_capacity_when_full(self):
        mgr = PortfolioRiskManager(initial_balance=1000.0, max_heat=0.01)
        mgr.add_position(_make_position(quantity=0.5))
        assert mgr.remaining_heat_capacity() == 0.0
