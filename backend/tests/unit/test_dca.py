"""Tests for DCA (Dollar Cost Averaging) calculator."""

import pytest

from app.risk.dca import DCACalculator, DEFAULT_DCA_CONFIG


class TestDCACalculatorInit:
    def test_default_config(self):
        calc = DCACalculator()
        assert calc.enabled is False
        assert calc.max_orders == 3
        assert calc.triggers == [2.0, 4.0, 6.0]
        assert calc.multipliers == [1.0, 1.5, 2.0]

    def test_custom_config(self):
        calc = DCACalculator({"enabled": True, "max_dca_orders": 5})
        assert calc.enabled is True
        assert calc.max_orders == 5


class TestShouldTriggerDCA:
    def test_disabled_returns_none(self):
        calc = DCACalculator({"enabled": False})
        assert calc.should_trigger_dca(100.0, 95.0, "LONG", 0) is None

    def test_max_orders_reached(self):
        calc = DCACalculator({"enabled": True, "max_dca_orders": 2})
        assert calc.should_trigger_dca(100.0, 90.0, "LONG", 2) is None

    def test_long_no_drop(self):
        calc = DCACalculator({"enabled": True})
        # Price above entry — no DCA
        assert calc.should_trigger_dca(100.0, 105.0, "LONG", 0) is None

    def test_long_drop_triggers_level_0(self):
        calc = DCACalculator({"enabled": True, "trigger_drop_pct": [2.0, 4.0, 6.0]})
        # 3% drop from 100 → 97, trigger threshold is 2%
        assert calc.should_trigger_dca(100.0, 97.0, "LONG", 0) == 0

    def test_long_drop_triggers_level_1(self):
        calc = DCACalculator({"enabled": True, "trigger_drop_pct": [2.0, 4.0, 6.0]})
        # Already filled level 0, 5% drop triggers level 1 (threshold 4%)
        assert calc.should_trigger_dca(100.0, 95.0, "LONG", 1) == 1

    def test_long_drop_not_enough(self):
        calc = DCACalculator({"enabled": True, "trigger_drop_pct": [2.0, 4.0, 6.0]})
        # Only 1% drop, not enough for 2% threshold
        assert calc.should_trigger_dca(100.0, 99.0, "LONG", 0) is None

    def test_short_drop_triggers(self):
        calc = DCACalculator({"enabled": True, "trigger_drop_pct": [2.0, 4.0]})
        # SHORT: price goes UP 3% from 100 → 103
        assert calc.should_trigger_dca(100.0, 103.0, "SHORT", 0) == 0

    def test_short_no_drop(self):
        calc = DCACalculator({"enabled": True})
        # SHORT: price goes DOWN (profit), no DCA
        assert calc.should_trigger_dca(100.0, 95.0, "SHORT", 0) is None


class TestCalculateDCAQuantity:
    def test_level_0(self):
        calc = DCACalculator({"qty_multiplier": [1.0, 1.5, 2.0]})
        assert calc.calculate_dca_quantity(10.0, 0) == 10.0

    def test_level_1(self):
        calc = DCACalculator({"qty_multiplier": [1.0, 1.5, 2.0]})
        assert calc.calculate_dca_quantity(10.0, 1) == 15.0

    def test_level_2(self):
        calc = DCACalculator({"qty_multiplier": [1.0, 1.5, 2.0]})
        assert calc.calculate_dca_quantity(10.0, 2) == 20.0

    def test_out_of_range(self):
        calc = DCACalculator({"qty_multiplier": [1.0]})
        # Level beyond array → returns initial qty
        assert calc.calculate_dca_quantity(10.0, 5) == 10.0


class TestCalculateNewAverageEntry:
    def test_basic_average(self):
        calc = DCACalculator()
        # 10 units @ $100, add 10 units @ $90 → avg = $95
        avg = calc.calculate_new_average_entry(10.0, 100.0, 10.0, 90.0)
        assert avg == pytest.approx(95.0)

    def test_unequal_quantities(self):
        calc = DCACalculator()
        # 10 units @ $100, add 20 units @ $90 → avg = (1000+1800)/30 = $93.33
        avg = calc.calculate_new_average_entry(10.0, 100.0, 20.0, 90.0)
        assert avg == pytest.approx(93.333, abs=0.01)

    def test_zero_new_qty(self):
        calc = DCACalculator()
        avg = calc.calculate_new_average_entry(10.0, 100.0, 0.0, 90.0)
        assert avg == pytest.approx(100.0)


class TestRecalculateSL:
    def test_follow_mode_long(self):
        calc = DCACalculator({"sl_recalc_mode": "follow"})
        # Original: entry=100, SL=95 (5% below)
        # New avg entry: 95 → new SL should be 5% below = 90.25
        new_sl = calc.recalculate_sl(100.0, 95.0, 95.0, "LONG")
        assert new_sl == pytest.approx(90.25)

    def test_follow_mode_short(self):
        calc = DCACalculator({"sl_recalc_mode": "follow"})
        # Original: entry=100, SL=105 (5% above)
        # New avg entry: 103 → new SL should be 5% above = 108.15
        new_sl = calc.recalculate_sl(100.0, 105.0, 103.0, "SHORT")
        assert new_sl == pytest.approx(108.15)

    def test_fixed_mode(self):
        calc = DCACalculator({"sl_recalc_mode": "fixed"})
        # Fixed mode: SL doesn't change
        new_sl = calc.recalculate_sl(100.0, 95.0, 90.0, "LONG")
        assert new_sl == 95.0


class TestRecalculateTP:
    def test_recalculate_mode_long(self):
        calc = DCACalculator({"tp_recalc_mode": "recalculate"})
        # Original: entry=100, TP=110 (10% above)
        # New avg entry: 95 → new TP should be 10% above = 104.5
        new_tp = calc.recalculate_tp(100.0, 110.0, 95.0, "LONG")
        assert new_tp == pytest.approx(104.5)

    def test_fixed_mode(self):
        calc = DCACalculator({"tp_recalc_mode": "fixed"})
        new_tp = calc.recalculate_tp(100.0, 110.0, 95.0, "LONG")
        assert new_tp == 110.0


class TestCheckRiskBudget:
    def test_within_budget(self):
        calc = DCACalculator({"max_total_risk_pct": 5.0})
        assert calc.check_risk_budget(3.0, 1.5) is True

    def test_exceeds_budget(self):
        calc = DCACalculator({"max_total_risk_pct": 5.0})
        assert calc.check_risk_budget(4.0, 2.0) is False

    def test_at_limit(self):
        calc = DCACalculator({"max_total_risk_pct": 5.0})
        assert calc.check_risk_budget(3.0, 2.0) is True
