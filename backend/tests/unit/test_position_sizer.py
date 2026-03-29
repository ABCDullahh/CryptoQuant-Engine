"""Unit tests for PositionSizer - all sizing methods."""

from __future__ import annotations

import pytest

from app.config.constants import (
    MAX_LEVERAGE,
    MAX_RISK_PER_TRADE,
    MAX_RISK_PER_TRADE_ABSOLUTE,
    MarketRegime,
)
from app.core.models import PositionSize
from app.risk.position_sizer import PositionSizer


class TestFixedFractional:
    def test_basic_long(self):
        ps = PositionSizer.fixed_fractional(
            entry=43200.0, stop_loss=42900.0, balance=10000.0
        )
        assert ps.risk_amount == pytest.approx(200.0)
        assert ps.risk_pct == MAX_RISK_PER_TRADE
        assert ps.quantity == pytest.approx(200.0 / 300.0)
        assert ps.notional == pytest.approx(ps.quantity * 43200.0)

    def test_basic_short(self):
        ps = PositionSizer.fixed_fractional(
            entry=43200.0, stop_loss=43500.0, balance=10000.0
        )
        assert ps.risk_amount == pytest.approx(200.0)
        assert ps.quantity == pytest.approx(200.0 / 300.0)

    def test_custom_risk_pct(self):
        ps = PositionSizer.fixed_fractional(
            entry=43200.0, stop_loss=42900.0, balance=10000.0, risk_pct=0.01
        )
        assert ps.risk_amount == pytest.approx(100.0)
        assert ps.risk_pct == 0.01

    def test_risk_pct_capped_at_absolute_max(self):
        ps = PositionSizer.fixed_fractional(
            entry=43200.0, stop_loss=42900.0, balance=10000.0, risk_pct=0.10
        )
        assert ps.risk_pct == MAX_RISK_PER_TRADE_ABSOLUTE
        assert ps.risk_amount == pytest.approx(10000.0 * MAX_RISK_PER_TRADE_ABSOLUTE)

    def test_zero_risk_fallback(self):
        ps = PositionSizer.fixed_fractional(
            entry=43200.0, stop_loss=43200.0, balance=10000.0
        )
        assert ps.quantity > 0
        assert ps.risk_amount == pytest.approx(200.0)

    def test_leverage_capped(self):
        ps = PositionSizer.fixed_fractional(
            entry=43200.0, stop_loss=42900.0, balance=10000.0
        )
        assert ps.leverage <= MAX_LEVERAGE
        assert ps.leverage >= 1

    def test_small_balance(self):
        ps = PositionSizer.fixed_fractional(
            entry=43200.0, stop_loss=42900.0, balance=100.0
        )
        assert ps.risk_amount == pytest.approx(2.0)
        assert ps.quantity > 0


class TestVolatilityBased:
    def test_trending_market_wider_stop(self):
        ps_trend = PositionSizer.volatility_based(
            entry=43200.0, atr=200.0, balance=10000.0,
            regime=MarketRegime.TRENDING_UP,
        )
        ps_range = PositionSizer.volatility_based(
            entry=43200.0, atr=200.0, balance=10000.0,
            regime=MarketRegime.RANGING,
        )
        # Trending uses wider stop → smaller position
        assert ps_trend.quantity < ps_range.quantity

    def test_volatile_market_smallest_position(self):
        ps_volatile = PositionSizer.volatility_based(
            entry=43200.0, atr=200.0, balance=10000.0,
            regime=MarketRegime.HIGH_VOLATILITY,
        )
        ps_lowvol = PositionSizer.volatility_based(
            entry=43200.0, atr=200.0, balance=10000.0,
            regime=MarketRegime.LOW_VOLATILITY,
        )
        assert ps_volatile.quantity < ps_lowvol.quantity

    def test_zero_atr_fallback(self):
        ps = PositionSizer.volatility_based(
            entry=43200.0, atr=0.0, balance=10000.0,
        )
        assert ps.quantity > 0

    def test_risk_pct_respected(self):
        ps = PositionSizer.volatility_based(
            entry=43200.0, atr=200.0, balance=10000.0, risk_pct=0.01,
        )
        assert ps.risk_pct == 0.01
        assert ps.risk_amount == pytest.approx(100.0)

    def test_all_regimes_produce_valid_result(self):
        for regime in MarketRegime:
            ps = PositionSizer.volatility_based(
                entry=43200.0, atr=200.0, balance=10000.0, regime=regime,
            )
            assert ps.quantity > 0
            assert ps.leverage >= 1


class TestKellyCriterion:
    def test_positive_edge(self):
        """Win rate 60%, avg win 1.5x avg loss → positive Kelly."""
        ps = PositionSizer.kelly_criterion(
            entry=43200.0, stop_loss=42900.0, balance=10000.0,
            win_rate=0.60, avg_win=450.0, avg_loss=300.0,
        )
        assert ps.quantity > 0
        assert ps.risk_pct > 0

    def test_no_edge(self):
        """Win rate 40%, equal win/loss → zero or negative Kelly."""
        ps = PositionSizer.kelly_criterion(
            entry=43200.0, stop_loss=42900.0, balance=10000.0,
            win_rate=0.40, avg_win=300.0, avg_loss=300.0,
        )
        assert ps.quantity == 0.0
        assert ps.risk_pct == 0.0

    def test_negative_edge(self):
        """Win rate 30%, equal win/loss → zero quantity."""
        ps = PositionSizer.kelly_criterion(
            entry=43200.0, stop_loss=42900.0, balance=10000.0,
            win_rate=0.30, avg_win=300.0, avg_loss=300.0,
        )
        assert ps.quantity == 0.0

    def test_fractional_kelly_reduces_size(self):
        """25% Kelly should be smaller than 50% Kelly."""
        ps_25 = PositionSizer.kelly_criterion(
            entry=43200.0, stop_loss=42900.0, balance=10000.0,
            win_rate=0.52, avg_win=310.0, avg_loss=300.0,
            fraction=0.25,
        )
        ps_50 = PositionSizer.kelly_criterion(
            entry=43200.0, stop_loss=42900.0, balance=10000.0,
            win_rate=0.52, avg_win=310.0, avg_loss=300.0,
            fraction=0.50,
        )
        assert ps_25.risk_amount < ps_50.risk_amount

    def test_kelly_capped_at_absolute_max(self):
        """Even very high Kelly should be capped."""
        ps = PositionSizer.kelly_criterion(
            entry=43200.0, stop_loss=42900.0, balance=10000.0,
            win_rate=0.90, avg_win=1000.0, avg_loss=100.0,
            fraction=1.0,  # Full Kelly
        )
        assert ps.risk_pct <= MAX_RISK_PER_TRADE_ABSOLUTE

    def test_zero_avg_win(self):
        ps = PositionSizer.kelly_criterion(
            entry=43200.0, stop_loss=42900.0, balance=10000.0,
            win_rate=0.60, avg_win=0.0, avg_loss=300.0,
        )
        assert ps.quantity == 0.0


class TestLeverageCap:
    def test_cap_reduces_leverage(self):
        ps = PositionSize(
            quantity=1.0, notional=43200.0, margin=4320.0,
            risk_amount=200.0, risk_pct=0.02, leverage=15,
        )
        capped = PositionSizer.apply_leverage_cap(ps, max_leverage=10)
        assert capped.leverage == 10
        assert capped.margin == pytest.approx(43200.0 / 10)

    def test_within_cap_unchanged(self):
        ps = PositionSize(
            quantity=1.0, notional=43200.0, margin=14400.0,
            risk_amount=200.0, risk_pct=0.02, leverage=3,
        )
        capped = PositionSizer.apply_leverage_cap(ps, max_leverage=10)
        assert capped.leverage == 3


class TestReduceByFactor:
    def test_reduce_50_percent(self):
        ps = PositionSize(
            quantity=1.0, notional=43200.0, margin=14400.0,
            risk_amount=200.0, risk_pct=0.02, leverage=3,
        )
        reduced = PositionSizer.reduce_by_factor(ps, 0.5)
        assert reduced.quantity == pytest.approx(0.5)
        assert reduced.notional == pytest.approx(21600.0)
        assert reduced.risk_amount == pytest.approx(100.0)

    def test_reduce_zero(self):
        ps = PositionSize(
            quantity=1.0, notional=43200.0, margin=14400.0,
            risk_amount=200.0, risk_pct=0.02, leverage=3,
        )
        reduced = PositionSizer.reduce_by_factor(ps, 0.0)
        assert reduced.quantity == 0.0

    def test_reduce_clamped_to_1(self):
        ps = PositionSize(
            quantity=1.0, notional=43200.0, margin=14400.0,
            risk_amount=200.0, risk_pct=0.02, leverage=3,
        )
        reduced = PositionSizer.reduce_by_factor(ps, 1.5)
        assert reduced.quantity == pytest.approx(1.0)
