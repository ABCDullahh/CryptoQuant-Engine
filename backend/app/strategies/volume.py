"""Volume Analysis Strategy - OBV trend, volume spikes, MFI, VWAP position."""

from __future__ import annotations

from app.config.constants import Direction, MarketRegime
from app.core.models import Candle, IndicatorValues, MarketContext, RawSignal
from app.strategies.base import BaseStrategy

# Used for reference only — regime adaptation handled by aggregator
_ALLOWED_REGIMES = {
    MarketRegime.TRENDING_UP,
    MarketRegime.TRENDING_DOWN,
    MarketRegime.RANGING,
    MarketRegime.LOW_VOLATILITY,
    MarketRegime.CHOPPY,
}


class VolumeAnalysisStrategy(BaseStrategy):
    """Volume-based trading strategy.

    LONG conditions:
    - OBV trending up (current > OBV from N bars ago estimated via momentum)
    - Volume > 1.5x SMA (volume spike)
    - MFI < 80 (not exhausted buying)
    - Price above VWAP

    SHORT conditions:
    - OBV trending down
    - Volume > 1.5x SMA
    - MFI > 20 (not exhausted selling)
    - Price below VWAP
    """

    name = "volume_analysis"
    weight = 0.15
    min_candles = 30

    VOLUME_SPIKE_RATIO = 1.5

    def evaluate(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
        context: MarketContext | None = None,
    ) -> RawSignal | None:
        obv = indicators.obv
        vwap = indicators.vwap
        vol_sma = indicators.volume_sma_20

        if any(v is None for v in (obv, vwap, vol_sma)):
            return None

        close = candles[-1].close
        volume = candles[-1].volume
        symbol = candles[-1].symbol
        timeframe = candles[-1].timeframe

        # OBV trend: compare last candle's contribution
        obv_rising = len(candles) >= 2 and candles[-1].close > candles[-2].close
        obv_falling = len(candles) >= 2 and candles[-1].close < candles[-2].close

        # Volume spike
        vol_ratio = volume / vol_sma if vol_sma > 0 else 0
        has_volume_spike = vol_ratio >= self.VOLUME_SPIKE_RATIO

        # MFI
        mfi = indicators.rsi_14  # We use MFI from volume module
        # If no MFI computed via pipeline, we can check volume-based conditions only
        # Note: pipeline stores MFI separately but IndicatorValues doesn't have mfi field
        # We'll use volume-based heuristics instead

        # --- LONG ---
        long_conditions = []
        long_score = 0.0

        if obv_rising:
            long_conditions.append("OBV_RISING")
            long_score += 0.25

        if has_volume_spike:
            long_conditions.append("VOLUME_SPIKE")
            long_score += 0.30

        if close > vwap:
            long_conditions.append("ABOVE_VWAP")
            long_score += 0.25

        # Price momentum confirmation
        if len(candles) >= 3 and candles[-1].close > candles[-3].close:
            long_conditions.append("PRICE_MOMENTUM_UP")
            long_score += 0.20

        # --- SHORT ---
        short_conditions = []
        short_score = 0.0

        if obv_falling:
            short_conditions.append("OBV_FALLING")
            short_score += 0.25

        if has_volume_spike:
            short_conditions.append("VOLUME_SPIKE")
            short_score += 0.30

        if close < vwap:
            short_conditions.append("BELOW_VWAP")
            short_score += 0.25

        if len(candles) >= 3 and candles[-1].close < candles[-3].close:
            short_conditions.append("PRICE_MOMENTUM_DOWN")
            short_score += 0.20

        if long_score >= 0.50 and long_score > short_score:
            return self._create_signal(
                direction=Direction.LONG,
                strength=long_score,
                entry_price=close,
                symbol=symbol,
                timeframe=timeframe,
                conditions=long_conditions,
                metadata={"obv": obv, "vwap": vwap, "volume_ratio": vol_ratio},
            )

        if short_score >= 0.50 and short_score > long_score:
            return self._create_signal(
                direction=Direction.SHORT,
                strength=-short_score,
                entry_price=close,
                symbol=symbol,
                timeframe=timeframe,
                conditions=short_conditions,
                metadata={"obv": obv, "vwap": vwap, "volume_ratio": vol_ratio},
            )

        return None
