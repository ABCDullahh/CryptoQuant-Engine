"""Unit tests for SignalAggregator - calculation methods (SL, TP, position size)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config.constants import (
    ATR_MULTIPLIER_RANGING,
    Direction,
    MIN_SL_PERCENT,
    SignalGrade,
    StopLossType,
)
from app.core.models import Candle, TakeProfit
from app.signals.aggregator import SignalAggregator


def _make_candle(close: float = 43200.0) -> Candle:
    return Candle(
        time=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        symbol="BTC/USDT", timeframe="1h",
        open=43000.0, high=43500.0, low=42900.0, close=close,
        volume=100.0,
    )


class TestComputeGrade:
    def test_grade_a(self):
        assert SignalAggregator._compute_grade(0.80) == SignalGrade.A
        assert SignalAggregator._compute_grade(0.95) == SignalGrade.A
        assert SignalAggregator._compute_grade(1.0) == SignalGrade.A

    def test_grade_b(self):
        assert SignalAggregator._compute_grade(0.60) == SignalGrade.B
        assert SignalAggregator._compute_grade(0.79) == SignalGrade.B

    def test_grade_c(self):
        assert SignalAggregator._compute_grade(0.40) == SignalGrade.C
        assert SignalAggregator._compute_grade(0.59) == SignalGrade.C

    def test_grade_d(self):
        assert SignalAggregator._compute_grade(0.39) == SignalGrade.D
        assert SignalAggregator._compute_grade(0.0) == SignalGrade.D


class TestCalculateStopLoss:
    def test_long_stop_loss(self):
        """Default regime=RANGING uses ATR_MULTIPLIER_RANGING."""
        candles = [_make_candle(close=43200.0)]
        sl, sl_type = SignalAggregator._calculate_stop_loss(
            candles, Direction.LONG, atr=200.0
        )
        expected_distance = max(200.0 * ATR_MULTIPLIER_RANGING, 43200.0 * MIN_SL_PERCENT)
        assert sl == pytest.approx(43200.0 - expected_distance)
        assert sl_type == StopLossType.ATR_BASED

    def test_short_stop_loss(self):
        candles = [_make_candle(close=43200.0)]
        sl, sl_type = SignalAggregator._calculate_stop_loss(
            candles, Direction.SHORT, atr=200.0
        )
        expected_distance = max(200.0 * ATR_MULTIPLIER_RANGING, 43200.0 * MIN_SL_PERCENT)
        assert sl == pytest.approx(43200.0 + expected_distance)
        assert sl_type == StopLossType.ATR_BASED

    def test_small_atr_uses_min_sl_percent(self):
        """When ATR * multiplier < MIN_SL_PERCENT, enforce minimum distance."""
        candles = [_make_candle(close=43200.0)]
        sl, _ = SignalAggregator._calculate_stop_loss(
            candles, Direction.LONG, atr=50.0
        )
        min_distance = 43200.0 * MIN_SL_PERCENT
        atr_distance = 50.0 * ATR_MULTIPLIER_RANGING
        expected_distance = max(atr_distance, min_distance)
        assert sl == pytest.approx(43200.0 - expected_distance)

    def test_large_atr_uses_atr(self):
        """When ATR * multiplier > MIN_SL_PERCENT, use ATR-based distance."""
        candles = [_make_candle(close=43200.0)]
        sl, _ = SignalAggregator._calculate_stop_loss(
            candles, Direction.LONG, atr=500.0
        )
        atr_distance = 500.0 * ATR_MULTIPLIER_RANGING
        assert sl == pytest.approx(43200.0 - atr_distance)


class TestCalculateTakeProfits:
    def test_long_three_tp_levels(self):
        tps = SignalAggregator._calculate_take_profits(
            entry=43200.0, stop_loss=42900.0, direction=Direction.LONG
        )
        assert len(tps) == 3
        assert tps[0].level == "TP1"
        assert tps[1].level == "TP2"
        assert tps[2].level == "TP3"

    def test_long_tp_prices_ascending(self):
        tps = SignalAggregator._calculate_take_profits(
            entry=43200.0, stop_loss=42900.0, direction=Direction.LONG
        )
        assert tps[0].price < tps[1].price < tps[2].price
        assert all(tp.price > 43200.0 for tp in tps)

    def test_short_tp_prices_descending(self):
        tps = SignalAggregator._calculate_take_profits(
            entry=43200.0, stop_loss=43500.0, direction=Direction.SHORT
        )
        assert tps[0].price > tps[1].price > tps[2].price
        assert all(tp.price < 43200.0 for tp in tps)

    def test_tp_close_pcts_sum_to_100(self):
        tps = SignalAggregator._calculate_take_profits(
            entry=43200.0, stop_loss=42900.0, direction=Direction.LONG
        )
        assert sum(tp.close_pct for tp in tps) == 100

    def test_tp_rr_ratios(self):
        tps = SignalAggregator._calculate_take_profits(
            entry=43200.0, stop_loss=42900.0, direction=Direction.LONG
        )
        assert tps[0].rr_ratio == 1.5
        assert tps[1].rr_ratio == 3.0
        assert tps[2].rr_ratio == 5.0

    def test_zero_risk_fallback(self):
        """Entry = stop loss → uses 1% of entry as fallback."""
        tps = SignalAggregator._calculate_take_profits(
            entry=43200.0, stop_loss=43200.0, direction=Direction.LONG
        )
        assert len(tps) == 3
        assert all(tp.price > 43200.0 for tp in tps)


class TestCalculateRiskReward:
    def test_risk_reward_ratios(self):
        tps = [
            TakeProfit(level="TP1", price=43650.0, close_pct=50, rr_ratio=1.5),
            TakeProfit(level="TP2", price=44100.0, close_pct=30, rr_ratio=3.0),
            TakeProfit(level="TP3", price=44700.0, close_pct=20, rr_ratio=5.0),
        ]
        rr = SignalAggregator._calculate_risk_reward(
            entry=43200.0, stop_loss=42900.0, take_profits=tps
        )
        assert rr.rr_tp1 == pytest.approx(1.5)
        assert rr.rr_tp2 == pytest.approx(3.0)
        assert rr.rr_tp3 == pytest.approx(5.0)

    def test_weighted_rr(self):
        tps = [
            TakeProfit(level="TP1", price=43650.0, close_pct=50, rr_ratio=1.5),
            TakeProfit(level="TP2", price=44100.0, close_pct=30, rr_ratio=3.0),
            TakeProfit(level="TP3", price=44700.0, close_pct=20, rr_ratio=5.0),
        ]
        rr = SignalAggregator._calculate_risk_reward(
            entry=43200.0, stop_loss=42900.0, take_profits=tps
        )
        # weighted = 1.5*0.5 + 3.0*0.3 + 5.0*0.2 = 0.75 + 0.9 + 1.0 = 2.65
        assert rr.weighted_rr == pytest.approx(2.65)


class TestCalculatePositionSize:
    def test_basic_position_size(self):
        ps = SignalAggregator._calculate_position_size(
            entry=43200.0, stop_loss=42900.0,
            portfolio_balance=10000.0, risk_pct=0.02,
        )
        assert ps.risk_pct == 0.02
        assert ps.quantity > 0
        assert ps.notional == pytest.approx(ps.quantity * 43200.0)
        # Leverage capped at MAX_LEVERAGE, margin capped per trade
        assert ps.leverage >= 1
        assert ps.leverage <= 10

    def test_leverage_calculation(self):
        ps = SignalAggregator._calculate_position_size(
            entry=43200.0, stop_loss=42900.0,
            portfolio_balance=10000.0, risk_pct=0.02,
        )
        assert ps.leverage >= 1

    def test_zero_risk_fallback(self):
        ps = SignalAggregator._calculate_position_size(
            entry=43200.0, stop_loss=43200.0,
            portfolio_balance=10000.0, risk_pct=0.02,
        )
        assert ps.quantity > 0

    def test_small_balance(self):
        ps = SignalAggregator._calculate_position_size(
            entry=43200.0, stop_loss=42900.0,
            portfolio_balance=100.0, risk_pct=0.02,
        )
        assert ps.quantity > 0
        # Margin capped: balance/MAX_OPEN_POSITIONS*0.95
        assert ps.margin <= 100.0

    def test_margin_capped_per_trade(self):
        """Margin per trade is capped at balance/MAX_OPEN_POSITIONS*0.95."""
        from app.config.constants import MAX_OPEN_POSITIONS
        ps = SignalAggregator._calculate_position_size(
            entry=43200.0, stop_loss=42900.0,
            portfolio_balance=10000.0, risk_pct=0.02,
        )
        max_margin = 10000.0 / MAX_OPEN_POSITIONS * 0.95
        assert ps.margin <= max_margin + 0.01
