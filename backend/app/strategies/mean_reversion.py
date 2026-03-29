"""Mean Reversion Strategy - Bollinger Bands + RSI extremes + volume confirmation."""

from __future__ import annotations

from app.config.constants import Direction, MarketRegime
from app.core.models import Candle, IndicatorValues, MarketContext, RawSignal
from app.strategies.base import BaseStrategy

# Used for reference only — regime adaptation handled by aggregator
_ALLOWED_REGIMES = {MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY}


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy using Bollinger Bands and RSI.

    LONG conditions:
    - Price near or below lower Bollinger Band
    - RSI < 30 (oversold)
    - Volume above average (confirms selling exhaustion)

    SHORT conditions:
    - Price near or above upper Bollinger Band
    - RSI > 70 (overbought)
    - Volume above average (confirms buying exhaustion)
    """

    name = "mean_reversion"
    weight = 0.10
    min_candles = 30

    # Distance from BB threshold (as fraction of BB width)
    BB_PROXIMITY = 0.1

    def evaluate(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
        context: MarketContext | None = None,
    ) -> RawSignal | None:
        bb_upper = indicators.bb_upper
        bb_lower = indicators.bb_lower
        bb_middle = indicators.bb_middle
        rsi = indicators.rsi_14
        vol_sma = indicators.volume_sma_20

        if any(v is None for v in (bb_upper, bb_lower, bb_middle, rsi)):
            return None

        close = candles[-1].close
        volume = candles[-1].volume
        symbol = candles[-1].symbol
        timeframe = candles[-1].timeframe
        bb_width = bb_upper - bb_lower

        if bb_width <= 0:
            return None

        # Position relative to BB (0 = lower, 1 = upper)
        bb_position = (close - bb_lower) / bb_width

        # Volume confirmation
        vol_ratio = volume / vol_sma if vol_sma and vol_sma > 0 else 1.0
        has_volume = vol_ratio >= 1.0

        # --- LONG: oversold ---
        long_conditions = []
        long_score = 0.0

        if bb_position <= self.BB_PROXIMITY:
            long_conditions.append("BELOW_LOWER_BB")
            long_score += 0.35
        elif bb_position <= 0.25:
            long_conditions.append("NEAR_LOWER_BB")
            long_score += 0.20

        if rsi < 25:
            long_conditions.append("RSI_EXTREME_OVERSOLD")
            long_score += 0.35
        elif rsi < 30:
            long_conditions.append("RSI_OVERSOLD")
            long_score += 0.25

        if has_volume:
            long_conditions.append("VOLUME_CONFIRMED")
            long_score += 0.15

        # --- SHORT: overbought ---
        short_conditions = []
        short_score = 0.0

        if bb_position >= (1.0 - self.BB_PROXIMITY):
            short_conditions.append("ABOVE_UPPER_BB")
            short_score += 0.35
        elif bb_position >= 0.75:
            short_conditions.append("NEAR_UPPER_BB")
            short_score += 0.20

        if rsi > 75:
            short_conditions.append("RSI_EXTREME_OVERBOUGHT")
            short_score += 0.35
        elif rsi > 70:
            short_conditions.append("RSI_OVERBOUGHT")
            short_score += 0.25

        if has_volume:
            short_conditions.append("VOLUME_CONFIRMED")
            short_score += 0.15

        # Need at least 0.50 score
        if long_score >= 0.50 and long_score > short_score:
            return self._create_signal(
                direction=Direction.LONG,
                strength=long_score,
                entry_price=close,
                symbol=symbol,
                timeframe=timeframe,
                conditions=long_conditions,
                metadata={
                    "rsi": rsi, "bb_position": bb_position,
                    "volume_ratio": vol_ratio,
                },
            )

        if short_score >= 0.50 and short_score > long_score:
            return self._create_signal(
                direction=Direction.SHORT,
                strength=-short_score,
                entry_price=close,
                symbol=symbol,
                timeframe=timeframe,
                conditions=short_conditions,
                metadata={
                    "rsi": rsi, "bb_position": bb_position,
                    "volume_ratio": vol_ratio,
                },
            )

        return None
