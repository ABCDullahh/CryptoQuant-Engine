"""Unit tests for PortfolioRiskManager - heat, drawdown, limits."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.config.constants import (
    MAX_CORRELATED_POSITIONS,
    MAX_DAILY_LOSS,
    MAX_DRAWDOWN,
    MAX_OPEN_POSITIONS,
    MAX_PORTFOLIO_HEAT,
    Direction,
)
from app.core.models import Position
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


class TestCalculateHeat:
    def test_no_positions_zero_heat(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        assert mgr.calculate_heat() == 0.0

    def test_single_position_heat(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        pos = _make_position(entry=43200.0, stop_loss=42900.0, quantity=0.5)
        mgr.add_position(pos)
        # risk = |43200 - 42900| * 0.5 * 3 (leverage) = 450
        # heat = 450 / 10000 = 0.045
        assert mgr.calculate_heat() == pytest.approx(0.045)

    def test_multiple_positions_heat(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.add_position(_make_position(entry=43200.0, stop_loss=42900.0, quantity=0.5))
        mgr.add_position(_make_position(entry=2500.0, stop_loss=2400.0, quantity=1.0))
        # risk1 = 300 * 0.5 * 3 = 450
        # risk2 = 100 * 1.0 * 3 = 300
        # heat = 750 / 10000 = 0.075
        assert mgr.calculate_heat() == pytest.approx(0.075)


class TestCalculateDrawdown:
    def test_no_drawdown_initially(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        assert mgr.calculate_drawdown() == 0.0

    def test_drawdown_after_loss(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(-500.0)
        # peak = 10000, equity = 9500
        # drawdown = 500 / 10000 = 0.05
        assert mgr.calculate_drawdown() == pytest.approx(0.05)

    def test_drawdown_peak_updates(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(1000.0)  # Equity = 11000
        assert mgr.peak_equity == 11000.0
        mgr.record_trade_result(-1500.0)  # Equity = 9500
        assert mgr.calculate_drawdown() == pytest.approx(1500.0 / 11000.0)


class TestDailyWeeklyLoss:
    def test_daily_loss_pct(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(-300.0)
        # daily_loss = 300, balance = 9700 after trade
        assert mgr.daily_loss_pct() == pytest.approx(300.0 / 9700.0)

    def test_weekly_loss_pct(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(-800.0)
        # weekly_loss = 800, balance = 9200 after trade
        assert mgr.weekly_loss_pct() == pytest.approx(800.0 / 9200.0)

    def test_daily_reset(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(-300.0)
        mgr.reset_daily_pnl()
        assert mgr.daily_loss_pct() == 0.0

    def test_weekly_reset(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(-800.0)
        mgr.reset_weekly_pnl()
        assert mgr.weekly_loss_pct() == 0.0

    def test_profit_no_loss(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(500.0)
        assert mgr.daily_loss_pct() == 0.0


class TestCanOpenPosition:
    def test_allowed_when_under_limits(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        allowed, reason = mgr.can_open_position()
        assert allowed is True
        assert reason == ""

    def test_blocked_by_max_positions(self):
        mgr = PortfolioRiskManager(initial_balance=100000.0, max_positions=2)
        mgr.add_position(_make_position())
        mgr.add_position(_make_position())
        allowed, reason = mgr.can_open_position()
        assert allowed is False
        assert "Max positions" in reason

    def test_blocked_by_heat(self):
        mgr = PortfolioRiskManager(initial_balance=1000.0, max_heat=0.01)
        # Risk = 300 * 0.5 = 150, heat = 150/1000 = 0.15 >> 0.01
        mgr.add_position(_make_position(quantity=0.5))
        allowed, reason = mgr.can_open_position()
        assert allowed is False
        assert "heat" in reason.lower()

    def test_blocked_by_drawdown(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(-2000.0)  # 20% drawdown
        allowed, reason = mgr.can_open_position()
        assert allowed is False
        assert "drawdown" in reason.lower()

    def test_blocked_by_daily_loss(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.record_trade_result(-600.0)  # 6% daily loss
        allowed, reason = mgr.can_open_position()
        assert allowed is False
        assert "Daily loss" in reason


class TestCheckCorrelation:
    def test_allowed_under_limit(self):
        mgr = PortfolioRiskManager(initial_balance=10000.0)
        mgr.add_position(_make_position(direction=Direction.LONG))
        allowed, reason = mgr.check_correlation("ETH/USDT", Direction.LONG)
        assert allowed is True

    def test_blocked_at_max_correlated(self):
        mgr = PortfolioRiskManager(initial_balance=100000.0, max_correlated=2)
        mgr.add_position(_make_position(direction=Direction.LONG))
        mgr.add_position(_make_position(direction=Direction.LONG))
        allowed, reason = mgr.check_correlation("SOL/USDT", Direction.LONG)
        assert allowed is False
        assert "correlated" in reason.lower()

    def test_opposite_direction_ok(self):
        mgr = PortfolioRiskManager(initial_balance=100000.0, max_correlated=2)
        mgr.add_position(_make_position(direction=Direction.LONG))
        mgr.add_position(_make_position(direction=Direction.LONG))
        allowed, _ = mgr.check_correlation("ETH/USDT", Direction.SHORT)
        assert allowed is True
