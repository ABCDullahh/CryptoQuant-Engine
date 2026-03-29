"""Unit tests for OrderManager - order lifecycle management."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.config.constants import (
    Direction,
    MAX_LEVERAGE,
    MAX_OPEN_POSITIONS,
    OrderSide,
    OrderStatus,
    OrderType,
    SignalGrade,
    StopLossType,
)
from app.core.models import (
    CompositeSignal,
    MarketContext,
    OrderIntent,
    PositionSize,
    RiskReward,
    TakeProfit,
)
from app.execution.order_manager import OrderManager, OrderValidationError


def _make_signal(
    direction=Direction.LONG,
    grade=SignalGrade.B,
    entry=43200.0,
    quantity=0.5,
) -> CompositeSignal:
    return CompositeSignal(
        symbol="BTC/USDT",
        direction=direction,
        grade=grade,
        strength=0.70,
        entry_price=entry,
        entry_zone=(entry - 100, entry + 100),
        stop_loss=entry - 300,
        sl_type=StopLossType.ATR_BASED,
        take_profits=[
            TakeProfit(level="TP1", price=entry + 450, close_pct=50, rr_ratio=1.5),
            TakeProfit(level="TP2", price=entry + 900, close_pct=30, rr_ratio=3.0),
        ],
        risk_reward=RiskReward(rr_tp1=1.5, rr_tp2=3.0, rr_tp3=5.0, weighted_rr=2.65),
        position_size=PositionSize(
            quantity=quantity, notional=quantity * entry,
            margin=quantity * entry / 3,
            risk_amount=200.0, risk_pct=0.02, leverage=3,
        ),
        strategy_scores={"momentum": 0.8},
        market_context=MarketContext(),
    )


class TestSignalToOrder:
    def test_long_signal_creates_buy(self):
        mgr = OrderManager()
        signal = _make_signal(Direction.LONG)
        order = mgr.signal_to_order(signal)
        assert order.side == OrderSide.BUY
        assert order.symbol == "BTC/USDT"
        assert order.quantity == 0.5

    def test_short_signal_creates_sell(self):
        mgr = OrderManager()
        signal = _make_signal(Direction.SHORT)
        order = mgr.signal_to_order(signal)
        assert order.side == OrderSide.SELL

    def test_neutral_raises(self):
        mgr = OrderManager()
        signal = _make_signal(Direction.NEUTRAL)
        with pytest.raises(OrderValidationError):
            mgr.signal_to_order(signal)

    def test_grade_a_uses_market(self):
        mgr = OrderManager()
        signal = _make_signal(grade=SignalGrade.A)
        order = mgr.signal_to_order(signal)
        assert order.order_type == OrderType.MARKET
        assert order.price is None

    def test_grade_b_uses_limit(self):
        mgr = OrderManager()
        signal = _make_signal(grade=SignalGrade.B)
        order = mgr.signal_to_order(signal)
        assert order.order_type == OrderType.LIMIT
        assert order.price == 43200.0

    def test_force_market_override(self):
        mgr = OrderManager()
        signal = _make_signal(grade=SignalGrade.C)
        order = mgr.signal_to_order(signal, use_market=True)
        assert order.order_type == OrderType.MARKET

    def test_paper_mode_flag(self):
        mgr = OrderManager(is_paper=True)
        order = mgr.signal_to_order(_make_signal())
        assert order.is_paper is True

    def test_take_profits_copied(self):
        mgr = OrderManager()
        signal = _make_signal()
        order = mgr.signal_to_order(signal)
        assert len(order.take_profits) == 2
        assert order.take_profits[0].level == "TP1"


class TestValidateOrder:
    def test_valid_order_no_errors(self):
        mgr = OrderManager()
        order = mgr.signal_to_order(_make_signal())
        errors = mgr.validate_order(order, balance=100000.0)
        assert errors == []

    def test_zero_quantity_error(self):
        mgr = OrderManager()
        order = mgr.signal_to_order(_make_signal(quantity=0.5))
        order = order.model_copy(update={"quantity": 0})
        errors = mgr.validate_order(order, balance=100000.0)
        assert any("Quantity" in e for e in errors)

    def test_max_positions_error(self):
        mgr = OrderManager()
        order = mgr.signal_to_order(_make_signal())
        errors = mgr.validate_order(order, balance=100000.0, open_positions=MAX_OPEN_POSITIONS)
        assert any("Max positions" in e for e in errors)

    def test_insufficient_balance_error(self):
        mgr = OrderManager()
        order = mgr.signal_to_order(_make_signal(quantity=1.0))
        errors = mgr.validate_order(order, balance=100.0)
        assert any("Insufficient" in e for e in errors)

    def test_excess_leverage_error(self):
        mgr = OrderManager()
        order = mgr.signal_to_order(_make_signal())
        order = order.model_copy(update={"leverage": MAX_LEVERAGE + 1})
        errors = mgr.validate_order(order, balance=100000.0)
        assert any("Leverage" in e for e in errors)

    def test_market_order_skip_price_check(self):
        mgr = OrderManager()
        signal = _make_signal(grade=SignalGrade.A)
        order = mgr.signal_to_order(signal)
        errors = mgr.validate_order(order, balance=100000.0)
        assert errors == []


class TestOrderLifecycle:
    def test_register_and_complete(self):
        mgr = OrderManager()
        order = mgr.signal_to_order(_make_signal())
        mgr.register_pending(order)
        assert mgr.pending_count == 1

        result = mgr.complete_order(
            str(order.id), filled_price=43200.0, filled_quantity=0.5, fees=8.64,
        )
        assert result.success is True
        assert result.status == OrderStatus.FILLED
        assert result.fees == 8.64
        assert mgr.pending_count == 0
        assert len(mgr.order_history) == 1

    def test_cancel_order(self):
        mgr = OrderManager()
        order = mgr.signal_to_order(_make_signal())
        mgr.register_pending(order)
        result = mgr.cancel_order(str(order.id))
        assert result.success is False
        assert result.status == OrderStatus.CANCELLED
        assert mgr.pending_count == 0

    def test_reject_order(self):
        mgr = OrderManager()
        order = mgr.signal_to_order(_make_signal())
        result = mgr.reject_order(str(order.id), "Insufficient balance")
        assert result.success is False
        assert result.status == OrderStatus.REJECTED


class TestFees:
    def test_taker_fee(self):
        fee = OrderManager.calculate_fees(1.0, 43200.0, is_maker=False)
        assert fee == pytest.approx(43200.0 * 0.0004)

    def test_maker_fee(self):
        fee = OrderManager.calculate_fees(1.0, 43200.0, is_maker=True)
        assert fee == pytest.approx(43200.0 * 0.0002)


class TestCreatePosition:
    def test_position_from_buy_fill(self):
        mgr = OrderManager()
        order = mgr.signal_to_order(_make_signal(Direction.LONG))
        pos = OrderManager.create_position_from_fill(order, 43200.0, 0.5, fees=8.64)
        assert pos.direction == Direction.LONG
        assert pos.entry_price == 43200.0
        assert pos.quantity == 0.5
        assert pos.remaining_qty == 0.5
        assert pos.total_fees == 8.64

    def test_position_from_sell_fill(self):
        mgr = OrderManager()
        order = mgr.signal_to_order(_make_signal(Direction.SHORT))
        pos = OrderManager.create_position_from_fill(order, 43200.0, 0.3)
        assert pos.direction == Direction.SHORT
