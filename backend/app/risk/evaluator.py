"""Risk Evaluator - orchestrates all risk checks before approving a signal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from app.config.constants import (
    MAX_RISK_PER_TRADE,
    Direction,
    EventChannel,
    SignalStatus,
)
from app.core.events import event_bus
from app.core.models import CompositeSignal, EventMessage
from app.risk.circuit_breaker import CircuitBreaker
from app.risk.portfolio import PortfolioRiskManager
from app.risk.position_sizer import PositionSizer

logger = structlog.get_logger(__name__)


@dataclass
class RiskCheckResult:
    """Result of risk evaluation."""
    approved: bool
    signal: CompositeSignal | None = None
    rejection_reasons: list[str] = field(default_factory=list)
    adjustments: list[str] = field(default_factory=list)


class RiskEvaluator:
    """Orchestrates all risk checks for incoming signals.

    Evaluation flow:
    1. Check circuit breaker status
    2. Check portfolio limits (position count, heat, drawdown)
    3. Check correlation limits
    4. Apply position sizing adjustments
    5. Return approved or rejected signal
    """

    def __init__(
        self,
        portfolio: PortfolioRiskManager,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._portfolio = portfolio
        self._circuit_breaker = circuit_breaker or CircuitBreaker()

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit_breaker

    @property
    def portfolio(self) -> PortfolioRiskManager:
        return self._portfolio

    def evaluate(self, signal: CompositeSignal) -> RiskCheckResult:
        """Run all risk checks on a CompositeSignal.

        Returns RiskCheckResult with approved/rejected status and reasons.
        """
        reasons: list[str] = []
        adjustments: list[str] = []

        # 1. Check circuit breaker
        self._check_circuit_breaker_triggers()

        if not self._circuit_breaker.is_trading_allowed():
            reasons.append(
                f"Circuit breaker is {self._circuit_breaker.state}: "
                f"{self._circuit_breaker.trigger_reason}"
            )
            return RiskCheckResult(
                approved=False,
                signal=None,
                rejection_reasons=reasons,
            )

        # 2. Check portfolio limits
        can_open, limit_reason = self._portfolio.can_open_position()
        if not can_open:
            reasons.append(limit_reason)
            return RiskCheckResult(
                approved=False,
                signal=None,
                rejection_reasons=reasons,
            )

        # 3. Check correlation
        corr_ok, corr_reason = self._portfolio.check_correlation(
            signal.symbol, signal.direction
        )
        if not corr_ok:
            reasons.append(corr_reason)
            return RiskCheckResult(
                approved=False,
                signal=None,
                rejection_reasons=reasons,
            )

        # 4. Apply circuit breaker size reduction if in HALF_OPEN
        size_factor = self._circuit_breaker.position_size_factor
        if size_factor < 1.0:
            adjusted_size = PositionSizer.reduce_by_factor(
                signal.position_size, size_factor
            )
            signal = signal.model_copy(update={"position_size": adjusted_size})
            adjustments.append(
                f"Position reduced to {size_factor:.0%} (circuit breaker)"
            )

        # 5. Check remaining heat capacity
        remaining = self._portfolio.remaining_heat_capacity()
        if remaining <= 0:
            reasons.append("No remaining portfolio heat capacity")
            return RiskCheckResult(
                approved=False,
                signal=None,
                rejection_reasons=reasons,
            )

        # 6. Cap position size to remaining heat
        equity = self._portfolio.equity
        if equity > 0:
            position_risk = (
                abs(signal.entry_price - signal.stop_loss)
                * signal.position_size.quantity
            )
            position_heat = position_risk / equity
            if position_heat > remaining:
                # Scale down to fit
                scale = remaining / position_heat
                adjusted_size = PositionSizer.reduce_by_factor(
                    signal.position_size, scale
                )
                signal = signal.model_copy(update={"position_size": adjusted_size})
                adjustments.append(
                    f"Position scaled to {scale:.0%} to fit heat capacity"
                )

        # Signal approved
        signal = signal.model_copy(update={"status": SignalStatus.ACTIVE})

        return RiskCheckResult(
            approved=True,
            signal=signal,
            adjustments=adjustments,
        )

    async def evaluate_and_publish(
        self, signal: CompositeSignal
    ) -> RiskCheckResult:
        """Evaluate signal and publish result to EventBus."""
        result = self.evaluate(signal)

        if result.approved and result.signal is not None:
            try:
                await event_bus.publish(
                    EventChannel.SIGNAL_APPROVED,
                    EventMessage(
                        event_type="signal_approved",
                        data=result.signal.model_dump(mode="json"),
                    ),
                )
            except Exception as exc:
                logger.debug("risk.publish_approved_failed", error=str(exc))

            logger.info(
                "risk.signal_approved",
                symbol=signal.symbol,
                direction=signal.direction,
                grade=signal.grade,
                adjustments=result.adjustments,
            )
        else:
            try:
                await event_bus.publish(
                    EventChannel.RISK_ALERT,
                    EventMessage(
                        event_type="signal_rejected",
                        data={
                            "symbol": signal.symbol,
                            "direction": signal.direction,
                            "reasons": result.rejection_reasons,
                        },
                    ),
                )
            except Exception as exc:
                logger.debug("risk.publish_rejected_failed", error=str(exc))

            logger.warning(
                "risk.signal_rejected",
                symbol=signal.symbol,
                reasons=result.rejection_reasons,
            )

        return result

    def _check_circuit_breaker_triggers(self) -> None:
        """Update circuit breaker based on current portfolio state."""
        state = self._portfolio.get_state()
        self._circuit_breaker.check_triggers(
            consecutive_losses=state.consecutive_losses,
            daily_loss_pct=self._portfolio.daily_loss_pct(),
            weekly_loss_pct=self._portfolio.weekly_loss_pct(),
            max_drawdown_pct=self._portfolio.calculate_drawdown(),
        )
