"""Tests for OrderBlockZonesStrategy."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.strategies.order_block_zones import OrderBlockZonesStrategy
from app.core.models import Candle, RawSignal
from app.config.constants import Direction
from app.zones.models import Zone, ZoneType


def _candle(offset, open, high, low, close, volume=100.0):
    return Candle(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=offset),
        symbol="BTC/USDT", timeframe="1h",
        open=open, high=high, low=low, close=close, volume=volume,
    )


def _make_candles(n=120):
    """Generate 120 candles with uptrend + volume spike at breakout + pullback."""
    candles = []
    for i in range(80):
        o = 65000 + i * 50
        c = o + 35
        h = c + 20
        l = o - 15
        candles.append(_candle(i, o, h, l, c, volume=100 + i * 2))
    # Volume spike + breakout around bar 40
    candles[40] = _candle(40, 67000, 67200, 66900, 67150, volume=800.0)
    candles[41] = _candle(41, 67150, 67600, 67100, 67500, volume=500.0)
    # Pullback
    for i in range(80, 120):
        o = 69000 - (i - 80) * 30
        c = o - 20
        l = c - 15
        h = o + 10
        candles.append(_candle(i, o, h, l, c, volume=100 + i))
    return candles


def _indicators(**overrides):
    defaults = {
        "rsi_14": 50.0, "atr_14": 500.0, "volume_sma_20": 100.0,
        "ema_9": 69000.0, "ema_21": 68800.0, "ema_55": 68500.0,
        "bb_upper": 70000.0, "bb_lower": 67000.0, "bb_middle": 68500.0,
        "adx": 30.0, "macd": 50.0, "macd_signal": 45.0, "macd_histogram": 5.0,
    }
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _make_demand_zone(top=68000.0, bottom=67500.0):
    """Create a demand zone for testing."""
    return Zone(
        type=ZoneType.DEMAND,
        top=top,
        bottom=bottom,
        origin_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        trigger="BOS",
        volume_ratio=2.0,
        touch_count=0,
        is_fresh=True,
    )


def _make_supply_zone(top=70000.0, bottom=69500.0):
    """Create a supply zone for testing."""
    return Zone(
        type=ZoneType.SUPPLY,
        top=top,
        bottom=bottom,
        origin_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        trigger="BOS",
        volume_ratio=2.0,
        touch_count=0,
        is_fresh=True,
    )


def _strategy_with_mock_detector_scorer(zones, score, conditions):
    """Create strategy with mocked detector and scorer returning controlled values."""
    s = OrderBlockZonesStrategy()
    s._initialized = True  # skip initialize call
    s._htf_trend = "bullish"

    # Mock detector
    s._detector = MagicMock()
    s._detector.update = MagicMock(return_value=[])
    s._detector.get_active_zones = MagicMock(return_value=zones)

    # Mock scorer
    s._scorer = MagicMock()
    s._scorer.score = MagicMock(return_value=(score, conditions))

    return s


# ------------------------------------------------------------------ #
# TestStrategyProperties                                              #
# ------------------------------------------------------------------ #

class TestStrategyProperties:
    def test_name(self):
        s = OrderBlockZonesStrategy()
        assert s.name == "ob_zones"

    def test_weight(self):
        s = OrderBlockZonesStrategy()
        assert s.weight == 0.20

    def test_min_candles(self):
        s = OrderBlockZonesStrategy()
        assert s.min_candles == 100


# ------------------------------------------------------------------ #
# TestEvaluateGuards                                                  #
# ------------------------------------------------------------------ #

class TestEvaluateGuards:
    def test_returns_none_insufficient_candles(self):
        s = OrderBlockZonesStrategy()
        candles = [_candle(i, 65000, 65100, 64900, 65050) for i in range(50)]
        result = s.evaluate(candles, _indicators())
        assert result is None

    def test_returns_none_empty_candles(self):
        s = OrderBlockZonesStrategy()
        result = s.evaluate([], _indicators())
        assert result is None


# ------------------------------------------------------------------ #
# TestEvaluateSignal                                                  #
# ------------------------------------------------------------------ #

class TestEvaluateSignal:
    def test_returns_raw_signal_or_none(self):
        s = OrderBlockZonesStrategy()
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is None or isinstance(result, RawSignal)

    def test_signal_has_correct_strategy_name(self):
        """With mocked detector/scorer, verify signal strategy_name is correct."""
        zone = _make_demand_zone(top=68000.0, bottom=67500.0)
        s = _strategy_with_mock_detector_scorer([zone], 0.65, ["TOUCH_ZONE", "MTF_ALIGNED"])
        candles = _make_candles(120)
        # Last candle close is ~67780. Zone midpoint ~67750. ATR=500, max_dist=1500.
        result = s.evaluate(candles, _indicators())
        assert result is not None
        assert result.strategy_name == "ob_zones"

    def test_signal_direction_long_for_demand(self):
        """Demand zone should produce LONG direction."""
        zone = _make_demand_zone(top=68000.0, bottom=67500.0)
        s = _strategy_with_mock_detector_scorer([zone], 0.70, ["REJECTION_CANDLE", "MTF_ALIGNED"])
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is not None
        assert result.direction == Direction.LONG

    def test_signal_direction_short_for_supply(self):
        """Supply zone should produce SHORT direction."""
        zone = _make_supply_zone(top=68200.0, bottom=67800.0)
        s = _strategy_with_mock_detector_scorer([zone], 0.60, ["TOUCH_ZONE", "VOLUME_SPIKE"])
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is not None
        assert result.direction == Direction.SHORT

    def test_signal_strength_positive_for_long(self):
        """LONG signal should have positive strength."""
        zone = _make_demand_zone(top=68000.0, bottom=67500.0)
        s = _strategy_with_mock_detector_scorer([zone], 0.65, ["TOUCH_ZONE"])
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is not None
        assert result.strength > 0
        assert result.strength <= 1.0

    def test_signal_strength_negative_for_short(self):
        """SHORT signal should have negative strength."""
        zone = _make_supply_zone(top=68200.0, bottom=67800.0)
        s = _strategy_with_mock_detector_scorer([zone], 0.60, ["TOUCH_ZONE"])
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is not None
        assert result.strength < 0
        assert result.strength >= -1.0

    def test_returns_none_when_score_below_threshold(self):
        """Score below OB_ZONE_MIN_SCORE should return None."""
        zone = _make_demand_zone(top=68000.0, bottom=67500.0)
        s = _strategy_with_mock_detector_scorer([zone], 0.30, ["TOUCH_ZONE"])
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is None

    def test_returns_none_when_no_active_zones(self):
        """No active zones should return None."""
        s = _strategy_with_mock_detector_scorer([], 0.0, [])
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is None


# ------------------------------------------------------------------ #
# TestSLTPCalculation                                                 #
# ------------------------------------------------------------------ #

class TestSLTPCalculation:
    def test_sl_outside_zone_for_long(self):
        """LONG signal: stop_loss must be below zone_bottom."""
        zone = _make_demand_zone(top=68000.0, bottom=67500.0)
        s = _strategy_with_mock_detector_scorer([zone], 0.65, ["TOUCH_ZONE", "MTF_ALIGNED"])
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is not None
        assert result.direction == Direction.LONG
        assert result.metadata["stop_loss"] < result.metadata["zone_bottom"]

    def test_sl_outside_zone_for_short(self):
        """SHORT signal: stop_loss must be above zone_top."""
        zone = _make_supply_zone(top=68200.0, bottom=67800.0)
        s = _strategy_with_mock_detector_scorer([zone], 0.60, ["TOUCH_ZONE", "VOLUME_SPIKE"])
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is not None
        assert result.direction == Direction.SHORT
        assert result.metadata["stop_loss"] > result.metadata["zone_top"]

    def test_metadata_contains_zone_info(self):
        """Signal metadata must include zone info and SL/TP levels."""
        zone = _make_demand_zone(top=68000.0, bottom=67500.0)
        s = _strategy_with_mock_detector_scorer([zone], 0.65, ["TOUCH_ZONE"])
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is not None
        assert "zone_type" in result.metadata
        assert "zone_top" in result.metadata
        assert "zone_bottom" in result.metadata
        assert "stop_loss" in result.metadata
        assert "tp1" in result.metadata
        assert "tp2" in result.metadata
        assert "tp3" in result.metadata

    def test_tp_levels_ordered_for_long(self):
        """For LONG: TP1 < TP2 < TP3, all above entry."""
        zone = _make_demand_zone(top=68000.0, bottom=67500.0)
        s = _strategy_with_mock_detector_scorer([zone], 0.65, ["TOUCH_ZONE"])
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is not None
        assert result.direction == Direction.LONG
        tp1 = result.metadata["tp1"]
        tp2 = result.metadata["tp2"]
        tp3 = result.metadata["tp3"]
        assert tp1 > result.entry_price
        assert tp2 > tp1
        assert tp3 > tp2

    def test_tp_levels_ordered_for_short(self):
        """For SHORT: TP1 > TP2 > TP3, all below entry."""
        zone = _make_supply_zone(top=68200.0, bottom=67800.0)
        s = _strategy_with_mock_detector_scorer([zone], 0.60, ["TOUCH_ZONE"])
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is not None
        assert result.direction == Direction.SHORT
        tp1 = result.metadata["tp1"]
        tp2 = result.metadata["tp2"]
        tp3 = result.metadata["tp3"]
        assert tp1 < result.entry_price
        assert tp2 < tp1
        assert tp3 < tp2


# ------------------------------------------------------------------ #
# TestAmbiguousZones                                                  #
# ------------------------------------------------------------------ #

class TestAmbiguousZones:
    def test_returns_none_with_overlapping_supply_demand(self):
        """Overlapping supply + demand zones at price should return None."""
        # Last candle close ~67780. Both zones contain that price.
        demand = _make_demand_zone(top=68000.0, bottom=67500.0)
        supply = _make_supply_zone(top=68100.0, bottom=67600.0)
        s = _strategy_with_mock_detector_scorer([demand, supply], 0.70, ["TOUCH_ZONE"])
        candles = _make_candles(120)
        result = s.evaluate(candles, _indicators())
        assert result is None


# ------------------------------------------------------------------ #
# TestPrepareAsync                                                    #
# ------------------------------------------------------------------ #

class TestPrepareAsync:
    @pytest.mark.asyncio
    async def test_prepare_fetches_htf_data(self):
        s = OrderBlockZonesStrategy()
        collector = AsyncMock()
        htf_candles = [_candle(i, 65000 + i * 100, 65200 + i * 100, 64900 + i * 100, 65100 + i * 100) for i in range(100)]
        collector.get_candles = AsyncMock(return_value=htf_candles)
        await s.prepare(collector, "BTC/USDT")
        assert hasattr(s, "_htf_trend")
        assert s._htf_trend in ("bullish", "bearish", "neutral")

    @pytest.mark.asyncio
    async def test_prepare_handles_failure(self):
        s = OrderBlockZonesStrategy()
        collector = AsyncMock()
        collector.get_candles = AsyncMock(side_effect=Exception("network error"))
        await s.prepare(collector, "BTC/USDT")
        assert s._htf_trend == "neutral"

    @pytest.mark.asyncio
    async def test_prepare_bullish_trend(self):
        """Strongly uptrending HTF candles should yield bullish trend."""
        s = OrderBlockZonesStrategy()
        collector = AsyncMock()
        # Strong uptrend: each candle higher than previous
        htf_candles = [
            _candle(i, 60000 + i * 200, 60300 + i * 200, 59900 + i * 200, 60200 + i * 200)
            for i in range(100)
        ]
        collector.get_candles = AsyncMock(return_value=htf_candles)
        await s.prepare(collector, "BTC/USDT")
        assert s._htf_trend == "bullish"

    @pytest.mark.asyncio
    async def test_prepare_bearish_trend(self):
        """Strongly downtrending HTF candles should yield bearish trend."""
        s = OrderBlockZonesStrategy()
        collector = AsyncMock()
        # Strong downtrend: each candle lower than previous
        htf_candles = [
            _candle(i, 80000 - i * 200, 80100 - i * 200, 79800 - i * 200, 79900 - i * 200)
            for i in range(100)
        ]
        collector.get_candles = AsyncMock(return_value=htf_candles)
        await s.prepare(collector, "BTC/USDT")
        assert s._htf_trend == "bearish"

    @pytest.mark.asyncio
    async def test_prepare_neutral_insufficient_candles(self):
        """Too few HTF candles should yield neutral trend."""
        s = OrderBlockZonesStrategy()
        collector = AsyncMock()
        htf_candles = [_candle(i, 65000, 65100, 64900, 65050) for i in range(10)]
        collector.get_candles = AsyncMock(return_value=htf_candles)
        await s.prepare(collector, "BTC/USDT")
        assert s._htf_trend == "neutral"
