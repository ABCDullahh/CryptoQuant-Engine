"""Stop loss calculation and trailing stop management."""

from __future__ import annotations

from app.config.constants import (
    ATR_MULTIPLIER_DEFAULT,
    ATR_MULTIPLIER_LOW_VOL,
    ATR_MULTIPLIER_RANGING,
    ATR_MULTIPLIER_TRENDING,
    ATR_MULTIPLIER_VOLATILE,
    MAX_SL_PERCENT,
    TRAILING_STOP_ATR_MULTIPLIER,
    Direction,
    MarketRegime,
    StopLossType,
)
from app.core.models import Candle


# Regime → ATR multiplier mapping
_REGIME_MULTIPLIERS: dict[MarketRegime, float] = {
    MarketRegime.TRENDING_UP: ATR_MULTIPLIER_TRENDING,
    MarketRegime.TRENDING_DOWN: ATR_MULTIPLIER_TRENDING,
    MarketRegime.RANGING: ATR_MULTIPLIER_RANGING,
    MarketRegime.HIGH_VOLATILITY: ATR_MULTIPLIER_VOLATILE,
    MarketRegime.LOW_VOLATILITY: ATR_MULTIPLIER_LOW_VOL,
    MarketRegime.CHOPPY: ATR_MULTIPLIER_DEFAULT,
}


class StopLossManager:
    """Calculates stop loss levels using multiple methods."""

    @staticmethod
    def atr_based(
        entry: float,
        direction: Direction,
        atr: float,
        regime: MarketRegime = MarketRegime.RANGING,
    ) -> tuple[float, StopLossType]:
        """ATR-based stop loss with regime-adjusted multiplier.

        LONG:  SL = entry - ATR * multiplier
        SHORT: SL = entry + ATR * multiplier
        """
        multiplier = _REGIME_MULTIPLIERS.get(regime, ATR_MULTIPLIER_DEFAULT)

        if direction == Direction.LONG:
            sl = entry - atr * multiplier
        else:
            sl = entry + atr * multiplier

        # Apply max SL distance cap
        sl = StopLossManager._cap_sl_distance(entry, sl, direction)

        return sl, StopLossType.ATR_BASED

    @staticmethod
    def structure_based(
        entry: float,
        direction: Direction,
        candles: list[Candle],
        atr: float,
        lookback: int = 20,
    ) -> tuple[float, StopLossType]:
        """Structure-based stop loss using recent swing highs/lows.

        LONG:  SL = recent swing low - buffer
        SHORT: SL = recent swing high + buffer
        """
        if len(candles) < 5:
            # Not enough data, fall back to percentage
            return StopLossManager._percentage_fallback(entry, direction)

        buffer = atr * 0.1
        window = candles[-lookback:] if len(candles) >= lookback else candles

        if direction == Direction.LONG:
            swing_low = min(c.low for c in window)
            sl = swing_low - buffer
        else:
            swing_high = max(c.high for c in window)
            sl = swing_high + buffer

        # Apply max SL distance cap
        sl = StopLossManager._cap_sl_distance(entry, sl, direction)

        return sl, StopLossType.STRUCTURE_BASED

    @staticmethod
    def combined(
        entry: float,
        direction: Direction,
        candles: list[Candle],
        atr: float,
        regime: MarketRegime = MarketRegime.RANGING,
    ) -> tuple[float, StopLossType]:
        """Combined approach: use the most protective SL.

        For LONG: the HIGHER of ATR and structure SL (less loss)
        For SHORT: the LOWER of ATR and structure SL (less loss)
        """
        atr_sl, _ = StopLossManager.atr_based(entry, direction, atr, regime)
        struct_sl, _ = StopLossManager.structure_based(
            entry, direction, candles, atr
        )

        if direction == Direction.LONG:
            # For long, higher SL = more protective (less loss)
            sl = max(atr_sl, struct_sl)
        else:
            # For short, lower SL = more protective (less loss)
            sl = min(atr_sl, struct_sl)

        return sl, StopLossType.COMBINED

    @staticmethod
    def trailing_stop(
        current_price: float,
        direction: Direction,
        highest_since_entry: float,
        lowest_since_entry: float,
        atr: float,
        multiplier: float = TRAILING_STOP_ATR_MULTIPLIER,
    ) -> float:
        """Calculate trailing stop level.

        For LONG:  trailing_sl = highest_price - ATR * multiplier
        For SHORT: trailing_sl = lowest_price + ATR * multiplier
        Trailing stop only moves in the favorable direction.
        """
        trail_distance = atr * multiplier

        if direction == Direction.LONG:
            return highest_since_entry - trail_distance
        else:
            return lowest_since_entry + trail_distance

    @staticmethod
    def should_move_to_breakeven(
        entry: float,
        current_sl: float,
        direction: Direction,
        tp1_hit: bool,
    ) -> float | None:
        """Check if SL should be moved to breakeven after TP1 hit.

        Returns new SL if it should be moved, None otherwise.
        """
        if not tp1_hit:
            return None

        # Only move if breakeven is more protective than current SL
        if direction == Direction.LONG:
            if entry > current_sl:
                return entry
        else:
            if entry < current_sl:
                return entry

        return None

    @staticmethod
    def _cap_sl_distance(
        entry: float,
        sl: float,
        direction: Direction,
    ) -> float:
        """Cap SL distance at MAX_SL_PERCENT of entry."""
        max_distance = entry * MAX_SL_PERCENT

        if direction == Direction.LONG:
            min_sl = entry - max_distance
            return max(sl, min_sl)
        else:
            max_sl = entry + max_distance
            return min(sl, max_sl)

    @staticmethod
    def _percentage_fallback(
        entry: float,
        direction: Direction,
    ) -> tuple[float, StopLossType]:
        """Fallback SL using MAX_SL_PERCENT."""
        distance = entry * MAX_SL_PERCENT
        if direction == Direction.LONG:
            sl = entry - distance
        else:
            sl = entry + distance
        return sl, StopLossType.PERCENTAGE
