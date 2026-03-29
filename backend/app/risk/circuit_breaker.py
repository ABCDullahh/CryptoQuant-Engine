"""Circuit breaker for risk management - state machine with triggers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog

from app.config.constants import (
    CIRCUIT_BREAKER_COOLDOWN_HOURS,
    CONSECUTIVE_LOSS_PAUSE,
    CONSECUTIVE_LOSS_REDUCE,
    MAX_DAILY_LOSS,
    MAX_DRAWDOWN,
    MAX_WEEKLY_LOSS,
    CircuitBreakerAction,
    CircuitBreakerState,
)

logger = structlog.get_logger(__name__)


class CircuitBreaker:
    """Circuit breaker state machine for trading risk control.

    States:
      CLOSED    → Normal operation, trading allowed
      OPEN      → Trading halted, cooldown period active
      HALF_OPEN → Testing with reduced position sizes

    Transitions:
      CLOSED → OPEN:      Trigger condition met
      OPEN → HALF_OPEN:   Cooldown period elapsed
      HALF_OPEN → CLOSED: Successful trade in reduced mode
      HALF_OPEN → OPEN:   Failed trade, reset cooldown
    """

    def __init__(self) -> None:
        self._state: CircuitBreakerState = CircuitBreakerState.CLOSED
        self._action: CircuitBreakerAction | None = None
        self._triggered_at: datetime | None = None
        self._cooldown_until: datetime | None = None
        self._trigger_reason: str = ""
        self._position_size_factor: float = 1.0

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    @property
    def action(self) -> CircuitBreakerAction | None:
        return self._action

    @property
    def trigger_reason(self) -> str:
        return self._trigger_reason

    @property
    def position_size_factor(self) -> float:
        """Factor to multiply position size by (1.0 = full, 0.5 = half)."""
        return self._position_size_factor

    @property
    def cooldown_until(self) -> datetime | None:
        return self._cooldown_until

    def is_trading_allowed(self, now: datetime | None = None) -> bool:
        """Check if trading is currently allowed."""
        now = now or datetime.now(tz=UTC)

        if self._state == CircuitBreakerState.CLOSED:
            return True

        if self._state == CircuitBreakerState.OPEN:
            # Check if cooldown has elapsed
            if self._cooldown_until and now >= self._cooldown_until:
                self._transition_to_half_open()
                return True
            return False

        if self._state == CircuitBreakerState.HALF_OPEN:
            return True

        return False

    def check_triggers(
        self,
        consecutive_losses: int = 0,
        daily_loss_pct: float = 0.0,
        weekly_loss_pct: float = 0.0,
        max_drawdown_pct: float = 0.0,
    ) -> CircuitBreakerAction | None:
        """Check all trigger conditions and open circuit breaker if needed.

        Returns the action taken, or None if no trigger was hit.
        """
        # Already in FULL_STOP, nothing more to do
        if self._action == CircuitBreakerAction.FULL_STOP:
            return self._action

        # Trigger 1: Max drawdown (most severe)
        if max_drawdown_pct >= MAX_DRAWDOWN:
            self._trigger(
                CircuitBreakerAction.FULL_STOP,
                f"Max drawdown {max_drawdown_pct:.1%} >= {MAX_DRAWDOWN:.0%}",
                cooldown_hours=None,  # Manual review required
            )
            return self._action

        # Trigger 2: Daily loss > 5% → stop 24h
        if daily_loss_pct >= MAX_DAILY_LOSS:
            self._trigger(
                CircuitBreakerAction.STOP_24H,
                f"Daily loss {daily_loss_pct:.1%} >= {MAX_DAILY_LOSS:.0%}",
                cooldown_hours=24,
            )
            return self._action

        # Trigger 3: Weekly loss > 10%
        if weekly_loss_pct >= MAX_WEEKLY_LOSS:
            self._trigger(
                CircuitBreakerAction.STOP_24H,
                f"Weekly loss {weekly_loss_pct:.1%} >= {MAX_WEEKLY_LOSS:.0%}",
                cooldown_hours=24,
            )
            return self._action

        # Trigger 4: 5 consecutive losses → pause 4h
        if consecutive_losses >= CONSECUTIVE_LOSS_PAUSE:
            self._trigger(
                CircuitBreakerAction.PAUSE_4H,
                f"{consecutive_losses} consecutive losses >= {CONSECUTIVE_LOSS_PAUSE}",
                cooldown_hours=CIRCUIT_BREAKER_COOLDOWN_HOURS,
            )
            return self._action

        # Trigger 5: 3 consecutive losses → reduce 50%
        if consecutive_losses >= CONSECUTIVE_LOSS_REDUCE:
            self._trigger(
                CircuitBreakerAction.REDUCE_50,
                f"{consecutive_losses} consecutive losses >= {CONSECUTIVE_LOSS_REDUCE}",
                cooldown_hours=0,  # Immediate, no cooldown
            )
            return self._action

        # Trigger 6: Daily loss > 3% → reduce 50%
        if daily_loss_pct >= 0.03:
            self._trigger(
                CircuitBreakerAction.REDUCE_50,
                f"Daily loss {daily_loss_pct:.1%} >= 3%",
                cooldown_hours=0,
            )
            return self._action

        return None

    def record_trade_result(self, is_win: bool) -> None:
        """Record a trade result to transition state.

        In HALF_OPEN:
          - Win → transition to CLOSED
          - Loss → transition back to OPEN (reset cooldown)
        """
        if self._state == CircuitBreakerState.HALF_OPEN:
            if is_win:
                self._transition_to_closed()
            else:
                self._transition_to_open(reset_cooldown=True)

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        self._state = CircuitBreakerState.CLOSED
        self._action = None
        self._triggered_at = None
        self._cooldown_until = None
        self._trigger_reason = ""
        self._position_size_factor = 1.0
        logger.info("circuit_breaker.reset")

    def _trigger(
        self,
        action: CircuitBreakerAction,
        reason: str,
        cooldown_hours: int | None,
    ) -> None:
        """Trigger the circuit breaker."""
        now = datetime.now(tz=UTC)

        self._action = action
        self._triggered_at = now
        self._trigger_reason = reason

        if action == CircuitBreakerAction.REDUCE_50:
            # REDUCE doesn't fully open, just reduces size
            self._state = CircuitBreakerState.HALF_OPEN
            self._position_size_factor = 0.5
            self._cooldown_until = None
        elif action == CircuitBreakerAction.FULL_STOP:
            self._state = CircuitBreakerState.OPEN
            self._position_size_factor = 0.0
            self._cooldown_until = None  # Manual reset required
        else:
            self._state = CircuitBreakerState.OPEN
            self._position_size_factor = 0.0
            if cooldown_hours is not None and cooldown_hours > 0:
                self._cooldown_until = now + timedelta(hours=cooldown_hours)

        logger.warning(
            "circuit_breaker.triggered",
            action=action,
            reason=reason,
            state=self._state,
            cooldown_until=self._cooldown_until,
        )

    def _transition_to_half_open(self) -> None:
        """Transition from OPEN to HALF_OPEN after cooldown."""
        self._state = CircuitBreakerState.HALF_OPEN
        self._position_size_factor = 0.5
        logger.info("circuit_breaker.half_open")

    def _transition_to_closed(self) -> None:
        """Transition from HALF_OPEN to CLOSED after successful trade."""
        self._state = CircuitBreakerState.CLOSED
        self._action = None
        self._position_size_factor = 1.0
        self._cooldown_until = None
        self._trigger_reason = ""
        logger.info("circuit_breaker.closed")

    def _transition_to_open(self, reset_cooldown: bool = False) -> None:
        """Transition from HALF_OPEN back to OPEN."""
        self._state = CircuitBreakerState.OPEN
        self._position_size_factor = 0.0
        if reset_cooldown:
            now = datetime.now(tz=UTC)
            self._cooldown_until = now + timedelta(
                hours=CIRCUIT_BREAKER_COOLDOWN_HOURS
            )
        logger.warning("circuit_breaker.reopened")
