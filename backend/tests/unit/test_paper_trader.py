"""Unit tests for PaperTrader - simulated execution."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.config.constants import (
    Direction,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionStatus,
)
from app.core.models import OrderIntent, TakeProfit
from app.execution.paper_trader import PaperTrader


def _make_order(
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    price=43200.0,
    quantity=0.5,
    leverage=3,
) -> OrderIntent:
    return OrderIntent(
        signal_id=uuid4(),
        symbol="BTC/USDT",
        side=side,
        order_type=order_type,
        price=price,
        quantity=quantity,
        stop_loss=42900.0,
        take_profits=[
            TakeProfit(level="TP1", price=43650.0, close_pct=50, rr_ratio=1.5),
        ],
        leverage=leverage,
    )


class TestExecuteOrder:
    def test_market_order_fills(self):
        pt = PaperTrader(initial_balance=100000.0)
        order = _make_order()
        result = pt.execute_order(order, current_price=43200.0)
        assert result.success is True
        assert result.status == OrderStatus.FILLED
        assert result.filled_quantity == 0.5
        assert result.fees > 0

    def test_limit_order_fills(self):
        pt = PaperTrader(initial_balance=100000.0)
        order = _make_order(order_type=OrderType.LIMIT)
        result = pt.execute_order(order)
        assert result.success is True
        assert result.filled_price is not None

    def test_insufficient_balance_rejected(self):
        pt = PaperTrader(initial_balance=100.0)
        order = _make_order(quantity=1.0)
        result = pt.execute_order(order, current_price=43200.0)
        assert result.success is False
        assert result.status == OrderStatus.REJECTED

    def test_slippage_applied_buy(self):
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=10.0)
        order = _make_order(side=OrderSide.BUY)
        result = pt.execute_order(order, current_price=43200.0)
        assert result.filled_price > 43200.0  # Buy slippage = higher

    def test_slippage_applied_sell(self):
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=10.0)
        order = _make_order(side=OrderSide.SELL)
        result = pt.execute_order(order, current_price=43200.0)
        assert result.filled_price < 43200.0  # Sell slippage = lower

    def test_position_created(self):
        pt = PaperTrader(initial_balance=100000.0)
        order = _make_order()
        pt.execute_order(order, current_price=43200.0)
        assert len(pt.open_positions) == 1

    def test_trade_count_increments(self):
        pt = PaperTrader(initial_balance=100000.0)
        pt.execute_order(_make_order(), current_price=43200.0)
        pt.execute_order(_make_order(), current_price=43200.0)
        assert pt.trade_count == 2

    def test_exchange_order_id_format(self):
        pt = PaperTrader(initial_balance=100000.0)
        result = pt.execute_order(_make_order(), current_price=43200.0)
        assert result.exchange_order_id.startswith("PAPER-")


class TestUpdatePrice:
    def test_updates_unrealized_pnl(self):
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=0)
        order = _make_order()
        pt.execute_order(order, current_price=43200.0)
        pt.update_price("BTC/USDT", 43500.0)
        pos = list(pt.open_positions.values())[0]
        assert pos.unrealized_pnl > 0  # Price went up for LONG

    def test_short_pnl_positive_on_drop(self):
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=0)
        order = _make_order(side=OrderSide.SELL)
        pt.execute_order(order, current_price=43200.0)
        pt.update_price("BTC/USDT", 43000.0)
        pos = list(pt.open_positions.values())[0]
        assert pos.unrealized_pnl > 0  # Price dropped for SHORT


class TestClosePosition:
    def test_full_close(self):
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=0, fee_rate=0)
        order = _make_order(leverage=1)
        pt.execute_order(order, current_price=43200.0)
        pos_id = list(pt.open_positions.keys())[0]
        pnl = pt.close_position(pos_id, close_price=43500.0)
        assert pnl == pytest.approx(300.0 * 0.5)  # (43500-43200)*0.5
        assert len(pt.open_positions) == 0
        assert len(pt.closed_positions) == 1

    def test_partial_close(self):
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=0, fee_rate=0)
        order = _make_order(leverage=1)
        pt.execute_order(order, current_price=43200.0)
        pos_id = list(pt.open_positions.keys())[0]
        pt.close_position(pos_id, close_price=43500.0, close_qty=0.25)
        pos = pt.open_positions[pos_id]
        assert pos.remaining_qty == pytest.approx(0.25)
        assert pos.status == PositionStatus.REDUCING

    def test_close_reason_recorded(self):
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=0, fee_rate=0)
        order = _make_order()
        pt.execute_order(order, current_price=43200.0)
        pos_id = list(pt.open_positions.keys())[0]
        pt.close_position(pos_id, close_price=42900.0, reason="SL_HIT")
        closed = pt.closed_positions[0]
        assert closed.close_reason == "SL_HIT"
        assert closed.status == PositionStatus.CLOSED

    def test_leverage_amplifies_pnl(self):
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=0, fee_rate=0)
        order = _make_order(leverage=3)
        pt.execute_order(order, current_price=43200.0)
        pos_id = list(pt.open_positions.keys())[0]
        pnl = pt.close_position(pos_id, close_price=43500.0)
        # (43500-43200)*0.5*3 = 450
        assert pnl == pytest.approx(450.0)

    def test_close_with_fees(self):
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=0, fee_rate=0.0004)
        order = _make_order(leverage=1)
        pt.execute_order(order, current_price=43200.0)
        pos_id = list(pt.open_positions.keys())[0]
        pnl = pt.close_position(pos_id, close_price=43500.0)
        # Raw pnl = 150, close fees = 0.5*43500*0.0004 = 8.7
        assert pnl < 150.0  # Fees reduce P&L


class TestEquityAndPnL:
    def test_equity_includes_unrealized(self):
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=0, fee_rate=0)
        order = _make_order(leverage=1)
        pt.execute_order(order, current_price=43200.0)
        pt.update_price("BTC/USDT", 43400.0)
        assert pt.equity > pt.balance

    def test_total_pnl_after_close(self):
        pt = PaperTrader(initial_balance=100000.0, slippage_bps=0, fee_rate=0)
        order = _make_order(leverage=1)
        pt.execute_order(order, current_price=43200.0)
        pos_id = list(pt.open_positions.keys())[0]
        pt.close_position(pos_id, close_price=43500.0)
        assert pt.get_total_pnl() == pytest.approx(150.0)


class TestReset:
    def test_reset_clears_state(self):
        pt = PaperTrader(initial_balance=10000.0, slippage_bps=0, fee_rate=0)
        order = _make_order(leverage=1)
        pt.execute_order(order, current_price=43200.0)
        pt.reset()
        assert pt.balance == 10000.0
        assert len(pt.open_positions) == 0
        assert pt.trade_count == 0
