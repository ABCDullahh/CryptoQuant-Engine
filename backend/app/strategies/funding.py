"""Funding Arbitrage Strategy - trade against extreme funding rates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config.constants import Direction
from app.core.models import Candle, IndicatorValues, MarketContext, RawSignal
from app.strategies.base import BaseStrategy

if TYPE_CHECKING:
    from app.data.collector import DataCollector


class FundingArbStrategy(BaseStrategy):
    """Funding rate arbitrage / mean-reversion strategy.

    Uses extreme funding rates as contrarian signals:
    - Very negative funding (< -0.01%) → market overleveraged short → LONG
    - Very positive funding (> 0.03%) → market overleveraged long → SHORT

    Lower weight (0.05) since funding alone isn't enough for a trade.
    """

    name = "funding_arb"
    weight = 0.05
    min_candles = 20

    # Funding rate thresholds
    EXTREME_NEGATIVE = -0.0001  # -0.01%
    EXTREME_POSITIVE = 0.0003   # +0.03%
    VERY_EXTREME_NEGATIVE = -0.0005  # -0.05%
    VERY_EXTREME_POSITIVE = 0.001    # +0.1%

    def __init__(self) -> None:
        super().__init__()
        self._last_funding_rate: float | None = None

    async def prepare(
        self,
        collector: DataCollector,
        symbol: str,
    ) -> None:
        """Pre-fetch funding rate so evaluate() has data."""
        funding_data = await collector.get_funding_rate(symbol)
        self._last_funding_rate = funding_data.rate if funding_data else None

    def evaluate(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
        context: MarketContext | None = None,
    ) -> RawSignal | None:
        """Evaluate using funding rate data.

        Reads funding rate from self._last_funding_rate which is set
        by analyze() after fetching from the collector.
        """
        funding_rate = self._last_funding_rate
        if funding_rate is None:
            return None

        close = candles[-1].close
        symbol = candles[-1].symbol
        timeframe = candles[-1].timeframe

        rsi = indicators.rsi_14
        adx = indicators.adx

        # --- LONG: negative funding ---
        long_conditions = []
        long_score = 0.0

        if funding_rate <= self.VERY_EXTREME_NEGATIVE:
            long_conditions.append("VERY_EXTREME_NEGATIVE_FUNDING")
            long_score += 0.50
        elif funding_rate <= self.EXTREME_NEGATIVE:
            long_conditions.append("EXTREME_NEGATIVE_FUNDING")
            long_score += 0.35

        # RSI confirmation
        if rsi is not None and rsi < 40:
            long_conditions.append("RSI_SUPPORTS_LONG")
            long_score += 0.20

        # Trend alignment (if no strong downtrend)
        if adx is not None and adx < 30:
            long_conditions.append("NO_STRONG_TREND")
            long_score += 0.15

        # --- SHORT: positive funding ---
        short_conditions = []
        short_score = 0.0

        if funding_rate >= self.VERY_EXTREME_POSITIVE:
            short_conditions.append("VERY_EXTREME_POSITIVE_FUNDING")
            short_score += 0.50
        elif funding_rate >= self.EXTREME_POSITIVE:
            short_conditions.append("EXTREME_POSITIVE_FUNDING")
            short_score += 0.35

        if rsi is not None and rsi > 60:
            short_conditions.append("RSI_SUPPORTS_SHORT")
            short_score += 0.20

        if adx is not None and adx < 30:
            short_conditions.append("NO_STRONG_TREND")
            short_score += 0.15

        if long_score >= 0.35 and long_score > short_score:
            return self._create_signal(
                direction=Direction.LONG,
                strength=min(long_score, 1.0),
                entry_price=close,
                symbol=symbol,
                timeframe=timeframe,
                conditions=long_conditions,
                metadata={"funding_rate": funding_rate, "rsi": rsi},
            )

        if short_score >= 0.35 and short_score > long_score:
            return self._create_signal(
                direction=Direction.SHORT,
                strength=-min(short_score, 1.0),
                entry_price=close,
                symbol=symbol,
                timeframe=timeframe,
                conditions=short_conditions,
                metadata={"funding_rate": funding_rate, "rsi": rsi},
            )

        return None

    async def analyze(
        self,
        collector: DataCollector,
        symbol: str,
        timeframe: str,
    ) -> RawSignal | None:
        """Override to also fetch funding rate from collector."""
        candles = await collector.get_candles(symbol, timeframe, limit=max(self.min_candles, 200))
        if len(candles) < self.min_candles:
            return None

        indicators = self._pipeline.compute(candles)

        funding_data = await collector.get_funding_rate(symbol)
        self._last_funding_rate = funding_data.rate if funding_data else None

        return self.evaluate(candles, indicators)
