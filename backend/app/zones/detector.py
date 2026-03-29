"""Zone detector — structure break + volume pivot dual confirmation.

Detects supply/demand zones from price action using:
1. Swing high/low detection (configurable lookback)
2. Structure break detection (BOS / CHoCH)
3. Volume confirmation (volume pivot OR volume spike)
4. Zone lifecycle management (tested / mitigated / expired)
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

import structlog

from app.config.constants import (
    OB_ZONE_ATR_MULT,
    OB_ZONE_LOOKBACK,
    OB_ZONE_MAX_AGE_CANDLES,
    OB_ZONE_VOLUME_THRESHOLD,
)
from app.zones.models import Zone, ZoneEvent, ZoneType

if TYPE_CHECKING:
    from app.core.models import Candle

logger = structlog.get_logger(__name__)


class ZoneDetector:
    """Detect supply/demand zones via structure break + volume pivot confirmation.

    Usage::

        detector = ZoneDetector(lookback=5)
        zones = detector.initialize(historical_candles)   # warm-up
        for new_candle in stream:
            events = detector.update(new_candle)           # incremental O(1)
        active = detector.get_active_zones()
    """

    def __init__(self, lookback: int = OB_ZONE_LOOKBACK) -> None:
        self._lookback = lookback
        self._zones: list[Zone] = []

        # Rolling candle buffer for swing detection (need 2*lookback+1)
        buf_size = lookback * 2 + 1
        self._candle_buffer: deque[Candle] = deque(maxlen=buf_size)

        # Rolling windows for ATR(14) and volume SMA(20)
        self._tr_window: deque[float] = deque(maxlen=14)
        self._volume_window: deque[float] = deque(maxlen=20)

        # Swing tracking
        self._swing_highs: list[tuple[float, int]] = []  # (price, candle_index)
        self._swing_lows: list[tuple[float, int]] = []

        # Structure tracking
        self._structure_trend: str = "neutral"  # "bullish" / "bearish" / "neutral"
        self._last_swing_high: float | None = None
        self._last_swing_low: float | None = None

        # Break tracking — prevent re-triggering on same swing level
        self._last_broken_high: float | None = None
        self._last_broken_low: float | None = None

        # Previous candle (for TR calculation)
        self._prev_candle: Candle | None = None
        self._candle_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def initialize(self, candles: list[Candle]) -> list[Zone]:
        """Warm up with historical data. Returns zones found during warm-up."""
        created: list[Zone] = []
        for candle in candles:
            events = self._process_candle(candle)
            for ev in events:
                if ev.event_type == "created":
                    created.append(ev.zone)
        return created

    def update(self, candle: Candle) -> list[ZoneEvent]:
        """Process a single new candle. Returns events emitted."""
        return self._process_candle(candle)

    def get_active_zones(self) -> list[Zone]:
        """Return non-mitigated zones."""
        return [z for z in self._zones if not z.mitigated]

    def get_nearest_zone(self, price: float, zone_type: ZoneType) -> Zone | None:
        """Return the closest active zone of the given type to *price*."""
        candidates = [
            z for z in self._zones
            if z.type == zone_type and not z.mitigated
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda z: abs(z.midpoint - price))

    # ------------------------------------------------------------------
    # Internal — candle processing pipeline
    # ------------------------------------------------------------------

    def _process_candle(self, candle: Candle) -> list[ZoneEvent]:
        """Full pipeline for one candle: indicators, swings, breaks, lifecycle."""
        events: list[ZoneEvent] = []

        # 1. Update rolling indicators
        self._update_indicators(candle)

        # 2. Add to buffer
        self._candle_buffer.append(candle)
        self._candle_count += 1

        # 3. Detect swing points (need full buffer)
        if len(self._candle_buffer) == self._candle_buffer.maxlen:
            self._detect_swing()

        # 4. Check structure break + zone formation
        creation_events = self._check_structure_break(candle)
        events.extend(creation_events)

        # 5. Check existing zone status (tested / mitigated / expired)
        lifecycle_events = self._check_zone_status(candle)
        events.extend(lifecycle_events)

        self._prev_candle = candle
        return events

    # ------------------------------------------------------------------
    # Indicator maintenance
    # ------------------------------------------------------------------

    def _update_indicators(self, candle: Candle) -> None:
        """Update TR window and volume window."""
        # True Range
        if self._prev_candle is not None:
            tr = max(
                candle.high - candle.low,
                abs(candle.high - self._prev_candle.close),
                abs(candle.low - self._prev_candle.close),
            )
        else:
            tr = candle.high - candle.low
        self._tr_window.append(tr)

        # Volume
        self._volume_window.append(candle.volume)

    @property
    def _atr(self) -> float:
        """Current ATR(14)."""
        if not self._tr_window:
            return 0.0
        return sum(self._tr_window) / len(self._tr_window)

    @property
    def _volume_sma(self) -> float:
        """Current volume SMA(20)."""
        if not self._volume_window:
            return 0.0
        return sum(self._volume_window) / len(self._volume_window)

    # ------------------------------------------------------------------
    # Swing detection
    # ------------------------------------------------------------------

    def _detect_swing(self) -> None:
        """Check if the middle candle of the buffer is a swing high/low."""
        buf = list(self._candle_buffer)
        lb = self._lookback
        mid = lb  # index of middle candle

        mid_candle = buf[mid]
        mid_high = mid_candle.high
        mid_low = mid_candle.low

        # Swing high: mid.high > all neighbours' highs
        is_swing_high = all(
            mid_high > buf[i].high for i in range(len(buf)) if i != mid
        )
        # Swing low: mid.low < all neighbours' lows
        is_swing_low = all(
            mid_low < buf[i].low for i in range(len(buf)) if i != mid
        )

        idx = self._candle_count - lb - 1  # real index of the mid candle

        if is_swing_high:
            self._swing_highs.append((mid_high, idx))
            self._last_swing_high = mid_high
            # New swing high means it can be broken — reset break tracker
            self._last_broken_high = None

        if is_swing_low:
            self._swing_lows.append((mid_low, idx))
            self._last_swing_low = mid_low
            # New swing low means it can be broken — reset break tracker
            self._last_broken_low = None

    # ------------------------------------------------------------------
    # Structure break detection + zone creation
    # ------------------------------------------------------------------

    def _check_structure_break(self, candle: Candle) -> list[ZoneEvent]:
        """Detect BOS / CHoCH and create zones when volume confirms."""
        events: list[ZoneEvent] = []

        if self._last_swing_high is None or self._last_swing_low is None:
            return events

        close = candle.close

        # Only detect a break if this swing level hasn't been broken already
        bullish_break = (
            close > self._last_swing_high
            and self._last_broken_high != self._last_swing_high
        )
        bearish_break = (
            close < self._last_swing_low
            and self._last_broken_low != self._last_swing_low
        )

        if not bullish_break and not bearish_break:
            return events

        # Determine trigger type
        if bullish_break:
            if self._structure_trend == "bearish":
                trigger = "CHoCH"
            else:
                trigger = "BOS"
        else:  # bearish break
            if self._structure_trend == "bullish":
                trigger = "CHoCH"
            else:
                trigger = "BOS"

        # Volume confirmation on the candle BEFORE the break (the OB candle)
        ob_candle = self._prev_candle
        if ob_candle is None:
            return events

        if not self._has_volume_confirmation(ob_candle):
            # Mark as broken even without volume confirmation
            # to prevent re-checking this level
            if bullish_break:
                self._last_broken_high = self._last_swing_high
                self._structure_trend = "bullish"
            else:
                self._last_broken_low = self._last_swing_low
                self._structure_trend = "bearish"
            return events

        # --- Create zone ---
        vol_sma = self._volume_sma
        vol_ratio = ob_candle.volume / vol_sma if vol_sma > 0 else 1.0

        zone_top = ob_candle.high
        zone_bottom = ob_candle.low

        # High-vol candle narrowing: if candle range >= 2x ATR, use body only
        candle_range = ob_candle.high - ob_candle.low
        atr = self._atr
        if atr > 0 and candle_range >= OB_ZONE_ATR_MULT * atr:
            body_top = max(ob_candle.open, ob_candle.close)
            body_bottom = min(ob_candle.open, ob_candle.close)
            zone_top = body_top
            zone_bottom = body_bottom

        # Ensure valid zone
        if zone_top <= zone_bottom:
            zone_top = zone_bottom + atr * 0.1 if atr > 0 else zone_bottom + 1.0

        zone_type = ZoneType.DEMAND if bullish_break else ZoneType.SUPPLY

        zone = Zone(
            type=zone_type,
            top=zone_top,
            bottom=zone_bottom,
            origin_time=ob_candle.time,
            trigger=trigger,
            volume_ratio=vol_ratio,
        )
        self._zones.append(zone)
        events.append(ZoneEvent(event_type="created", zone=zone))

        # Update structure trend and mark this level as broken
        if bullish_break:
            self._structure_trend = "bullish"
            self._last_broken_high = self._last_swing_high
        else:
            self._structure_trend = "bearish"
            self._last_broken_low = self._last_swing_low

        logger.debug(
            "zone_created",
            zone_type=zone_type,
            trigger=trigger,
            top=zone_top,
            bottom=zone_bottom,
            volume_ratio=round(vol_ratio, 2),
        )

        return events

    def _has_volume_confirmation(self, candle: Candle) -> bool:
        """Check if candle has volume pivot OR volume spike."""
        # Volume spike: volume >= threshold * SMA(20)
        vol_sma = self._volume_sma
        if vol_sma > 0 and candle.volume >= OB_ZONE_VOLUME_THRESHOLD * vol_sma:
            return True

        # Volume pivot: candle volume > all neighbours in buffer
        if len(self._candle_buffer) >= 3:
            buf = list(self._candle_buffer)
            # The OB candle is the second-to-last in the buffer
            # (buffer was already appended with the break candle)
            for i in range(len(buf) - 1):
                if buf[i].volume == candle.volume and buf[i].time == candle.time:
                    # Check neighbours within lookback range
                    is_pivot = True
                    start = max(0, i - self._lookback)
                    end = min(len(buf), i + self._lookback + 1)
                    for j in range(start, end):
                        if j != i and buf[j].volume >= candle.volume:
                            is_pivot = False
                            break
                    if is_pivot:
                        return True

        return False

    # ------------------------------------------------------------------
    # Zone lifecycle
    # ------------------------------------------------------------------

    def _check_zone_status(self, candle: Candle) -> list[ZoneEvent]:
        """Check all active zones for tested / mitigated / expired."""
        events: list[ZoneEvent] = []
        to_remove: list[Zone] = []

        for zone in self._zones:
            if zone.mitigated:
                continue

            # Age increment
            zone.age_candles += 1

            # Expiry check
            if zone.age_candles >= OB_ZONE_MAX_AGE_CANDLES:
                zone.mark_mitigated()
                events.append(ZoneEvent(event_type="expired", zone=zone))
                to_remove.append(zone)
                continue

            # Mitigation check: price CLOSES through the zone
            if zone.type == ZoneType.SUPPLY and candle.close > zone.top:
                zone.mark_mitigated()
                events.append(ZoneEvent(event_type="mitigated", zone=zone))
                to_remove.append(zone)
                continue

            if zone.type == ZoneType.DEMAND and candle.close < zone.bottom:
                zone.mark_mitigated()
                events.append(ZoneEvent(event_type="mitigated", zone=zone))
                to_remove.append(zone)
                continue

            # Tested check: price touches zone without closing through
            touched = False
            if zone.type == ZoneType.DEMAND and candle.low <= zone.top and candle.close >= zone.bottom:
                touched = True
            elif zone.type == ZoneType.SUPPLY and candle.high >= zone.bottom and candle.close <= zone.top:
                touched = True

            if touched:
                zone.mark_tested()
                events.append(ZoneEvent(event_type="tested", zone=zone))

        # Remove mitigated/expired zones from the list
        for z in to_remove:
            self._zones.remove(z)

        return events
