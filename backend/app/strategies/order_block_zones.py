"""Order Block Zones Strategy — zone-based entry/exit using supply/demand zones.

Detects supply/demand zones via ZoneDetector, scores entries via EntryScorer,
and generates signals with zone-aware SL/TP placement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.config.constants import (
    HIGHER_TF_MAP,
    OB_ZONE_MAX_DISTANCE_ATR,
    OB_ZONE_MIN_RR,
    OB_ZONE_MIN_SCORE,
    OB_ZONE_SL_ATR_MULT,
    OB_ZONE_SL_MIN_PCT,
    OB_ZONE_WEIGHT,
    Direction,
)
from app.core.models import Candle, IndicatorValues, MarketContext, RawSignal
from app.strategies.base import BaseStrategy
from app.zones.detector import ZoneDetector
from app.zones.models import ZoneType
from app.zones.scorer import EntryScorer

if TYPE_CHECKING:
    from app.data.collector import DataCollector

logger = structlog.get_logger(__name__)


class OrderBlockZonesStrategy(BaseStrategy):
    """Zone-based entry/exit strategy using supply/demand order blocks.

    Uses ZoneDetector for zone identification and EntryScorer for
    multi-factor entry scoring. Includes HTF trend alignment via
    async prepare() pre-fetch.
    """

    name = "ob_zones"
    weight = OB_ZONE_WEIGHT  # 0.20
    min_candles = 100

    def __init__(self) -> None:
        super().__init__()
        self._detector = ZoneDetector()
        self._scorer = EntryScorer()
        self._htf_trend: str = "neutral"
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Async pre-fetch
    # ------------------------------------------------------------------

    async def prepare(
        self,
        collector: DataCollector,
        symbol: str,
    ) -> None:
        """Pre-fetch HTF candles and compute EMA alignment trend."""
        # Determine current timeframe from last candle if available
        # Default to "1h" if no context
        timeframe = "1h"
        htf = HIGHER_TF_MAP.get(timeframe, "4h")

        try:
            htf_candles = await collector.get_candles(symbol, htf, limit=100)
            self._htf_trend = self._compute_htf_trend(htf_candles)
        except Exception:
            logger.error(
                "ob_zones_prepare_failed",
                symbol=symbol,
                error="failed to fetch HTF candles",
            )
            self._htf_trend = "neutral"

    @staticmethod
    def _compute_htf_trend(candles: list[Candle]) -> str:
        """Compute simple EMA alignment from HTF candles.

        EMA9 > EMA21 > EMA55 -> "bullish"
        EMA9 < EMA21 < EMA55 -> "bearish"
        Otherwise -> "neutral"
        """
        if len(candles) < 55:
            return "neutral"

        closes = [c.close for c in candles]

        ema9 = _ema(closes, 9)
        ema21 = _ema(closes, 21)
        ema55 = _ema(closes, 55)

        if ema9 > ema21 > ema55:
            return "bullish"
        if ema9 < ema21 < ema55:
            return "bearish"
        return "neutral"

    # ------------------------------------------------------------------
    # Main evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
        context: MarketContext | None = None,
    ) -> RawSignal | None:
        """Evaluate zone-based entry using current candles and indicators."""
        # Guard: insufficient data
        if len(candles) < self.min_candles:
            return None

        current = candles[-1]
        price = current.close
        symbol = current.symbol
        timeframe = current.timeframe

        atr = getattr(indicators, "atr_14", None) or 0.0
        if atr <= 0:
            return None

        # Initialize or update detector
        if not self._initialized:
            self._detector.initialize(candles)
            self._initialized = True
        else:
            self._detector.update(current)

        # Get active zones
        active_zones = self._detector.get_active_zones()
        if not active_zones:
            return None

        # Filter zones within max distance
        max_distance = OB_ZONE_MAX_DISTANCE_ATR * atr
        nearby_zones = [
            z for z in active_zones
            if abs(z.midpoint - price) <= max_distance
        ]
        if not nearby_zones:
            return None

        # Check for ambiguous overlapping supply + demand zones near price
        nearby_demand = [z for z in nearby_zones if z.type == ZoneType.DEMAND]
        nearby_supply = [z for z in nearby_zones if z.type == ZoneType.SUPPLY]

        # Ambiguous: both supply and demand zones overlap the current price
        demand_overlaps = any(z.contains(price) for z in nearby_demand)
        supply_overlaps = any(z.contains(price) for z in nearby_supply)
        if demand_overlaps and supply_overlaps:
            return None

        # Score each candidate zone and pick the best
        recent_candles = candles[-10:]
        best_zone = None
        best_score = 0.0
        best_conditions: list[str] = []

        for zone in nearby_zones:
            score, conditions = self._scorer.score(
                current, zone, indicators, self._htf_trend, recent_candles,
            )
            if score >= OB_ZONE_MIN_SCORE and score > best_score:
                best_zone = zone
                best_score = score
                best_conditions = conditions

        if best_zone is None:
            return None

        # Determine direction
        if best_zone.type == ZoneType.DEMAND:
            direction = Direction.LONG
        else:
            direction = Direction.SHORT

        # Calculate SL
        sl_buffer = max(atr * OB_ZONE_SL_ATR_MULT, price * OB_ZONE_SL_MIN_PCT)
        if direction == Direction.LONG:
            stop_loss = best_zone.bottom - sl_buffer
        else:
            stop_loss = best_zone.top + sl_buffer

        # Calculate risk distance
        risk = abs(price - stop_loss)
        if risk <= 0:
            return None

        # Calculate TPs
        tp1 = self._calc_tp1(price, direction, risk, candles, active_zones)
        tp2 = self._calc_tp2(price, direction, risk, active_zones)
        tp3 = self._calc_tp3(price, direction, risk, active_zones)

        # Enforce min R:R on TP1
        tp1_distance = abs(tp1 - price)
        rr = tp1_distance / risk if risk > 0 else 0.0
        if rr < OB_ZONE_MIN_RR:
            return None

        # Strength: positive for LONG, negative for SHORT
        strength = best_score if direction == Direction.LONG else -best_score

        metadata = {
            "zone_type": str(best_zone.type),
            "zone_top": best_zone.top,
            "zone_bottom": best_zone.bottom,
            "stop_loss": stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "zone_score": round(best_score, 4),
            "zone_fresh": best_zone.is_fresh,
            "zone_touch_count": best_zone.touch_count,
            "htf_trend": self._htf_trend,
            "rr_ratio": round(rr, 2),
        }

        return self._create_signal(
            direction=direction,
            strength=strength,
            entry_price=price,
            symbol=symbol,
            timeframe=timeframe,
            conditions=best_conditions,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # TP calculation helpers
    # ------------------------------------------------------------------

    def _calc_tp1(
        self,
        price: float,
        direction: Direction,
        risk: float,
        candles: list[Candle],
        active_zones: list,
    ) -> float:
        """TP1: nearest opposite swing high/low. Fallback: entry +/- risk * 1.5."""
        swing = self._find_nearest_swing(price, direction, candles)
        if swing is not None:
            return swing
        if direction == Direction.LONG:
            return price + risk * 1.5
        return price - risk * 1.5

    def _calc_tp2(
        self,
        price: float,
        direction: Direction,
        risk: float,
        active_zones: list,
    ) -> float:
        """TP2: nearest opposite zone. Fallback: entry +/- risk * 3.0."""
        opp_type = ZoneType.SUPPLY if direction == Direction.LONG else ZoneType.DEMAND
        opp_zones = sorted(
            [z for z in active_zones if z.type == opp_type],
            key=lambda z: abs(z.midpoint - price),
        )
        if opp_zones:
            zone = opp_zones[0]
            if direction == Direction.LONG and zone.midpoint > price:
                return zone.bottom
            if direction == Direction.SHORT and zone.midpoint < price:
                return zone.top
        if direction == Direction.LONG:
            return price + risk * 3.0
        return price - risk * 3.0

    def _calc_tp3(
        self,
        price: float,
        direction: Direction,
        risk: float,
        active_zones: list,
    ) -> float:
        """TP3: next opposite zone beyond TP2. Fallback: entry +/- risk * 5.0."""
        opp_type = ZoneType.SUPPLY if direction == Direction.LONG else ZoneType.DEMAND
        opp_zones = sorted(
            [z for z in active_zones if z.type == opp_type],
            key=lambda z: abs(z.midpoint - price),
        )
        if len(opp_zones) >= 2:
            zone = opp_zones[1]
            if direction == Direction.LONG and zone.midpoint > price:
                return zone.bottom
            if direction == Direction.SHORT and zone.midpoint < price:
                return zone.top
        if direction == Direction.LONG:
            return price + risk * 5.0
        return price - risk * 5.0

    @staticmethod
    def _find_nearest_swing(
        price: float,
        direction: Direction,
        candles: list[Candle],
    ) -> float | None:
        """Find nearest opposite swing high (for LONG) or low (for SHORT)."""
        if len(candles) < 5:
            return None

        lookback = min(50, len(candles))
        recent = candles[-lookback:]

        if direction == Direction.LONG:
            # Find swing highs above price
            swing_highs = []
            for i in range(2, len(recent) - 2):
                if (recent[i].high > recent[i - 1].high
                        and recent[i].high > recent[i - 2].high
                        and recent[i].high > recent[i + 1].high
                        and recent[i].high > recent[i + 2].high
                        and recent[i].high > price):
                    swing_highs.append(recent[i].high)
            if swing_highs:
                return min(swing_highs)  # nearest above
        else:
            # Find swing lows below price
            swing_lows = []
            for i in range(2, len(recent) - 2):
                if (recent[i].low < recent[i - 1].low
                        and recent[i].low < recent[i - 2].low
                        and recent[i].low < recent[i + 1].low
                        and recent[i].low < recent[i + 2].low
                        and recent[i].low < price):
                    swing_lows.append(recent[i].low)
            if swing_lows:
                return max(swing_lows)  # nearest below

        return None


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _ema(values: list[float], period: int) -> float:
    """Compute the final EMA value for a series."""
    if len(values) < period:
        return values[-1] if values else 0.0

    # Seed with SMA
    sma = sum(values[:period]) / period
    multiplier = 2.0 / (period + 1)
    ema_val = sma
    for v in values[period:]:
        ema_val = (v - ema_val) * multiplier + ema_val
    return ema_val
