"""Unit tests for PositionTracker - SL/TP monitoring and lifecycle."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.config.constants import CloseReason, Direction, PositionStatus
from app.core.models import Position, TakeProfit
from app.execution.position_tracker import PositionEvent, PositionTracker


def _make_position(
    direction=Direction.LONG,
    entry=43200.0,
    sl=42900.0,
    qty=0.5,
    leverage=3,
    tp_prices=(43650.0, 44100.0, 44700.0),
) -> Position:
    tps = [
        TakeProfit(level="TP1", price=tp_prices[0], close_pct=50, rr_ratio=1.5),
        TakeProfit(level="TP2", price=tp_prices[1], close_pct=30, rr_ratio=3.0),
        TakeProfit(level="TP3", price=tp_prices[2], close_pct=20, rr_ratio=5.0),
    ]
    return Position(
        signal_id=uuid4(), symbol="BTC/USDT", direction=direction,
        entry_price=entry, current_price=entry,
        quantity=qty, remaining_qty=qty, leverage=leverage,
        stop_loss=sl, take_profits=tps,
    )


class TestAddRemove:
    def test_add_position(self):
        tracker = PositionTracker()
        pos = _make_position()
        tracker.add_position(pos)
        assert tracker.position_count == 1

    def test_remove_position(self):
        tracker = PositionTracker()
        pos = _make_position()
        tracker.add_position(pos)
        removed = tracker.remove_position(str(pos.id))
        assert removed is not None
        assert tracker.position_count == 0

    def test_remove_nonexistent(self):
        tracker = PositionTracker()
        removed = tracker.remove_position("nonexistent")
        assert removed is None


class TestStopLoss:
    def test_sl_hit_long(self):
        tracker = PositionTracker()
        pos = _make_position(direction=Direction.LONG, entry=43200.0, sl=42900.0)
        tracker.add_position(pos)
        events = tracker.check_price("BTC/USDT", 42850.0)
        assert len(events) == 1
        assert events[0].reason == CloseReason.SL_HIT
        assert events[0].close_qty == 0.5

    def test_sl_hit_short(self):
        tracker = PositionTracker()
        pos = _make_position(
            direction=Direction.SHORT, entry=43200.0, sl=43500.0,
            tp_prices=(42750.0, 42300.0, 41700.0),
        )
        tracker.add_position(pos)
        events = tracker.check_price("BTC/USDT", 43600.0)
        assert len(events) == 1
        assert events[0].reason == CloseReason.SL_HIT

    def test_sl_not_hit(self):
        tracker = PositionTracker()
        pos = _make_position(entry=43200.0, sl=42900.0)
        tracker.add_position(pos)
        events = tracker.check_price("BTC/USDT", 43100.0)
        assert len(events) == 0

    def test_sl_exact_hit(self):
        tracker = PositionTracker()
        pos = _make_position(entry=43200.0, sl=42900.0)
        tracker.add_position(pos)
        events = tracker.check_price("BTC/USDT", 42900.0)
        assert len(events) == 1


class TestTakeProfit:
    def test_tp1_hit_long(self):
        tracker = PositionTracker()
        pos = _make_position()
        tracker.add_position(pos)
        events = tracker.check_price("BTC/USDT", 43700.0)
        assert len(events) == 1
        assert events[0].reason == CloseReason.TP1_HIT
        # TP1 closes 50% of remaining
        assert events[0].close_qty == pytest.approx(0.25)

    def test_tp1_moves_sl_to_breakeven(self):
        tracker = PositionTracker()
        pos = _make_position(entry=43200.0, sl=42900.0)
        tracker.add_position(pos)
        tracker.check_price("BTC/USDT", 43700.0)
        # After TP1, SL should be at entry price
        tracked = tracker.positions[str(pos.id)]
        assert tracked.stop_loss == 43200.0

    def test_tp2_activates_trailing(self):
        tracker = PositionTracker()
        pos = _make_position()
        tracker.add_position(pos)
        pid = str(pos.id)
        # Hit TP1 first
        tracker.check_price("BTC/USDT", 43700.0)
        assert not tracker.is_trailing_active(pid)
        # Hit TP2
        tracker.check_price("BTC/USDT", 44200.0)
        assert tracker.is_trailing_active(pid)

    def test_tp3_closes_remaining(self):
        tracker = PositionTracker()
        pos = _make_position()
        tracker.add_position(pos)
        pid = str(pos.id)
        # TP1
        tracker.check_price("BTC/USDT", 43700.0)
        # TP2
        tracker.check_price("BTC/USDT", 44200.0)
        # TP3
        events = tracker.check_price("BTC/USDT", 44800.0)
        tp3_events = [e for e in events if e.reason == CloseReason.TP3_HIT]
        assert len(tp3_events) == 1

    def test_tp_not_hit_twice(self):
        tracker = PositionTracker()
        pos = _make_position()
        tracker.add_position(pos)
        tracker.check_price("BTC/USDT", 43700.0)  # TP1 hit
        events = tracker.check_price("BTC/USDT", 43700.0)  # Same price again
        tp1_events = [e for e in events if e.reason == CloseReason.TP1_HIT]
        assert len(tp1_events) == 0  # Already hit

    def test_get_tp_hit(self):
        tracker = PositionTracker()
        pos = _make_position()
        tracker.add_position(pos)
        pid = str(pos.id)
        tracker.check_price("BTC/USDT", 43700.0)
        assert "TP1" in tracker.get_tp_hit(pid)


class TestTrailingStop:
    def test_trailing_triggers_long(self):
        tracker = PositionTracker()
        pos = _make_position()
        tracker.add_position(pos)
        pid = str(pos.id)
        # Hit TP1 and TP2 to activate trailing
        tracker.check_price("BTC/USDT", 43700.0)
        tracker.check_price("BTC/USDT", 44200.0)
        # Price goes up to set high watermark
        tracker.check_price("BTC/USDT", 45000.0)
        # Price drops 0.5%+ from 45000 = 44775
        events = tracker.check_price("BTC/USDT", 44700.0)
        trailing_events = [e for e in events if e.reason == CloseReason.TRAILING_STOP]
        assert len(trailing_events) == 1

    def test_trailing_triggers_short(self):
        tracker = PositionTracker()
        pos = _make_position(
            direction=Direction.SHORT, entry=43200.0, sl=43500.0,
            tp_prices=(42750.0, 42300.0, 41700.0),
        )
        tracker.add_position(pos)
        pid = str(pos.id)
        # Hit TP1 and TP2
        tracker.check_price("BTC/USDT", 42700.0)
        tracker.check_price("BTC/USDT", 42200.0)
        # Price drops more (sets low watermark)
        tracker.check_price("BTC/USDT", 41500.0)
        # Price bounces up 0.5%+ from 41500 = 41707.5
        events = tracker.check_price("BTC/USDT", 41750.0)
        trailing_events = [e for e in events if e.reason == CloseReason.TRAILING_STOP]
        assert len(trailing_events) == 1

    def test_trailing_not_active_before_tp2(self):
        tracker = PositionTracker()
        pos = _make_position()
        tracker.add_position(pos)
        tracker.check_price("BTC/USDT", 43700.0)  # Only TP1
        # Big drop - should trigger SL not trailing
        events = tracker.check_price("BTC/USDT", 42800.0)
        trailing_events = [e for e in events if e.reason == CloseReason.TRAILING_STOP]
        assert len(trailing_events) == 0


class TestPnLCalculation:
    def test_unrealized_pnl_long(self):
        tracker = PositionTracker()
        pos = _make_position(entry=43200.0, qty=0.5, leverage=3)
        tracker.add_position(pos)
        tracker.check_price("BTC/USDT", 43500.0)
        tracked = tracker.positions[str(pos.id)]
        expected = (43500.0 - 43200.0) * 0.5 * 3  # 450
        assert tracked.unrealized_pnl == pytest.approx(expected)

    def test_unrealized_pnl_short(self):
        tracker = PositionTracker()
        pos = _make_position(
            direction=Direction.SHORT, entry=43200.0, sl=43500.0, qty=0.5, leverage=3,
            tp_prices=(42750.0, 42300.0, 41700.0),
        )
        tracker.add_position(pos)
        tracker.check_price("BTC/USDT", 43000.0)
        tracked = tracker.positions[str(pos.id)]
        expected = (43200.0 - 43000.0) * 0.5 * 3  # 300
        assert tracked.unrealized_pnl == pytest.approx(expected)


class TestMultiplePositions:
    def test_only_matching_symbol_checked(self):
        tracker = PositionTracker()
        btc = _make_position()
        eth = Position(
            signal_id=uuid4(), symbol="ETH/USDT", direction=Direction.LONG,
            entry_price=2500.0, current_price=2500.0,
            quantity=1.0, remaining_qty=1.0, leverage=3,
            stop_loss=2400.0, take_profits=[],
        )
        tracker.add_position(btc)
        tracker.add_position(eth)
        # Only BTC price checked
        events = tracker.check_price("BTC/USDT", 42800.0)  # SL for BTC
        assert len(events) == 1
        assert events[0].symbol == "BTC/USDT"
        assert tracker.position_count == 2  # ETH untouched


class TestPositionEvent:
    def test_event_repr(self):
        evt = PositionEvent(
            event_type="close", position_id="abc",
            symbol="BTC/USDT", reason="SL_HIT",
        )
        assert "SL_HIT" in repr(evt)
