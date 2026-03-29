"""Market Regime Detection - classifies current market state."""

from __future__ import annotations

import numpy as np

from app.config.constants import MarketRegime
from app.core.models import Candle, IndicatorValues, MarketContext


class MarketRegimeDetector:
    """Detects current market regime from indicators and price action.

    Regimes:
    - TRENDING_UP: ADX > 25, EMA alignment up, close > EMAs
    - TRENDING_DOWN: ADX > 25, EMA alignment down, close < EMAs
    - RANGING: ADX < 20, price within BB, low volatility
    - HIGH_VOLATILITY: BB width expanding, ATR spike
    - LOW_VOLATILITY: BB width contracting, ATR low
    - CHOPPY: Mixed signals, no clear direction
    """

    # ADX thresholds
    ADX_TRENDING = 25.0
    ADX_WEAK = 20.0

    # BB width percentiles (relative thresholds)
    BB_WIDTH_HIGH = 0.04  # > 4% of price = high vol
    BB_WIDTH_LOW = 0.015  # < 1.5% of price = low vol

    def detect(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
    ) -> MarketContext:
        """Classify current market regime."""
        regime = self._classify_regime(candles, indicators)
        trend_dir = self._detect_trend_direction(indicators)
        volatility = self._classify_volatility(indicators)
        volume_profile = self._classify_volume(candles, indicators)

        return MarketContext(
            regime=regime,
            trend_1h=trend_dir,
            volatility=volatility,
            volume_profile=volume_profile,
        )

    def _classify_regime(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
    ) -> MarketRegime:
        """Determine the primary market regime."""
        adx = indicators.adx
        bb_width = indicators.bb_width
        ema_9 = indicators.ema_9
        ema_21 = indicators.ema_21
        ema_55 = indicators.ema_55

        close = candles[-1].close if candles else 0

        # High volatility check first
        if bb_width is not None and bb_width > self.BB_WIDTH_HIGH:
            return MarketRegime.HIGH_VOLATILITY

        # Low volatility
        if bb_width is not None and bb_width < self.BB_WIDTH_LOW:
            return MarketRegime.LOW_VOLATILITY

        # Strong trend
        if adx is not None and adx >= self.ADX_TRENDING:
            if ema_9 is not None and ema_21 is not None:
                if ema_9 > ema_21:
                    return MarketRegime.TRENDING_UP
                elif ema_9 < ema_21:
                    return MarketRegime.TRENDING_DOWN

            # ADX strong but no clear EMA alignment
            return MarketRegime.CHOPPY

        # Weak ADX = ranging or choppy
        if adx is not None and adx < self.ADX_WEAK:
            return MarketRegime.RANGING

        # Middle ground: choppy
        return MarketRegime.CHOPPY

    def _detect_trend_direction(self, indicators: IndicatorValues) -> str:
        """Classify trend direction from EMAs."""
        ema_9 = indicators.ema_9
        ema_21 = indicators.ema_21
        ema_55 = indicators.ema_55

        if ema_9 is None or ema_21 is None:
            return "NEUTRAL"

        if ema_55 is not None:
            if ema_9 > ema_21 > ema_55:
                return "STRONG_UP"
            if ema_9 < ema_21 < ema_55:
                return "STRONG_DOWN"

        if ema_9 > ema_21:
            return "UP"
        if ema_9 < ema_21:
            return "DOWN"

        return "NEUTRAL"

    def _classify_volatility(self, indicators: IndicatorValues) -> str:
        """Classify volatility level."""
        bb_width = indicators.bb_width
        atr = indicators.atr_14

        if bb_width is None:
            return "MEDIUM"

        if bb_width > self.BB_WIDTH_HIGH:
            return "HIGH"
        if bb_width < self.BB_WIDTH_LOW:
            return "LOW"
        return "MEDIUM"

    def _classify_volume(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
    ) -> str:
        """Classify volume relative to average."""
        vol_sma = indicators.volume_sma_20
        if vol_sma is None or vol_sma == 0 or not candles:
            return "AVERAGE"

        current_vol = candles[-1].volume
        ratio = current_vol / vol_sma

        if ratio > 2.0:
            return "VERY_HIGH"
        if ratio > 1.5:
            return "HIGH"
        if ratio < 0.5:
            return "LOW"
        return "AVERAGE"
