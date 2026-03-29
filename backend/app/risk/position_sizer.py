"""Position sizing algorithms for risk management."""

from __future__ import annotations

import math

from app.config.constants import (
    DEFAULT_LEVERAGE,
    KELLY_FRACTION,
    MAX_LEVERAGE,
    MAX_RISK_PER_TRADE,
    MAX_RISK_PER_TRADE_ABSOLUTE,
    MarketRegime,
)
from app.core.models import PositionSize


class PositionSizer:
    """Calculates position sizes using multiple methods."""

    @staticmethod
    def fixed_fractional(
        entry: float,
        stop_loss: float,
        balance: float,
        risk_pct: float = MAX_RISK_PER_TRADE,
    ) -> PositionSize:
        """Fixed fractional position sizing (default method).

        risk_amount = balance * risk_pct
        quantity = risk_amount / |entry - stop_loss|
        """
        risk_pct = min(risk_pct, MAX_RISK_PER_TRADE_ABSOLUTE)
        risk_amount = balance * risk_pct
        risk_per_unit = abs(entry - stop_loss)

        if risk_per_unit == 0:
            risk_per_unit = entry * 0.01

        quantity = risk_amount / risk_per_unit
        notional = quantity * entry
        leverage = max(1, min(int(math.ceil(notional / balance)), MAX_LEVERAGE))
        margin = notional / leverage

        return PositionSize(
            quantity=quantity,
            notional=notional,
            margin=margin,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            leverage=leverage,
        )

    @staticmethod
    def volatility_based(
        entry: float,
        atr: float,
        balance: float,
        regime: MarketRegime = MarketRegime.RANGING,
        risk_pct: float = MAX_RISK_PER_TRADE,
    ) -> PositionSize:
        """Volatility-based position sizing using ATR and regime.

        stop_distance = atr * regime_multiplier
        quantity = risk_amount / stop_distance
        """
        from app.config.constants import (
            ATR_MULTIPLIER_DEFAULT,
            ATR_MULTIPLIER_LOW_VOL,
            ATR_MULTIPLIER_RANGING,
            ATR_MULTIPLIER_TRENDING,
            ATR_MULTIPLIER_VOLATILE,
        )

        multiplier_map = {
            MarketRegime.TRENDING_UP: ATR_MULTIPLIER_TRENDING,
            MarketRegime.TRENDING_DOWN: ATR_MULTIPLIER_TRENDING,
            MarketRegime.RANGING: ATR_MULTIPLIER_RANGING,
            MarketRegime.HIGH_VOLATILITY: ATR_MULTIPLIER_VOLATILE,
            MarketRegime.LOW_VOLATILITY: ATR_MULTIPLIER_LOW_VOL,
            MarketRegime.CHOPPY: ATR_MULTIPLIER_DEFAULT,
        }
        multiplier = multiplier_map.get(regime, ATR_MULTIPLIER_DEFAULT)

        risk_pct = min(risk_pct, MAX_RISK_PER_TRADE_ABSOLUTE)
        risk_amount = balance * risk_pct
        stop_distance = atr * multiplier

        if stop_distance == 0:
            stop_distance = entry * 0.01

        quantity = risk_amount / stop_distance
        notional = quantity * entry
        leverage = max(1, min(int(math.ceil(notional / balance)), MAX_LEVERAGE))
        margin = notional / leverage

        return PositionSize(
            quantity=quantity,
            notional=notional,
            margin=margin,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            leverage=leverage,
        )

    @staticmethod
    def kelly_criterion(
        entry: float,
        stop_loss: float,
        balance: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        fraction: float = KELLY_FRACTION,
    ) -> PositionSize:
        """Kelly criterion position sizing (fractional Kelly).

        kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        Practical: use fraction (25-50%) of full Kelly.
        """
        if avg_win <= 0 or avg_loss <= 0:
            # No edge, use minimum
            kelly = 0.0
        else:
            kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win

        # Fractional Kelly for safety
        kelly_fraction = max(0.0, min(kelly * fraction, MAX_RISK_PER_TRADE_ABSOLUTE))

        risk_amount = balance * kelly_fraction
        risk_per_unit = abs(entry - stop_loss)

        if risk_per_unit == 0:
            risk_per_unit = entry * 0.01

        quantity = risk_amount / risk_per_unit if risk_amount > 0 else 0.0
        notional = quantity * entry
        leverage = max(1, min(int(math.ceil(notional / balance)) if balance > 0 else 1, MAX_LEVERAGE))
        margin = notional / leverage if leverage > 0 else 0.0

        return PositionSize(
            quantity=quantity,
            notional=notional,
            margin=margin,
            risk_amount=risk_amount,
            risk_pct=kelly_fraction,
            leverage=leverage,
        )

    @staticmethod
    def apply_leverage_cap(
        position: PositionSize,
        max_leverage: int = MAX_LEVERAGE,
        default_leverage: int = DEFAULT_LEVERAGE,
    ) -> PositionSize:
        """Apply leverage cap and adjust position accordingly."""
        capped_leverage = max(1, min(position.leverage, max_leverage))

        if capped_leverage == position.leverage:
            return position

        # Recalculate with capped leverage
        margin = position.notional / capped_leverage

        return PositionSize(
            quantity=position.quantity,
            notional=position.notional,
            margin=margin,
            risk_amount=position.risk_amount,
            risk_pct=position.risk_pct,
            leverage=capped_leverage,
        )

    @staticmethod
    def reduce_by_factor(
        position: PositionSize,
        factor: float,
    ) -> PositionSize:
        """Reduce position size by a factor (e.g., 0.5 for 50% reduction).

        Used by circuit breaker to reduce exposure.
        """
        factor = max(0.0, min(factor, 1.0))
        quantity = position.quantity * factor
        notional = quantity * (position.notional / position.quantity) if position.quantity > 0 else 0.0
        margin = notional / position.leverage if position.leverage > 0 else 0.0

        return PositionSize(
            quantity=quantity,
            notional=notional,
            margin=margin,
            risk_amount=position.risk_amount * factor,
            risk_pct=position.risk_pct,
            leverage=position.leverage,
        )
