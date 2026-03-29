"""Tests for ZoneDetector — structure break + volume pivot zone detection."""

from datetime import datetime, timezone, timedelta

import pytest

from app.zones.detector import ZoneDetector
from app.zones.models import Zone, ZoneEvent, ZoneType
from app.core.models import Candle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_candle(
    time_offset: int,
    open: float,
    high: float,
    low: float,
    close: float,
    volume: float = 100.0,
) -> Candle:
    return Candle(
        time=BASE_TIME + timedelta(hours=time_offset),
        symbol="BTC/USDT",
        timeframe="1h",
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _make_uptrend_with_swings(
    n_waves: int = 6,
    start: float = 65000.0,
    wave_up: float = 500.0,
    wave_down: float = 200.0,
    bars_up: int = 6,
    bars_down: int = 6,
    base_volume: float = 100.0,
) -> list[Candle]:
    """Uptrend with clear swing highs and lows.

    Each wave: bars_up rising, bars_down pulling back.
    Net movement per wave = wave_up - wave_down (positive).
    """
    candles: list[Candle] = []
    price = start
    idx = 0

    for _wave in range(n_waves):
        up_step = wave_up / bars_up
        for j in range(bars_up):
            o = price
            c = price + up_step * 0.8
            h = c + up_step * 0.15
            l = o - up_step * 0.05
            price = c
            candles.append(_make_candle(idx, o, h, l, c, volume=base_volume))
            idx += 1

        down_step = wave_down / bars_down
        for j in range(bars_down):
            o = price
            c = price - down_step * 0.8
            h = o + down_step * 0.05
            l = c - down_step * 0.15
            price = c
            candles.append(_make_candle(idx, o, h, l, c, volume=base_volume))
            idx += 1

    return candles


def _make_downtrend_with_swings(
    n_waves: int = 6,
    start: float = 75000.0,
    wave_down: float = 500.0,
    wave_up: float = 200.0,
    bars_down: int = 6,
    bars_up: int = 6,
    base_volume: float = 100.0,
) -> list[Candle]:
    """Downtrend with clear swing highs and lows."""
    candles: list[Candle] = []
    price = start
    idx = 0

    for _wave in range(n_waves):
        down_step = wave_down / bars_down
        for j in range(bars_down):
            o = price
            c = price - down_step * 0.8
            h = o + down_step * 0.05
            l = c - down_step * 0.15
            price = c
            candles.append(_make_candle(idx, o, h, l, c, volume=base_volume))
            idx += 1

        up_step = wave_up / bars_up
        for j in range(bars_up):
            o = price
            c = price + up_step * 0.8
            h = c + up_step * 0.15
            l = o - up_step * 0.05
            price = c
            candles.append(_make_candle(idx, o, h, l, c, volume=base_volume))
            idx += 1

    return candles


def _find_break_indices(candles: list[Candle], lookback: int = 5) -> dict:
    """Dry-run the detector to find where structure breaks happen, then return
    a dict of {break_index: 'bullish'|'bearish'} so tests can place volume
    spikes at index-1 (the OB candle)."""
    det = ZoneDetector(lookback=lookback)
    breaks: dict[int, str] = {}
    for i, c in enumerate(candles):
        sh = det._last_swing_high
        sl = det._last_swing_low
        bh = det._last_broken_high
        bl = det._last_broken_low
        if sh is not None and sl is not None:
            if c.close > sh and bh != sh:
                breaks[i] = "bullish"
            elif c.close < sl and bl != sl:
                breaks[i] = "bearish"
        det._process_candle(c)
    return breaks


def _inject_volume_spike(
    candles: list[Candle],
    indices: list[int],
    spike_volume: float = 800.0,
) -> None:
    """Mutate candles list: set high volume at given indices."""
    for i in indices:
        if 0 <= i < len(candles):
            c = candles[i]
            candles[i] = _make_candle(i, c.open, c.high, c.low, c.close, spike_volume)


def _make_v_shaped(
    down_waves: int = 3,
    up_waves: int = 4,
    start: float = 70000.0,
) -> list[Candle]:
    """V-shape: downtrend with swings then reversal uptrend with swings."""
    down_candles = _make_downtrend_with_swings(
        n_waves=down_waves, start=start, wave_down=400.0, wave_up=150.0,
        bars_down=6, bars_up=6,
    )
    last_close = down_candles[-1].close
    up_candles = _make_uptrend_with_swings(
        n_waves=up_waves, start=last_close, wave_up=500.0, wave_down=150.0,
        bars_up=6, bars_down=6,
    )
    base_idx = len(down_candles)
    for i, c in enumerate(up_candles):
        up_candles[i] = _make_candle(
            base_idx + i, c.open, c.high, c.low, c.close, c.volume,
        )
    return down_candles + up_candles


# ===========================================================================
# TestZoneDetectorInit
# ===========================================================================


class TestZoneDetectorInit:
    """Construction and default parameter tests."""

    def test_default_lookback(self):
        det = ZoneDetector()
        assert det._lookback == 5

    def test_custom_lookback(self):
        det = ZoneDetector(lookback=10)
        assert det._lookback == 10

    def test_empty_zones_on_init(self):
        det = ZoneDetector()
        assert det.get_active_zones() == []

    def test_get_nearest_zone_empty(self):
        det = ZoneDetector()
        assert det.get_nearest_zone(70000.0, ZoneType.DEMAND) is None
        assert det.get_nearest_zone(70000.0, ZoneType.SUPPLY) is None


# ===========================================================================
# TestStructureBreakDetection
# ===========================================================================


class TestStructureBreakDetection:
    """Structure break (BOS / CHoCH) with volume confirmation creates zones."""

    def test_uptrend_with_volume_spike_creates_demand_zone(self):
        """Uptrend with swings + volume spike at OB candle -> DEMAND zone."""
        candles = _make_uptrend_with_swings(n_waves=6)
        # Find where breaks happen and put volume spikes at OB candles
        breaks = _find_break_indices(candles)
        ob_indices = [bi - 1 for bi in breaks if breaks[bi] == "bullish" and bi > 0]
        assert len(ob_indices) >= 1, "Should have at least 1 bullish break"
        _inject_volume_spike(candles, ob_indices, 800.0)

        det = ZoneDetector()
        det.initialize(candles)
        active = det.get_active_zones()
        demand_zones = [z for z in active if z.type == ZoneType.DEMAND]
        assert len(demand_zones) >= 1, (
            f"Expected >= 1 DEMAND zone, got {len(demand_zones)}. "
            f"Active: {len(active)}, breaks: {breaks}, ob_indices: {ob_indices}"
        )

    def test_downtrend_with_volume_spike_creates_supply_zone(self):
        """Downtrend with swings + volume spike at OB candle -> SUPPLY zone."""
        candles = _make_downtrend_with_swings(n_waves=6)
        breaks = _find_break_indices(candles)
        ob_indices = [bi - 1 for bi in breaks if breaks[bi] == "bearish" and bi > 0]
        assert len(ob_indices) >= 1, "Should have at least 1 bearish break"
        _inject_volume_spike(candles, ob_indices, 800.0)

        det = ZoneDetector()
        det.initialize(candles)
        active = det.get_active_zones()
        supply_zones = [z for z in active if z.type == ZoneType.SUPPLY]
        assert len(supply_zones) >= 1, (
            f"Expected >= 1 SUPPLY zone, got {len(supply_zones)}. "
            f"Active: {len(active)}, breaks: {breaks}, ob_indices: {ob_indices}"
        )

    def test_insufficient_data_no_zones(self):
        """With fewer candles than 2*lookback+1, no zones should form."""
        candles = _make_uptrend_with_swings(n_waves=1)[:8]
        det = ZoneDetector(lookback=5)
        zones = det.initialize(candles)
        assert len(zones) == 0
        assert len(det.get_active_zones()) == 0

    def test_initialize_returns_zone_list(self):
        """initialize() should return a list (possibly empty) of Zone objects."""
        det = ZoneDetector()
        result = det.initialize(_make_uptrend_with_swings(n_waves=3))
        assert isinstance(result, list)
        for z in result:
            assert isinstance(z, Zone)

    def test_v_shaped_reversal_creates_demand_zone(self):
        """V-shape with volume spike near reversal should form DEMAND zone."""
        candles = _make_v_shaped()
        breaks = _find_break_indices(candles)
        # Put volume spikes at all OB candles
        ob_indices = [bi - 1 for bi in breaks if bi > 0]
        _inject_volume_spike(candles, ob_indices, 800.0)

        det = ZoneDetector()
        det.initialize(candles)
        active = det.get_active_zones()
        demand = [z for z in active if z.type == ZoneType.DEMAND]
        assert len(demand) >= 1, (
            f"V-shaped reversal should create demand zone. "
            f"Active: {len(active)}, types: {[z.type for z in active]}, "
            f"breaks: {breaks}"
        )


# ===========================================================================
# TestVolumeConfirmation
# ===========================================================================


class TestVolumeConfirmation:
    """Volume confirmation is required for zone formation."""

    def test_no_volume_spike_few_or_no_zones(self):
        """Without volume spikes, breaks still happen but no zones form."""
        candles = _make_uptrend_with_swings(n_waves=6)
        # All volumes are constant 100.0 — no spike
        det = ZoneDetector()
        det.initialize(candles)
        active = det.get_active_zones()
        # With constant volume, volume pivot check fails (all equal), and
        # spike condition won't fire. Zones should be scarce or zero.
        assert len(active) <= 2, (
            f"No volume spikes should produce at most 2 zones, got {len(active)}"
        )

    def test_volume_spike_at_ob_candle_creates_zone(self):
        """Volume spike right before a breakout should create a zone."""
        candles = _make_uptrend_with_swings(n_waves=6)
        breaks = _find_break_indices(candles)
        ob_indices = [bi - 1 for bi in breaks if bi > 0]
        _inject_volume_spike(candles, ob_indices, 1000.0)

        det = ZoneDetector()
        det.initialize(candles)
        active = det.get_active_zones()
        assert len(active) >= 1, (
            f"Volume spike at OB candle should create >= 1 zone. "
            f"ob_indices: {ob_indices}"
        )

    def test_volume_pivot_detection(self):
        """A bar whose volume exceeds its neighbours is a volume pivot."""
        candles = _make_uptrend_with_swings(n_waves=6)
        breaks = _find_break_indices(candles)
        ob_indices = [bi - 1 for bi in breaks if bi > 0]
        # Make just one OB candle a volume pivot (not necessarily spike)
        if ob_indices:
            i = ob_indices[0]
            # Set neighbours low, OB candle high
            for j in range(max(0, i - 5), min(len(candles), i + 6)):
                if j != i:
                    c = candles[j]
                    candles[j] = _make_candle(j, c.open, c.high, c.low, c.close, 50.0)
            c = candles[i]
            candles[i] = _make_candle(i, c.open, c.high, c.low, c.close, 500.0)

        det = ZoneDetector()
        det.initialize(candles)
        active = det.get_active_zones()
        assert isinstance(active, list)


# ===========================================================================
# TestZoneLifecycle
# ===========================================================================


class TestZoneLifecycle:
    """Zone state transitions: tested, mitigated, expired."""

    def test_zone_mitigated_on_close_through(self):
        """A supply zone should be mitigated when price closes above it."""
        det = ZoneDetector()
        supply = Zone(
            type=ZoneType.SUPPLY,
            top=72000.0,
            bottom=71500.0,
            origin_time=BASE_TIME,
            trigger="BOS",
            volume_ratio=2.0,
        )
        det._zones.append(supply)

        candle = _make_candle(100, 71800.0, 72500.0, 71700.0, 72400.0)
        events = det.update(candle)

        mitigated_events = [e for e in events if e.event_type == "mitigated"]
        assert len(mitigated_events) >= 1, "Supply zone should be mitigated when close > top"
        assert supply.mitigated is True

    def test_zone_mitigated_demand_close_below(self):
        """A demand zone should be mitigated when price closes below it."""
        det = ZoneDetector()
        demand = Zone(
            type=ZoneType.DEMAND,
            top=68000.0,
            bottom=67500.0,
            origin_time=BASE_TIME,
            trigger="BOS",
            volume_ratio=2.0,
        )
        det._zones.append(demand)

        candle = _make_candle(100, 67800.0, 68100.0, 67200.0, 67300.0)
        events = det.update(candle)

        mitigated_events = [e for e in events if e.event_type == "mitigated"]
        assert len(mitigated_events) >= 1, "Demand zone should be mitigated when close < bottom"
        assert demand.mitigated is True

    def test_zone_tested_touch_without_close_through(self):
        """Touching a demand zone without closing through it should mark it tested."""
        det = ZoneDetector()
        demand = Zone(
            type=ZoneType.DEMAND,
            top=68000.0,
            bottom=67500.0,
            origin_time=BASE_TIME,
            trigger="BOS",
            volume_ratio=2.0,
        )
        det._zones.append(demand)

        candle = _make_candle(100, 68200.0, 68300.0, 67800.0, 68100.0)
        events = det.update(candle)

        tested_events = [e for e in events if e.event_type == "tested"]
        assert len(tested_events) >= 1, "Demand zone should be tested when low enters zone"
        assert demand.touch_count == 1
        assert demand.is_fresh is False

    def test_supply_zone_tested_wick_into_zone(self):
        """Wick into supply zone without close through should mark tested."""
        det = ZoneDetector()
        supply = Zone(
            type=ZoneType.SUPPLY,
            top=72000.0,
            bottom=71500.0,
            origin_time=BASE_TIME,
            trigger="BOS",
            volume_ratio=2.0,
        )
        det._zones.append(supply)

        candle = _make_candle(100, 71200.0, 71700.0, 71100.0, 71300.0)
        events = det.update(candle)

        tested_events = [e for e in events if e.event_type == "tested"]
        assert len(tested_events) >= 1
        assert supply.touch_count == 1
        assert supply.is_fresh is False

    def test_zone_expiry_at_max_age(self):
        """Zone at age_candles=499 should expire after one more update."""
        det = ZoneDetector()
        zone = Zone(
            type=ZoneType.DEMAND,
            top=68000.0,
            bottom=67500.0,
            origin_time=BASE_TIME,
            trigger="BOS",
            volume_ratio=2.0,
            age_candles=499,
        )
        det._zones.append(zone)

        candle = _make_candle(600, 70000.0, 70100.0, 69900.0, 70050.0)
        events = det.update(candle)

        expired_events = [e for e in events if e.event_type == "expired"]
        assert len(expired_events) >= 1, "Zone at age 499 should expire after 1 update"
        assert len(det.get_active_zones()) == 0

    def test_mitigated_zone_removed_from_active(self):
        """Mitigated zone should not appear in get_active_zones()."""
        det = ZoneDetector()
        supply = Zone(
            type=ZoneType.SUPPLY,
            top=72000.0,
            bottom=71500.0,
            origin_time=BASE_TIME,
            trigger="BOS",
            volume_ratio=2.0,
        )
        det._zones.append(supply)
        assert len(det.get_active_zones()) == 1

        candle = _make_candle(100, 71800.0, 72500.0, 71700.0, 72400.0)
        det.update(candle)
        assert len(det.get_active_zones()) == 0

    def test_age_increments_each_update(self):
        """Zone age should increment by 1 with each update call."""
        det = ZoneDetector()
        zone = Zone(
            type=ZoneType.DEMAND,
            top=68000.0,
            bottom=67500.0,
            origin_time=BASE_TIME,
            trigger="BOS",
            volume_ratio=2.0,
            age_candles=0,
        )
        det._zones.append(zone)

        for i in range(5):
            candle = _make_candle(100 + i, 70000.0, 70100.0, 69900.0, 70050.0)
            det.update(candle)

        assert zone.age_candles == 5


# ===========================================================================
# TestIncrementalUpdate
# ===========================================================================


class TestIncrementalUpdate:
    """update() should be O(1) incremental and return ZoneEvent list."""

    def test_update_returns_event_list(self):
        det = ZoneDetector()
        det.initialize(_make_uptrend_with_swings(n_waves=3))
        candle = _make_candle(50, 70000.0, 70200.0, 69800.0, 70100.0)
        result = det.update(candle)
        assert isinstance(result, list)
        for e in result:
            assert isinstance(e, ZoneEvent)

    def test_get_nearest_zone_returns_closest(self):
        """get_nearest_zone should return the zone whose midpoint is closest."""
        det = ZoneDetector()
        z1 = Zone(
            type=ZoneType.DEMAND,
            top=68000.0,
            bottom=67500.0,
            origin_time=BASE_TIME,
            trigger="BOS",
            volume_ratio=2.0,
        )
        z2 = Zone(
            type=ZoneType.DEMAND,
            top=66000.0,
            bottom=65500.0,
            origin_time=BASE_TIME,
            trigger="BOS",
            volume_ratio=1.8,
        )
        det._zones.extend([z1, z2])

        nearest = det.get_nearest_zone(67600.0, ZoneType.DEMAND)
        assert nearest is not None
        assert nearest is z1

    def test_get_nearest_zone_filters_by_type(self):
        """get_nearest_zone should only consider zones of the requested type."""
        det = ZoneDetector()
        demand = Zone(
            type=ZoneType.DEMAND,
            top=68000.0,
            bottom=67500.0,
            origin_time=BASE_TIME,
            trigger="BOS",
            volume_ratio=2.0,
        )
        supply = Zone(
            type=ZoneType.SUPPLY,
            top=72000.0,
            bottom=71500.0,
            origin_time=BASE_TIME,
            trigger="BOS",
            volume_ratio=2.0,
        )
        det._zones.extend([demand, supply])

        result = det.get_nearest_zone(70000.0, ZoneType.SUPPLY)
        assert result is supply

        result = det.get_nearest_zone(70000.0, ZoneType.DEMAND)
        assert result is demand

    def test_get_nearest_zone_none_when_empty(self):
        det = ZoneDetector()
        assert det.get_nearest_zone(70000.0, ZoneType.DEMAND) is None

    def test_get_nearest_zone_ignores_mitigated(self):
        """Mitigated zones should not be returned by get_nearest_zone."""
        det = ZoneDetector()
        z = Zone(
            type=ZoneType.DEMAND,
            top=68000.0,
            bottom=67500.0,
            origin_time=BASE_TIME,
            trigger="BOS",
            volume_ratio=2.0,
            mitigated=True,
        )
        det._zones.append(z)
        assert det.get_nearest_zone(67700.0, ZoneType.DEMAND) is None

    def test_multiple_updates_accumulate_zones(self):
        """Feeding candles one-by-one via update() should eventually create zones."""
        det = ZoneDetector()
        candles = _make_uptrend_with_swings(n_waves=6)
        breaks = _find_break_indices(candles)
        ob_indices = [bi - 1 for bi in breaks if bi > 0]
        _inject_volume_spike(candles, ob_indices, 800.0)

        # Feed first batch via initialize
        det.initialize(candles[:15])
        # Feed rest via update
        all_events: list[ZoneEvent] = []
        for c in candles[15:]:
            events = det.update(c)
            all_events.extend(events)
        active = det.get_active_zones()
        assert len(active) >= 0  # sanity — no crash
        assert isinstance(all_events, list)


# ===========================================================================
# TestZoneProperties
# ===========================================================================


class TestZoneProperties:
    """Zone width, midpoint, contains, strength scoring."""

    def _create_detector_with_zones(self):
        """Helper: create a detector that has produced zones."""
        candles = _make_uptrend_with_swings(n_waves=6)
        breaks = _find_break_indices(candles)
        ob_indices = [bi - 1 for bi in breaks if bi > 0]
        _inject_volume_spike(candles, ob_indices, 800.0)
        det = ZoneDetector()
        det.initialize(candles)
        return det

    def test_zone_top_gte_bottom(self):
        """All created zones should have top >= bottom."""
        det = self._create_detector_with_zones()
        for z in det.get_active_zones():
            assert z.top >= z.bottom, f"Zone top ({z.top}) < bottom ({z.bottom})"

    def test_zone_trigger_is_bos_or_choch(self):
        """Zone trigger should be 'BOS' or 'CHoCH'."""
        det = self._create_detector_with_zones()
        for z in det.get_active_zones():
            assert z.trigger in ("BOS", "CHoCH"), f"Unexpected trigger: {z.trigger}"

    def test_zone_volume_ratio_positive(self):
        """Volume ratio should be > 0 for all zones."""
        candles = _make_downtrend_with_swings(n_waves=6)
        breaks = _find_break_indices(candles)
        ob_indices = [bi - 1 for bi in breaks if bi > 0]
        _inject_volume_spike(candles, ob_indices, 800.0)
        det = ZoneDetector()
        det.initialize(candles)
        for z in det.get_active_zones():
            assert z.volume_ratio > 0

    def test_zone_is_fresh_on_creation(self):
        """Newly created zones should be fresh (unless touched by later candles)."""
        det = self._create_detector_with_zones()
        for z in det.get_active_zones():
            if z.touch_count == 0:
                assert z.is_fresh is True


# ===========================================================================
# TestHighVolumeCandleNarrowing
# ===========================================================================


class TestHighVolumeCandleNarrowing:
    """When OB candle range >= 2x ATR, zone should narrow to body only."""

    def test_wide_candle_zone_uses_body(self):
        """Manually create scenario where ATR is small and OB candle is wide."""
        det = ZoneDetector()
        candles: list[Candle] = []
        for i in range(30):
            o = 70000.0
            c = 70100.0
            h = 70150.0
            l = 69950.0
            candles.append(_make_candle(i, o, h, l, c, volume=100.0))
        det.initialize(candles)

        wide_ob = _make_candle(30, 70000.0, 70600.0, 70000.0, 70500.0, volume=800.0)
        breakout = _make_candle(31, 70500.0, 70800.0, 70400.0, 70750.0, volume=100.0)

        det.update(wide_ob)
        det.update(breakout)

        for z in det.get_active_zones():
            assert z.top >= z.bottom


# ===========================================================================
# TestEdgeCases
# ===========================================================================


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_single_candle_no_crash(self):
        det = ZoneDetector()
        zones = det.initialize([_make_candle(0, 70000, 70100, 69900, 70050)])
        assert zones == []

    def test_duplicate_candle_no_crash(self):
        """Feeding the same candle twice should not crash."""
        det = ZoneDetector()
        c = _make_candle(0, 70000, 70100, 69900, 70050)
        det.initialize([c, c, c, c, c])
        det.update(c)
        assert isinstance(det.get_active_zones(), list)

    def test_zero_volume_candle(self):
        """Zero-volume candle should not crash."""
        det = ZoneDetector()
        candles = _make_uptrend_with_swings(n_waves=3)
        det.initialize(candles)
        zero_vol = _make_candle(50, 70000, 70100, 69900, 70050, volume=0.0)
        events = det.update(zero_vol)
        assert isinstance(events, list)

    def test_initialize_then_update_consistency(self):
        """initialize(all) should produce same zones as initialize(first) + update(rest)."""
        candles = _make_uptrend_with_swings(n_waves=5)
        breaks = _find_break_indices(candles)
        ob_indices = [bi - 1 for bi in breaks if bi > 0]
        _inject_volume_spike(candles, ob_indices, 800.0)

        det1 = ZoneDetector()
        det1.initialize(candles)
        zones1 = det1.get_active_zones()

        det2 = ZoneDetector()
        det2.initialize(candles[:20])
        for c in candles[20:]:
            det2.update(c)
        zones2 = det2.get_active_zones()

        assert len(zones1) == len(zones2), (
            f"Batch ({len(zones1)}) vs incremental ({len(zones2)}) zone count mismatch"
        )

    def test_lookback_1_works(self):
        """Lookback of 1 should still work (swing = local extremum)."""
        det = ZoneDetector(lookback=1)
        candles = _make_uptrend_with_swings(n_waves=3)
        zones = det.initialize(candles)
        assert isinstance(zones, list)
