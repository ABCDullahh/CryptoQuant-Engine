"""Unit tests for CircuitBreaker - state machine transitions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.config.constants import (
    CIRCUIT_BREAKER_COOLDOWN_HOURS,
    CircuitBreakerAction,
    CircuitBreakerState,
)
from app.risk.circuit_breaker import CircuitBreaker


class TestInitialState:
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_trading_allowed_initially(self):
        cb = CircuitBreaker()
        assert cb.is_trading_allowed() is True

    def test_no_action_initially(self):
        cb = CircuitBreaker()
        assert cb.action is None

    def test_full_position_size_initially(self):
        cb = CircuitBreaker()
        assert cb.position_size_factor == 1.0


class TestClosedToOpen:
    def test_daily_loss_triggers_open(self):
        cb = CircuitBreaker()
        cb.check_triggers(daily_loss_pct=0.06)
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.action == CircuitBreakerAction.STOP_24H

    def test_consecutive_losses_triggers_open(self):
        cb = CircuitBreaker()
        cb.check_triggers(consecutive_losses=5)
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.action == CircuitBreakerAction.PAUSE_4H

    def test_max_drawdown_triggers_full_stop(self):
        cb = CircuitBreaker()
        cb.check_triggers(max_drawdown_pct=0.16)
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.action == CircuitBreakerAction.FULL_STOP

    def test_open_blocks_trading(self):
        cb = CircuitBreaker()
        cb.check_triggers(daily_loss_pct=0.06)
        assert cb.is_trading_allowed() is False

    def test_trigger_sets_reason(self):
        cb = CircuitBreaker()
        cb.check_triggers(daily_loss_pct=0.06)
        assert "Daily loss" in cb.trigger_reason


class TestOpenToHalfOpen:
    def test_cooldown_elapsed_transitions_to_half_open(self):
        cb = CircuitBreaker()
        cb.check_triggers(consecutive_losses=5)
        assert cb.state == CircuitBreakerState.OPEN

        # Fast-forward past cooldown
        future = datetime.now(tz=UTC) + timedelta(hours=CIRCUIT_BREAKER_COOLDOWN_HOURS + 1)
        assert cb.is_trading_allowed(now=future) is True
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_cooldown_not_elapsed_stays_open(self):
        cb = CircuitBreaker()
        cb.check_triggers(consecutive_losses=5)

        # Still within cooldown
        near_future = datetime.now(tz=UTC) + timedelta(hours=1)
        assert cb.is_trading_allowed(now=near_future) is False
        assert cb.state == CircuitBreakerState.OPEN

    def test_half_open_reduced_size(self):
        cb = CircuitBreaker()
        cb.check_triggers(consecutive_losses=5)
        future = datetime.now(tz=UTC) + timedelta(hours=CIRCUIT_BREAKER_COOLDOWN_HOURS + 1)
        cb.is_trading_allowed(now=future)
        assert cb.position_size_factor == 0.5


class TestHalfOpenTransitions:
    def test_win_in_half_open_transitions_to_closed(self):
        cb = CircuitBreaker()
        cb.check_triggers(consecutive_losses=5)
        future = datetime.now(tz=UTC) + timedelta(hours=CIRCUIT_BREAKER_COOLDOWN_HOURS + 1)
        cb.is_trading_allowed(now=future)
        assert cb.state == CircuitBreakerState.HALF_OPEN

        cb.record_trade_result(is_win=True)
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.position_size_factor == 1.0

    def test_loss_in_half_open_transitions_back_to_open(self):
        cb = CircuitBreaker()
        cb.check_triggers(consecutive_losses=5)
        future = datetime.now(tz=UTC) + timedelta(hours=CIRCUIT_BREAKER_COOLDOWN_HOURS + 1)
        cb.is_trading_allowed(now=future)

        cb.record_trade_result(is_win=False)
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.position_size_factor == 0.0


class TestFullStop:
    def test_full_stop_blocks_trading(self):
        cb = CircuitBreaker()
        cb.check_triggers(max_drawdown_pct=0.20)
        assert cb.action == CircuitBreakerAction.FULL_STOP
        assert cb.is_trading_allowed() is False

    def test_full_stop_no_cooldown(self):
        """FULL_STOP has no automatic recovery - needs manual reset."""
        cb = CircuitBreaker()
        cb.check_triggers(max_drawdown_pct=0.20)
        assert cb.cooldown_until is None

        # Even far future doesn't auto-recover
        far_future = datetime.now(tz=UTC) + timedelta(days=30)
        assert cb.is_trading_allowed(now=far_future) is False

    def test_full_stop_requires_manual_reset(self):
        cb = CircuitBreaker()
        cb.check_triggers(max_drawdown_pct=0.20)
        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.is_trading_allowed() is True


class TestReset:
    def test_reset_clears_all_state(self):
        cb = CircuitBreaker()
        cb.check_triggers(daily_loss_pct=0.06)
        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.action is None
        assert cb.trigger_reason == ""
        assert cb.position_size_factor == 1.0
        assert cb.cooldown_until is None


class TestReduceAction:
    def test_reduce_50_sets_half_open(self):
        cb = CircuitBreaker()
        cb.check_triggers(consecutive_losses=3)
        assert cb.state == CircuitBreakerState.HALF_OPEN
        assert cb.action == CircuitBreakerAction.REDUCE_50
        assert cb.position_size_factor == 0.5

    def test_reduce_50_allows_trading(self):
        cb = CircuitBreaker()
        cb.check_triggers(consecutive_losses=3)
        assert cb.is_trading_allowed() is True
