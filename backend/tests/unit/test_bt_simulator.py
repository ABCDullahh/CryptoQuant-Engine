"""Tests for backtesting trade simulator."""

from __future__ import annotations

import pytest

from app.backtesting.simulator import SimPosition, SimTrade, TradeSimulator
from app.config.constants import CloseReason, Direction


@pytest.fixture
def sim():
    return TradeSimulator(initial_balance=10000.0, slippage_bps=0, fee_rate=0.0004)


@pytest.fixture
def sim_no_cost():
    return TradeSimulator(initial_balance=100000.0, slippage_bps=0, fee_rate=0)


class TestInit:
    def test_initial_state(self, sim):
        assert sim.balance == 10000.0
        assert len(sim.positions) == 0
        assert len(sim.closed_trades) == 0

    def test_reset(self, sim):
        sim.balance = 5000
        sim.reset()
        assert sim.balance == 10000.0
        assert len(sim.equity_history) == 1


class TestOpenPosition:
    def test_open_long(self, sim_no_cost):
        pos = sim_no_cost.open_position("BTC/USDT", Direction.LONG, 40000, 0.1, 39000)
        assert pos is not None
        assert pos.direction == Direction.LONG
        assert pos.entry_price == 40000.0
        assert pos.quantity == 0.1
        assert pos.remaining_qty == 0.1
        assert pos.stop_loss == 39000.0

    def test_open_with_tps(self, sim_no_cost):
        tps = [(41000, 50), (42000, 30), (43000, 20)]
        pos = sim_no_cost.open_position("BTC/USDT", Direction.LONG, 40000, 0.1, 39000, tps)
        assert len(pos.take_profits) == 3

    def test_insufficient_balance(self):
        small_sim = TradeSimulator(initial_balance=1000.0, slippage_bps=0, fee_rate=0)
        pos = small_sim.open_position("BTC/USDT", Direction.LONG, 40000, 1.0, 39000)
        assert pos is None  # 40000 * 1.0 > 1000

    def test_fees_deducted(self, sim):
        pos = sim.open_position("BTC/USDT", Direction.LONG, 40000, 0.1, 39000)
        assert pos is not None
        expected_fee = 40000 * 0.1 * 0.0004  # 1.6
        assert sim.balance < 10000.0
        assert pos.fees == pytest.approx(expected_fee)


class TestSLHit:
    def test_long_sl_hit(self, sim_no_cost):
        sim_no_cost.open_position("BTC/USDT", Direction.LONG, 40000, 0.1, 39000)
        trades = sim_no_cost.process_candle("BTC/USDT", 40100, 38900, 39000, time_idx=1)
        assert len(trades) == 1
        assert trades[0].close_reason == CloseReason.SL_HIT
        assert trades[0].pnl < 0
        assert len(sim_no_cost.positions) == 0

    def test_short_sl_hit(self, sim_no_cost):
        sim_no_cost.open_position("BTC/USDT", Direction.SHORT, 40000, 0.1, 41000)
        trades = sim_no_cost.process_candle("BTC/USDT", 41100, 39900, 41000, time_idx=1)
        assert len(trades) == 1
        assert trades[0].close_reason == CloseReason.SL_HIT
        assert trades[0].pnl < 0


class TestTPHit:
    def test_long_tp1(self, sim_no_cost):
        tps = [(41000, 50), (42000, 30), (43000, 20)]
        sim_no_cost.open_position("BTC/USDT", Direction.LONG, 40000, 1.0, 39000, tps)
        trades = sim_no_cost.process_candle("BTC/USDT", 41100, 40000, 41000, time_idx=1)
        assert len(trades) == 1
        assert trades[0].quantity == pytest.approx(0.5)  # 50% close
        pos = list(sim_no_cost.positions.values())[0]
        assert pos.stop_loss == pos.entry_price  # SL moved to breakeven

    def test_short_tp1(self, sim_no_cost):
        tps = [(39000, 50), (38000, 30), (37000, 20)]
        sim_no_cost.open_position("BTC/USDT", Direction.SHORT, 40000, 1.0, 41000, tps)
        trades = sim_no_cost.process_candle("BTC/USDT", 40000, 38900, 39000, time_idx=1)
        assert len(trades) == 1
        assert trades[0].quantity == pytest.approx(0.5)

    def test_tp2_activates_trailing(self, sim_no_cost):
        tps = [(41000, 50), (42000, 30), (43000, 20)]
        sim_no_cost.open_position("BTC/USDT", Direction.LONG, 40000, 1.0, 39000, tps)
        sim_no_cost.process_candle("BTC/USDT", 41100, 40500, 41000, time_idx=1)
        sim_no_cost.process_candle("BTC/USDT", 42100, 41500, 42000, time_idx=2)
        pos = list(sim_no_cost.positions.values())[0]
        assert pos.trailing_active is True


class TestTrailingStop:
    def test_trailing_triggers(self, sim_no_cost):
        sim_no_cost.trailing_callback_pct = 0.01  # 1% callback
        # TP3 at 50000 so it won't be hit before trailing triggers
        tps = [(41000, 50), (42000, 30), (50000, 20)]
        sim_no_cost.open_position("BTC/USDT", Direction.LONG, 40000, 1.0, 39000, tps)
        # TP1
        sim_no_cost.process_candle("BTC/USDT", 41100, 40500, 41000, time_idx=1)
        # TP2 → activates trailing, trailing_high = 42100
        sim_no_cost.process_candle("BTC/USDT", 42100, 41500, 42000, time_idx=2)
        # Price goes up, low stays above trail: high=44000, trail_sl=44000*0.99=43560
        sim_no_cost.process_candle("BTC/USDT", 44000, 43600, 43900, time_idx=3)
        # Price drops below trail_sl (43560)
        trades = sim_no_cost.process_candle("BTC/USDT", 44000, 43500, 43500, time_idx=4)
        trailing = [t for t in trades if t.close_reason == CloseReason.TRAILING_STOP]
        assert len(trailing) == 1


class TestFullLifecycle:
    def test_entry_tp1_sl_breakeven(self, sim_no_cost):
        """Open → TP1 → SL at breakeven."""
        tps = [(41000, 50), (42000, 30), (43000, 20)]
        sim_no_cost.open_position("BTC/USDT", Direction.LONG, 40000, 1.0, 39000, tps, time_idx=0)

        # TP1 hit
        trades1 = sim_no_cost.process_candle("BTC/USDT", 41100, 40500, 41000, time_idx=1)
        assert len(trades1) == 1

        # Price drops to breakeven → SL hit at entry_price (40000)
        trades2 = sim_no_cost.process_candle("BTC/USDT", 40100, 39900, 39900, time_idx=2)
        assert len(trades2) == 1
        assert trades2[0].close_reason == CloseReason.SL_HIT
        assert len(sim_no_cost.positions) == 0

    def test_multiple_positions(self, sim_no_cost):
        sim_no_cost.open_position("BTC/USDT", Direction.LONG, 40000, 0.05, 39000, time_idx=0)
        sim_no_cost.open_position("ETH/USDT", Direction.SHORT, 3000, 1.0, 3100, time_idx=0)
        assert len(sim_no_cost.positions) == 2


class TestPnLAndFees:
    def test_long_profitable(self, sim):
        sim.open_position("BTC/USDT", Direction.LONG, 40000, 0.1, 39000, time_idx=0)
        trades = sim.process_candle("BTC/USDT", 40100, 38900, 39000, time_idx=1)  # SL hit
        assert len(trades) == 1
        assert trades[0].fees > 0
        assert trades[0].net_pnl < trades[0].pnl

    def test_trade_pnl_array(self, sim_no_cost):
        sim_no_cost.open_position("BTC/USDT", Direction.LONG, 40000, 0.1, 39000, time_idx=0)
        sim_no_cost.process_candle("BTC/USDT", 40100, 38900, 39000, time_idx=1)
        pnls = sim_no_cost.get_trade_pnls()
        assert len(pnls) == 1

    def test_equity_curve(self, sim_no_cost):
        sim_no_cost.open_position("BTC/USDT", Direction.LONG, 40000, 0.1, 39000, time_idx=0)
        sim_no_cost.process_candle("BTC/USDT", 40100, 39100, 39500, time_idx=1)
        eq = sim_no_cost.get_equity_curve()
        assert len(eq) == 2  # initial + 1 candle
        assert eq[0] == 100000.0


class TestSlippage:
    def test_long_entry_slippage(self):
        sim = TradeSimulator(initial_balance=100000, slippage_bps=10, fee_rate=0)
        pos = sim.open_position("BTC/USDT", Direction.LONG, 40000, 0.1, 39000)
        assert pos.entry_price > 40000

    def test_short_entry_slippage(self):
        sim = TradeSimulator(initial_balance=100000, slippage_bps=10, fee_rate=0)
        pos = sim.open_position("BTC/USDT", Direction.SHORT, 40000, 0.1, 41000)
        assert pos.entry_price < 40000


class TestSummary:
    def test_summary(self, sim_no_cost):
        sim_no_cost.open_position("BTC/USDT", Direction.LONG, 40000, 0.1, 39000, time_idx=0)
        sim_no_cost.process_candle("BTC/USDT", 40100, 38900, 39000, time_idx=1)
        summary = sim_no_cost.get_summary()
        assert summary["total_trades"] == 1
        assert summary["open_positions"] == 0
        assert summary["initial_balance"] == 100000.0
