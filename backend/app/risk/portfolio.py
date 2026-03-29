"""Portfolio-level risk management - heat, drawdown, position limits."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog

from app.config.constants import (
    MAX_CORRELATED_POSITIONS,
    MAX_DAILY_LOSS,
    MAX_DRAWDOWN,
    MAX_OPEN_POSITIONS,
    MAX_PORTFOLIO_HEAT,
    MAX_WEEKLY_LOSS,
    Direction,
)
from app.core.models import PortfolioState, Position

logger = structlog.get_logger(__name__)


class PortfolioRiskManager:
    """Manages portfolio-level risk metrics and limits.

    Tracks:
    - Portfolio heat (total % at risk)
    - Peak equity and drawdown
    - Daily and weekly P&L
    - Open position count and correlation
    - Consecutive losses
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        max_positions: int = MAX_OPEN_POSITIONS,
        max_heat: float = MAX_PORTFOLIO_HEAT,
        max_correlated: int = MAX_CORRELATED_POSITIONS,
    ) -> None:
        self._balance = initial_balance
        self._equity = initial_balance
        self._peak_equity = initial_balance
        self._max_positions = max_positions
        self._max_heat = max_heat
        self._max_correlated = max_correlated

        self._open_positions: list[Position] = []
        self._daily_pnl: float = 0.0
        self._weekly_pnl: float = 0.0
        self._consecutive_losses: int = 0
        self._day_start: datetime = datetime.now(tz=UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self._week_start: datetime = self._day_start - timedelta(
            days=self._day_start.weekday()
        )

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def equity(self) -> float:
        return self._equity

    @property
    def peak_equity(self) -> float:
        return self._peak_equity

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses

    @property
    def open_positions(self) -> list[Position]:
        return list(self._open_positions)

    def get_state(self) -> PortfolioState:
        """Get current portfolio state snapshot."""
        unrealized = sum(p.unrealized_pnl for p in self._open_positions)
        margin_used = sum(
            p.quantity * p.entry_price / p.leverage
            for p in self._open_positions
        )

        return PortfolioState(
            balance=self._balance,
            equity=self._equity,
            unrealized_pnl=unrealized,
            margin_used=margin_used,
            margin_available=self._balance - margin_used,
            portfolio_heat=self.calculate_heat(),
            open_positions=len(self._open_positions),
            daily_pnl=self._daily_pnl,
            weekly_pnl=self._weekly_pnl,
            max_drawdown=self.calculate_drawdown(),
            consecutive_losses=self._consecutive_losses,
        )

    # ----------------------------------------------------------------
    # Risk metric calculations
    # ----------------------------------------------------------------

    def calculate_heat(self) -> float:
        """Calculate portfolio heat: total % of equity at risk.

        heat = sum(position_risk * leverage) / equity
        position_risk = |entry - stop_loss| * quantity * leverage
        """
        if self._equity <= 0:
            return 0.0

        total_risk = 0.0
        for pos in self._open_positions:
            risk_per_unit = abs(pos.entry_price - pos.stop_loss)
            position_risk = risk_per_unit * pos.quantity * pos.leverage
            total_risk += position_risk

        return total_risk / self._equity

    def calculate_drawdown(self) -> float:
        """Calculate current drawdown from peak equity.

        drawdown = (peak - current) / peak
        """
        if self._peak_equity <= 0:
            return 0.0
        return max(0.0, (self._peak_equity - self._equity) / self._peak_equity)

    def daily_loss_pct(self) -> float:
        """Calculate daily loss as percentage of starting balance."""
        if self._balance <= 0:
            return 0.0
        return max(0.0, -self._daily_pnl / self._balance)

    def weekly_loss_pct(self) -> float:
        """Calculate weekly loss as percentage of starting balance."""
        if self._balance <= 0:
            return 0.0
        return max(0.0, -self._weekly_pnl / self._balance)

    # ----------------------------------------------------------------
    # Limit checks
    # ----------------------------------------------------------------

    def can_open_position(self) -> tuple[bool, str]:
        """Check if a new position can be opened.

        Returns (allowed, reason).
        """
        if len(self._open_positions) >= self._max_positions:
            return False, f"Max positions reached ({self._max_positions})"

        if self.calculate_heat() >= self._max_heat:
            return False, f"Portfolio heat >= {self._max_heat:.0%}"

        if self.calculate_drawdown() >= MAX_DRAWDOWN:
            return False, f"Max drawdown >= {MAX_DRAWDOWN:.0%}"

        if self.daily_loss_pct() >= MAX_DAILY_LOSS:
            return False, f"Daily loss >= {MAX_DAILY_LOSS:.0%}"

        if self.weekly_loss_pct() >= MAX_WEEKLY_LOSS:
            return False, f"Weekly loss >= {MAX_WEEKLY_LOSS:.0%}"

        return True, ""

    def check_correlation(
        self,
        symbol: str,
        direction: Direction,
    ) -> tuple[bool, str]:
        """Check if adding a position would violate correlation limits.

        Max positions in same direction for same/correlated pairs.
        """
        same_direction_count = sum(
            1 for p in self._open_positions
            if p.direction == direction
        )

        if same_direction_count >= self._max_correlated:
            return False, (
                f"Max correlated positions reached "
                f"({same_direction_count} {direction} positions)"
            )

        return True, ""

    def remaining_heat_capacity(self) -> float:
        """Calculate remaining portfolio heat capacity.

        Returns max additional risk allowed as fraction of equity.
        """
        return max(0.0, self._max_heat - self.calculate_heat())

    # ----------------------------------------------------------------
    # Position management
    # ----------------------------------------------------------------

    def add_position(self, position: Position) -> None:
        """Register a new open position."""
        self._open_positions.append(position)
        logger.info(
            "portfolio.position_added",
            symbol=position.symbol,
            direction=position.direction,
            open_count=len(self._open_positions),
        )

    def remove_position(self, position_id) -> Position | None:
        """Remove a closed position and return it."""
        pid = str(position_id)
        for i, pos in enumerate(self._open_positions):
            if str(pos.id) == pid:
                return self._open_positions.pop(i)
        return None

    def record_trade_result(self, pnl: float) -> None:
        """Record a closed trade's P&L.

        Updates balance, equity, peak, daily/weekly P&L, consecutive losses.
        """
        self._balance += pnl
        self._equity = self._balance + sum(
            p.unrealized_pnl for p in self._open_positions
        )

        if self._equity > self._peak_equity:
            self._peak_equity = self._equity

        self._daily_pnl += pnl
        self._weekly_pnl += pnl

        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    def update_equity(self, unrealized_pnl: float) -> None:
        """Update equity based on unrealized P&L changes."""
        self._equity = self._balance + unrealized_pnl
        if self._equity > self._peak_equity:
            self._peak_equity = self._equity

    def reset_daily_pnl(self) -> None:
        """Reset daily P&L counter (called at day boundary)."""
        self._daily_pnl = 0.0

    def reset_weekly_pnl(self) -> None:
        """Reset weekly P&L counter (called at week boundary)."""
        self._weekly_pnl = 0.0
