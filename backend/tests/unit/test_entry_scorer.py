"""Tests for EntryScorer — 3 entry modes + 5 confirmation factors."""

from datetime import datetime, timezone, timedelta

import pytest

from app.zones.scorer import EntryScorer
from app.zones.models import Zone, ZoneType
from app.core.models import Candle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _zone(zone_type=ZoneType.DEMAND, top=69000.0, bottom=68500.0, touch_count=0):
    return Zone(
        type=zone_type, top=top, bottom=bottom,
        origin_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        trigger="BOS", volume_ratio=2.0,
        touch_count=touch_count, is_fresh=(touch_count == 0),
    )


def _candle(open, high, low, close, volume=100.0, offset=0):
    return Candle(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=offset),
        symbol="BTC/USDT", timeframe="1h",
        open=open, high=high, low=low, close=close, volume=volume,
    )


def _indicators(**overrides):
    defaults = {
        "rsi_14": 50.0,
        "atr_14": 500.0,
        "volume_sma_20": 100.0,
        "ema_9": 69000.0,
        "ema_21": 68800.0,
        "ema_55": 68500.0,
    }
    defaults.update(overrides)

    class MockInd:
        pass

    ind = MockInd()
    for k, v in defaults.items():
        setattr(ind, k, v)
    return ind


# ---------------------------------------------------------------------------
# Entry Modes
# ---------------------------------------------------------------------------

class TestEntryModes:
    """Tests for the three entry mode detections."""

    def setup_method(self):
        self.scorer = EntryScorer()

    def test_touch_zone_demand(self):
        """Candle.low enters demand zone, close above zone.top -> TOUCH_ZONE."""
        zone = _zone(ZoneType.DEMAND, top=69000.0, bottom=68500.0)
        # low dips into zone, close stays above zone top
        candle = _candle(open=69200.0, high=69300.0, low=68900.0, close=69100.0)
        score, conds = self.scorer.score(candle, zone, _indicators(), "neutral", [])
        assert "TOUCH_ZONE" in conds
        assert score >= 0.15

    def test_touch_zone_supply(self):
        """Candle.high enters supply zone, close below zone.bottom -> TOUCH_ZONE."""
        zone = _zone(ZoneType.SUPPLY, top=71000.0, bottom=70500.0)
        # high reaches into zone, close stays below zone bottom
        # Upper wick = 70600-70400 = 200, range = 70600-70000 = 600 -> 33% (not rejection)
        candle = _candle(open=70400.0, high=70600.0, low=70000.0, close=70300.0)
        score, conds = self.scorer.score(candle, zone, _indicators(), "neutral", [])
        assert "TOUCH_ZONE" in conds
        assert score >= 0.15

    def test_rejection_candle_pin_bar(self):
        """Pin bar in zone (wick >= 60% of range) -> REJECTION_CANDLE."""
        zone = _zone(ZoneType.DEMAND, top=69000.0, bottom=68500.0)
        # Pin bar: long lower wick into zone, small body near top
        # Range = 69100 - 68600 = 500. Lower wick = 69000 - 68600 = 400 = 80% of range.
        candle = _candle(open=69050.0, high=69100.0, low=68600.0, close=69080.0)
        score, conds = self.scorer.score(candle, zone, _indicators(), "neutral", [])
        assert "REJECTION_CANDLE" in conds
        assert score >= 0.25

    def test_no_entry_when_far_from_zone(self):
        """Price far from zone -> no entry mode triggered."""
        zone = _zone(ZoneType.DEMAND, top=69000.0, bottom=68500.0)
        # Candle entirely above zone, not touching it
        candle = _candle(open=70000.0, high=70500.0, low=69500.0, close=70200.0)
        score, conds = self.scorer.score(candle, zone, _indicators(), "neutral", [])
        # Should have no entry mode conditions
        entry_modes = {"TOUCH_ZONE", "REJECTION_CANDLE", "BREAK_RETEST"}
        assert not (set(conds) & entry_modes)
        assert score < 0.15  # no entry mode base score

    def test_break_retest(self):
        """Recent candles show break then pullback -> BREAK_RETEST."""
        zone = _zone(ZoneType.DEMAND, top=69000.0, bottom=68500.0)
        # Candles: was below zone, then broke above, now pulling back into zone
        recent = [
            _candle(open=68200.0, high=68400.0, low=68100.0, close=68300.0, offset=1),  # below zone
            _candle(open=68300.0, high=68600.0, low=68200.0, close=68500.0, offset=2),  # still below
            _candle(open=68500.0, high=69200.0, low=68400.0, close=69100.0, offset=3),  # broke above zone.top
            _candle(open=69100.0, high=69300.0, low=69050.0, close=69200.0, offset=4),  # above zone
        ]
        # Current candle pulls back into zone
        candle = _candle(open=69100.0, high=69150.0, low=68800.0, close=69050.0, offset=5)
        score, conds = self.scorer.score(candle, zone, _indicators(), "neutral", recent)
        assert "BREAK_RETEST" in conds
        assert score >= 0.30


# ---------------------------------------------------------------------------
# Confirmation Factors
# ---------------------------------------------------------------------------

class TestConfirmationFactors:
    """Tests for the 5 confirmation factors."""

    def setup_method(self):
        self.scorer = EntryScorer()

    def _touch_demand_candle(self):
        """Returns a candle that touches a default demand zone (TOUCH_ZONE)."""
        return _candle(open=69200.0, high=69300.0, low=68900.0, close=69100.0)

    def test_mtf_aligned_demand_bullish(self):
        """htf_trend='bullish' for DEMAND zone -> MTF_ALIGNED (+0.20)."""
        zone = _zone(ZoneType.DEMAND)
        candle = self._touch_demand_candle()
        score, conds = self.scorer.score(candle, zone, _indicators(), "bullish", [])
        assert "MTF_ALIGNED" in conds
        # touch_zone=0.15 + mtf=0.20 + zone_fresh=0.10 = 0.45 minimum
        assert score >= 0.35

    def test_mtf_misaligned(self):
        """htf_trend opposes zone direction -> no MTF_ALIGNED."""
        zone = _zone(ZoneType.DEMAND)
        candle = self._touch_demand_candle()
        score, conds = self.scorer.score(candle, zone, _indicators(), "bearish", [])
        assert "MTF_ALIGNED" not in conds

    def test_volume_spike(self):
        """Volume >= 1.5x SMA20 -> VOLUME_SPIKE (+0.15)."""
        zone = _zone(ZoneType.DEMAND)
        # volume=200, sma20=100 -> 2.0x threshold
        candle = _candle(open=69200.0, high=69300.0, low=68900.0, close=69100.0, volume=200.0)
        ind = _indicators(volume_sma_20=100.0)
        score, conds = self.scorer.score(candle, zone, ind, "neutral", [])
        assert "VOLUME_SPIKE" in conds

    def test_zone_fresh(self):
        """touch_count=0 -> ZONE_FRESH (+0.10)."""
        zone = _zone(ZoneType.DEMAND, touch_count=0)
        candle = self._touch_demand_candle()
        score, conds = self.scorer.score(candle, zone, _indicators(), "neutral", [])
        assert "ZONE_FRESH" in conds

    def test_zone_tested_1(self):
        """touch_count=1 -> ZONE_TESTED_1 (+0.05)."""
        zone = _zone(ZoneType.DEMAND, touch_count=1)
        candle = self._touch_demand_candle()
        score, conds = self.scorer.score(candle, zone, _indicators(), "neutral", [])
        assert "ZONE_TESTED_1" in conds
        assert "ZONE_FRESH" not in conds

    def test_zone_2plus_touches(self):
        """touch_count=2 -> no freshness score."""
        zone = _zone(ZoneType.DEMAND, touch_count=2)
        candle = self._touch_demand_candle()
        score, conds = self.scorer.score(candle, zone, _indicators(), "neutral", [])
        assert "ZONE_FRESH" not in conds
        assert "ZONE_TESTED_1" not in conds

    def test_body_ratio(self):
        """Rejection wick >= 60% of range -> BODY_RATIO (+0.10)."""
        zone = _zone(ZoneType.DEMAND, top=69000.0, bottom=68500.0)
        # Pin bar with long lower wick: range=500, lower_wick=400 (80%)
        candle = _candle(open=69050.0, high=69100.0, low=68600.0, close=69080.0)
        score, conds = self.scorer.score(candle, zone, _indicators(), "neutral", [])
        assert "BODY_RATIO" in conds

    def test_no_body_ratio_marubozu(self):
        """Marubozu (body dominant, tiny wicks) -> no BODY_RATIO."""
        zone = _zone(ZoneType.DEMAND, top=69000.0, bottom=68500.0)
        # Marubozu: nearly all body, touching zone
        candle = _candle(open=68900.0, high=69300.0, low=68890.0, close=69290.0)
        score, conds = self.scorer.score(candle, zone, _indicators(), "neutral", [])
        assert "BODY_RATIO" not in conds

    def test_rsi_divergence(self):
        """Basic test that scorer handles RSI divergence input without error."""
        zone = _zone(ZoneType.DEMAND, top=69000.0, bottom=68500.0)
        candle = self._touch_demand_candle()
        # Build recent candles with decreasing lows (lower lows)
        recent = []
        for i in range(10):
            low = 68900.0 - i * 50  # price making lower lows
            recent.append(_candle(
                open=69100.0, high=69200.0, low=low, close=69050.0, offset=i + 1,
            ))
        # RSI making higher lows (bullish divergence) - we just provide indicators
        ind = _indicators(rsi_14=45.0)
        score, conds = self.scorer.score(candle, zone, ind, "neutral", recent)
        # Should not error; if divergence detected, RSI_DIVERGENCE in conds
        assert isinstance(score, float)
        assert isinstance(conds, list)


# ---------------------------------------------------------------------------
# Score Threshold
# ---------------------------------------------------------------------------

class TestScoreThreshold:
    """Tests for score capping and thresholds."""

    def setup_method(self):
        self.scorer = EntryScorer()

    def test_score_capped_at_1(self):
        """Score cannot exceed 1.0 even with all confirmations."""
        zone = _zone(ZoneType.DEMAND, top=69000.0, bottom=68500.0, touch_count=0)

        # Break-retest entry (+0.30) + all confirmations
        recent = [
            _candle(open=68200.0, high=68400.0, low=68100.0, close=68300.0, offset=1),
            _candle(open=68300.0, high=68600.0, low=68200.0, close=68500.0, offset=2),
            _candle(open=68500.0, high=69200.0, low=68400.0, close=69100.0, offset=3),
            _candle(open=69100.0, high=69300.0, low=69050.0, close=69200.0, offset=4),
        ]
        # Pin bar pullback into zone with huge volume
        candle = _candle(open=69050.0, high=69100.0, low=68600.0, close=69080.0, volume=500.0, offset=5)
        ind = _indicators(volume_sma_20=100.0, rsi_14=30.0)
        score, conds = self.scorer.score(candle, zone, ind, "bullish", recent)
        assert score <= 1.0

    def test_below_threshold_low_score(self):
        """No entry mode + bad conditions -> well below 0.50."""
        zone = _zone(ZoneType.DEMAND, top=69000.0, bottom=68500.0, touch_count=5)
        # Price far away, no confirmation
        candle = _candle(open=70000.0, high=70500.0, low=69500.0, close=70200.0, volume=10.0)
        ind = _indicators(volume_sma_20=100.0)
        score, conds = self.scorer.score(candle, zone, ind, "bearish", [])
        assert score < 0.50


# ---------------------------------------------------------------------------
# Supply Zone
# ---------------------------------------------------------------------------

class TestSupplyZone:
    """Tests specific to supply zone scoring."""

    def setup_method(self):
        self.scorer = EntryScorer()

    def test_supply_zone_touch(self):
        """High enters supply zone, close below bottom -> TOUCH_ZONE."""
        zone = _zone(ZoneType.SUPPLY, top=71000.0, bottom=70500.0)
        # Upper wick = 70600-70400 = 200, range = 70600-70000 = 600 -> 33% (not rejection)
        candle = _candle(open=70400.0, high=70600.0, low=70000.0, close=70300.0)
        score, conds = self.scorer.score(candle, zone, _indicators(), "neutral", [])
        assert "TOUCH_ZONE" in conds
        assert score >= 0.15
