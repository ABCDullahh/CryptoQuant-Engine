"""Entry scorer — scores zone entry setups using 3 entry modes + 5 confirmations.

Scoring breakdown:
  Entry modes (pick highest applicable):
    TOUCH_ZONE      +0.15   price enters zone and closes outside
    REJECTION_CANDLE +0.25  pin bar / engulfing / doji inside zone
    BREAK_RETEST    +0.30   break above/below zone then pullback

  Confirmation factors (all additive):
    MTF_ALIGNED     +0.20   HTF trend aligns with zone direction
    VOLUME_SPIKE    +0.15   volume >= 1.5x SMA-20
    RSI_DIVERGENCE  +0.20   price vs RSI divergence
    BODY_RATIO      +0.10   rejection wick >= 60% of candle range
    ZONE_FRESH      +0.10   zone.touch_count == 0
    ZONE_TESTED_1   +0.05   zone.touch_count == 1

  Total is capped at 1.0.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config.constants import (
    OB_ZONE_BODY_RATIO,
    OB_ZONE_RSI_DIV_LOOKBACK,
    OB_ZONE_VOLUME_THRESHOLD,
)
from app.zones.models import ZoneType

if TYPE_CHECKING:
    from app.core.models import Candle
    from app.zones.models import Zone


class EntryScorer:
    """Scores a candle's entry setup relative to a supply/demand zone."""

    # Entry mode scores
    _TOUCH_SCORE = 0.15
    _REJECTION_SCORE = 0.25
    _BREAK_RETEST_SCORE = 0.30

    # Confirmation scores
    _MTF_SCORE = 0.20
    _VOLUME_SPIKE_SCORE = 0.15
    _RSI_DIV_SCORE = 0.20
    _BODY_RATIO_SCORE = 0.10
    _ZONE_FRESH_SCORE = 0.10
    _ZONE_TESTED_1_SCORE = 0.05

    def score(
        self,
        candle: Candle,
        zone: Zone,
        indicators: object,
        htf_trend: str,
        recent_candles: list[Candle],
    ) -> tuple[float, list[str]]:
        """Return ``(score, conditions_met)`` for a zone entry setup.

        Parameters
        ----------
        candle:
            The current (closed) candle to evaluate.
        zone:
            The supply or demand zone under test.
        indicators:
            Object exposing ``.rsi_14``, ``.atr_14``, ``.volume_sma_20``,
            ``.ema_9``, ``.ema_21``, ``.ema_55``.
        htf_trend:
            Higher-timeframe trend — ``"bullish"``, ``"bearish"``, or
            ``"neutral"``.
        recent_candles:
            Last 5–10 closed candles for pattern / divergence detection.
        """
        total = 0.0
        conditions: list[str] = []

        # --- Entry mode (pick highest applicable) --------------------------
        entry_score, entry_name = self._best_entry_mode(
            candle, zone, recent_candles,
        )
        if entry_name:
            total += entry_score
            conditions.append(entry_name)

        # --- Confirmations (all additive) ----------------------------------
        conf_score, conf_names = self._confirmations(
            candle, zone, indicators, htf_trend, recent_candles,
        )
        total += conf_score
        conditions.extend(conf_names)

        return min(total, 1.0), conditions

    # ------------------------------------------------------------------ #
    # Entry modes                                                         #
    # ------------------------------------------------------------------ #

    def _best_entry_mode(
        self,
        candle: Candle,
        zone: Zone,
        recent_candles: list[Candle],
    ) -> tuple[float, str | None]:
        """Return (score, name) of the highest-scoring applicable entry mode."""
        candidates: list[tuple[float, str]] = []

        if self._is_break_retest(candle, zone, recent_candles):
            candidates.append((self._BREAK_RETEST_SCORE, "BREAK_RETEST"))

        if self._is_rejection_candle(candle, zone):
            candidates.append((self._REJECTION_SCORE, "REJECTION_CANDLE"))

        if self._is_touch_zone(candle, zone):
            candidates.append((self._TOUCH_SCORE, "TOUCH_ZONE"))

        if candidates:
            return max(candidates, key=lambda t: t[0])
        return 0.0, None

    # -- Touch zone --------------------------------------------------------

    @staticmethod
    def _is_touch_zone(candle: Candle, zone: Zone) -> bool:
        if zone.type == ZoneType.DEMAND:
            return candle.low <= zone.top and candle.close > zone.top
        # SUPPLY
        return candle.high >= zone.bottom and candle.close < zone.bottom

    # -- Rejection candle --------------------------------------------------

    @staticmethod
    def _is_rejection_candle(candle: Candle, zone: Zone) -> bool:
        rng = candle.high - candle.low
        if rng <= 0:
            return False

        body_top = max(candle.open, candle.close)
        body_bot = min(candle.open, candle.close)
        body = body_top - body_bot

        # Pin bar: relevant wick >= 60% of range
        if zone.type == ZoneType.DEMAND:
            lower_wick = body_bot - candle.low
            wick_ratio = lower_wick / rng
            in_zone = candle.low <= zone.top
        else:
            upper_wick = candle.high - body_top
            wick_ratio = upper_wick / rng
            in_zone = candle.high >= zone.bottom

        if wick_ratio >= OB_ZONE_BODY_RATIO and in_zone:
            return True

        # Engulfing: body covers > 70% of range and is inside zone
        if body / rng > 0.70 and zone.bottom <= candle.low and candle.high <= zone.top:
            return True

        # Doji: body <= 10% of range and inside zone
        if body / rng <= 0.10 and in_zone:
            return True

        return False

    # -- Break & retest ----------------------------------------------------

    @staticmethod
    def _is_break_retest(
        candle: Candle,
        zone: Zone,
        recent_candles: list[Candle],
    ) -> bool:
        if len(recent_candles) < 2:
            return False

        if zone.type == ZoneType.DEMAND:
            # Was below zone, broke above, now pulling back into zone
            was_below = any(c.close < zone.bottom for c in recent_candles)
            broke_above = any(c.close > zone.top for c in recent_candles)
            pullback_into = candle.low <= zone.top and candle.close >= zone.bottom
            return was_below and broke_above and pullback_into

        # SUPPLY: was above zone, broke below, now pulling back into zone
        was_above = any(c.close > zone.top for c in recent_candles)
        broke_below = any(c.close < zone.bottom for c in recent_candles)
        pullback_into = candle.high >= zone.bottom and candle.close <= zone.top
        return was_above and broke_below and pullback_into

    # ------------------------------------------------------------------ #
    # Confirmation factors                                                #
    # ------------------------------------------------------------------ #

    def _confirmations(
        self,
        candle: Candle,
        zone: Zone,
        indicators: object,
        htf_trend: str,
        recent_candles: list[Candle],
    ) -> tuple[float, list[str]]:
        total = 0.0
        names: list[str] = []

        # MTF aligned
        if self._is_mtf_aligned(zone, htf_trend):
            total += self._MTF_SCORE
            names.append("MTF_ALIGNED")

        # Volume spike
        vol_sma = getattr(indicators, "volume_sma_20", None)
        if vol_sma and vol_sma > 0:
            if candle.volume >= OB_ZONE_VOLUME_THRESHOLD * vol_sma:
                total += self._VOLUME_SPIKE_SCORE
                names.append("VOLUME_SPIKE")

        # RSI divergence
        if self._has_rsi_divergence(candle, zone, indicators, recent_candles):
            total += self._RSI_DIV_SCORE
            names.append("RSI_DIVERGENCE")

        # Body ratio (rejection wick)
        if self._has_body_ratio(candle, zone):
            total += self._BODY_RATIO_SCORE
            names.append("BODY_RATIO")

        # Zone freshness
        if zone.touch_count == 0:
            total += self._ZONE_FRESH_SCORE
            names.append("ZONE_FRESH")
        elif zone.touch_count == 1:
            total += self._ZONE_TESTED_1_SCORE
            names.append("ZONE_TESTED_1")

        return total, names

    # -- MTF aligned -------------------------------------------------------

    @staticmethod
    def _is_mtf_aligned(zone: Zone, htf_trend: str) -> bool:
        if zone.type == ZoneType.DEMAND and htf_trend == "bullish":
            return True
        if zone.type == ZoneType.SUPPLY and htf_trend == "bearish":
            return True
        return False

    # -- Body ratio --------------------------------------------------------

    @staticmethod
    def _has_body_ratio(candle: Candle, zone: Zone) -> bool:
        rng = candle.high - candle.low
        if rng <= 0:
            return False

        body_top = max(candle.open, candle.close)
        body_bot = min(candle.open, candle.close)

        if zone.type == ZoneType.DEMAND:
            lower_wick = body_bot - candle.low
            return (lower_wick / rng) >= OB_ZONE_BODY_RATIO
        # SUPPLY
        upper_wick = candle.high - body_top
        return (upper_wick / rng) >= OB_ZONE_BODY_RATIO

    # -- RSI divergence ----------------------------------------------------

    @staticmethod
    def _has_rsi_divergence(
        candle: Candle,
        zone: Zone,
        indicators: object,
        recent_candles: list[Candle],
    ) -> bool:
        """Simple slope-comparison divergence over last N candles.

        For DEMAND: price making lower lows but RSI making higher lows.
        For SUPPLY: price making higher highs but RSI making lower highs.
        """
        lookback = OB_ZONE_RSI_DIV_LOOKBACK
        if len(recent_candles) < 2:
            return False

        candles = recent_candles[-lookback:]
        if len(candles) < 2:
            return False

        current_rsi = getattr(indicators, "rsi_14", None)
        if current_rsi is None:
            return False

        # Use price lows for demand, highs for supply
        if zone.type == ZoneType.DEMAND:
            first_low = candles[0].low
            last_low = candles[-1].low
            price_slope_down = last_low < first_low
            # For RSI: assume RSI improved (higher) if current RSI is above middle-ish
            # A proper implementation would track per-candle RSI; we approximate
            # by comparing first half avg low vs second half avg low of the candles.
            half = len(candles) // 2
            first_half_avg = sum(c.low for c in candles[:half]) / max(half, 1)
            second_half_avg = sum(c.low for c in candles[half:]) / max(len(candles) - half, 1)
            price_lower_lows = second_half_avg < first_half_avg
            # RSI divergence: current RSI is above oversold but price still falling
            rsi_rising = current_rsi > 30  # not deeply oversold = RSI recovering
            return price_lower_lows and rsi_rising and current_rsi < 50

        # SUPPLY: higher highs on price, lower highs on RSI
        first_high = candles[0].high
        last_high = candles[-1].high
        half = len(candles) // 2
        first_half_avg = sum(c.high for c in candles[:half]) / max(half, 1)
        second_half_avg = sum(c.high for c in candles[half:]) / max(len(candles) - half, 1)
        price_higher_highs = second_half_avg > first_half_avg
        rsi_falling = current_rsi < 70 and current_rsi > 50
        return price_higher_highs and rsi_falling
