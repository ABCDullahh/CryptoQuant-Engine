"""Unit tests for CircuitBreaker - trigger conditions."""

from __future__ import annotations

import pytest

from app.config.constants import (
    CONSECUTIVE_LOSS_PAUSE,
    CONSECUTIVE_LOSS_REDUCE,
    MAX_DAILY_LOSS,
    MAX_DRAWDOWN,
    MAX_WEEKLY_LOSS,
    CircuitBreakerAction,
    CircuitBreakerState,
)
from app.risk.circuit_breaker import CircuitBreaker


class TestConsecutiveLossTriggers:
    def test_3_losses_reduce(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(consecutive_losses=3)
        assert result == CircuitBreakerAction.REDUCE_50

    def test_4_losses_still_reduce(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(consecutive_losses=4)
        assert result == CircuitBreakerAction.REDUCE_50

    def test_5_losses_pause(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(consecutive_losses=5)
        assert result == CircuitBreakerAction.PAUSE_4H

    def test_2_losses_no_trigger(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(consecutive_losses=2)
        assert result is None

    def test_0_losses_no_trigger(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(consecutive_losses=0)
        assert result is None


class TestDailyLossTriggers:
    def test_3pct_daily_loss_reduce(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(daily_loss_pct=0.035)
        assert result == CircuitBreakerAction.REDUCE_50

    def test_5pct_daily_loss_stop(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(daily_loss_pct=0.05)
        assert result == CircuitBreakerAction.STOP_24H

    def test_2pct_daily_loss_no_trigger(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(daily_loss_pct=0.02)
        assert result is None

    def test_exact_threshold_triggers(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(daily_loss_pct=MAX_DAILY_LOSS)
        assert result == CircuitBreakerAction.STOP_24H


class TestWeeklyLossTriggers:
    def test_10pct_weekly_loss_stop(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(weekly_loss_pct=0.10)
        assert result == CircuitBreakerAction.STOP_24H

    def test_8pct_weekly_loss_no_trigger(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(weekly_loss_pct=0.08)
        assert result is None


class TestDrawdownTriggers:
    def test_15pct_drawdown_full_stop(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(max_drawdown_pct=0.15)
        assert result == CircuitBreakerAction.FULL_STOP

    def test_20pct_drawdown_full_stop(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(max_drawdown_pct=0.20)
        assert result == CircuitBreakerAction.FULL_STOP

    def test_10pct_drawdown_no_trigger(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(max_drawdown_pct=0.10)
        assert result is None


class TestTriggerPriority:
    def test_drawdown_takes_priority_over_daily(self):
        """Drawdown (FULL_STOP) is most severe → takes priority."""
        cb = CircuitBreaker()
        result = cb.check_triggers(
            daily_loss_pct=0.06,
            max_drawdown_pct=0.16,
        )
        assert result == CircuitBreakerAction.FULL_STOP

    def test_daily_loss_takes_priority_over_consecutive(self):
        """Daily loss (STOP_24H) > consecutive loss (PAUSE_4H)."""
        cb = CircuitBreaker()
        result = cb.check_triggers(
            daily_loss_pct=0.06,
            consecutive_losses=5,
        )
        assert result == CircuitBreakerAction.STOP_24H

    def test_full_stop_stays_in_full_stop(self):
        """Once in FULL_STOP, cannot be overridden."""
        cb = CircuitBreaker()
        cb.check_triggers(max_drawdown_pct=0.20)
        result = cb.check_triggers(consecutive_losses=3)
        assert result == CircuitBreakerAction.FULL_STOP


class TestMultipleTriggers:
    def test_no_triggers_returns_none(self):
        cb = CircuitBreaker()
        result = cb.check_triggers(
            consecutive_losses=0,
            daily_loss_pct=0.0,
            weekly_loss_pct=0.0,
            max_drawdown_pct=0.0,
        )
        assert result is None

    def test_all_triggers_at_once(self):
        """When everything is bad, most severe wins."""
        cb = CircuitBreaker()
        result = cb.check_triggers(
            consecutive_losses=10,
            daily_loss_pct=0.10,
            weekly_loss_pct=0.15,
            max_drawdown_pct=0.20,
        )
        assert result == CircuitBreakerAction.FULL_STOP
