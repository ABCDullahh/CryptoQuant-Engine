"""Momentum Strategy - trend-following using EMA crossovers, RSI, MACD, ADX."""

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


class MomentumStrategy(BaseStrategy):
    """Trend-following momentum strategy.

    LONG conditions:
    - EMA9 > EMA21 > EMA55 (aligned uptrend)
    - RSI between 40-70 (not overbought)
    - MACD histogram positive
    - ADX > 25 (trend has strength)

    SHORT conditions:
    - EMA9 < EMA21 < EMA55 (aligned downtrend)
    - RSI between 30-60 (not oversold)
    - MACD histogram negative
    - ADX > 25 (trend has strength)
    """

    name = "momentum"
    weight = 0.15
    min_candles = 55

    def evaluate(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
        context: MarketContext | None = None,
    ) -> RawSignal | None:
        ema9 = indicators.ema_9
        ema21 = indicators.ema_21
        ema55 = indicators.ema_55
        rsi = indicators.rsi_14
        macd_hist = indicators.macd_histogram
        adx = indicators.adx

        # Need all core indicators
        if any(v is None for v in (ema9, ema21, ema55, rsi, macd_hist)):
            return None

        entry_price = candles[-1].close
        symbol = candles[-1].symbol
        timeframe = candles[-1].timeframe

        # Check for LONG
        long_conditions = []
        long_score = 0.0

        if ema9 > ema21 > ema55:
            long_conditions.append("EMA_ALIGNED_UP")
            long_score += 0.30

        if 40 <= rsi <= 70:
            long_conditions.append("RSI_HEALTHY")
            long_score += 0.20

        if macd_hist > 0:
            long_conditions.append("MACD_POSITIVE")
            long_score += 0.25

        if adx is not None and adx > 25:
            long_conditions.append("ADX_STRONG")
            long_score += 0.25

        # Check for SHORT
        short_conditions = []
        short_score = 0.0

        if ema9 < ema21 < ema55:
            short_conditions.append("EMA_ALIGNED_DOWN")
            short_score += 0.30

        if 30 <= rsi <= 60:
            short_conditions.append("RSI_HEALTHY")
            short_score += 0.20

        if macd_hist < 0:
            short_conditions.append("MACD_NEGATIVE")
            short_score += 0.25

        if adx is not None and adx > 25:
            short_conditions.append("ADX_STRONG")
            short_score += 0.25

        # Need at least 2 conditions met for a signal
        if long_score >= 0.50 and long_score > short_score:
            return self._create_signal(
                direction=Direction.LONG,
                strength=long_score,
                entry_price=entry_price,
                symbol=symbol,
                timeframe=timeframe,
                conditions=long_conditions,
                metadata={"rsi": rsi, "adx": adx, "macd_hist": macd_hist},
            )

        if short_score >= 0.50 and short_score > long_score:
            return self._create_signal(
                direction=Direction.SHORT,
                strength=-short_score,
                entry_price=entry_price,
                symbol=symbol,
                timeframe=timeframe,
                conditions=short_conditions,
                metadata={"rsi": rsi, "adx": adx, "macd_hist": macd_hist},
            )

        return None
