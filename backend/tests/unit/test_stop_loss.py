"""Unit tests for StopLossManager - all SL methods."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config.constants import (
    MAX_SL_PERCENT,
    Direction,
    MarketRegime,
    StopLossType,
)
from app.core.models import Candle
from app.risk.stop_loss import StopLossManager


def _make_candle(close: float, high: float = 0.0, low: float = 0.0) -> Candle:
    return Candle(
        time=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        symbol="BTC/USDT", timeframe="1h",
        open=close - 10, high=high or close + 20,
        low=low or close - 20, close=close,
        volume=100.0,
    )


def _make_candles_with_swing(n: int = 20) -> list[Candle]:
    """Create candles with clear swing high and swing low."""
    candles = []
    for i in range(n):
        price = 43000.0 + (i * 10)
        candles.append(_make_candle(
            close=price, high=price + 50, low=price - 50,
        ))
    return candles


class TestAtrBased:
    def test_long_atr_ranging(self):
        from app.config.constants import ATR_MULTIPLIER_RANGING
        sl, sl_type = StopLossManager.atr_based(
            entry=43200.0, direction=Direction.LONG, atr=200.0,
            regime=MarketRegime.RANGING,
        )
        assert sl == pytest.approx(43200.0 - 200.0 * ATR_MULTIPLIER_RANGING)
        assert sl_type == StopLossType.ATR_BASED

    def test_short_atr_ranging(self):
        from app.config.constants import ATR_MULTIPLIER_RANGING
        sl, _ = StopLossManager.atr_based(
            entry=43200.0, direction=Direction.SHORT, atr=200.0,
            regime=MarketRegime.RANGING,
        )
        assert sl == pytest.approx(43200.0 + 200.0 * ATR_MULTIPLIER_RANGING)

    def test_trending_uses_wider_multiplier(self):
        sl_trend, _ = StopLossManager.atr_based(
            entry=43200.0, direction=Direction.LONG, atr=200.0,
            regime=MarketRegime.TRENDING_UP,
        )
        sl_range, _ = StopLossManager.atr_based(
            entry=43200.0, direction=Direction.LONG, atr=200.0,
            regime=MarketRegime.RANGING,
        )
        # Trending SL is further away (lower for LONG)
        assert sl_trend < sl_range

    def test_volatile_widest_stop(self):
        sl_volatile, _ = StopLossManager.atr_based(
            entry=43200.0, direction=Direction.LONG, atr=200.0,
            regime=MarketRegime.HIGH_VOLATILITY,
        )
        sl_lowvol, _ = StopLossManager.atr_based(
            entry=43200.0, direction=Direction.LONG, atr=200.0,
            regime=MarketRegime.LOW_VOLATILITY,
        )
        assert sl_volatile < sl_lowvol

    def test_max_sl_distance_cap_long(self):
        """Large ATR should be capped at MAX_SL_PERCENT distance."""
        sl, _ = StopLossManager.atr_based(
            entry=43200.0, direction=Direction.LONG, atr=2000.0,
            regime=MarketRegime.HIGH_VOLATILITY,
        )
        max_distance = 43200.0 * MAX_SL_PERCENT
        assert sl >= 43200.0 - max_distance

    def test_max_sl_distance_cap_short(self):
        sl, _ = StopLossManager.atr_based(
            entry=43200.0, direction=Direction.SHORT, atr=2000.0,
            regime=MarketRegime.HIGH_VOLATILITY,
        )
        max_distance = 43200.0 * MAX_SL_PERCENT
        assert sl <= 43200.0 + max_distance


class TestStructureBased:
    def test_long_uses_swing_low(self):
        candles = _make_candles_with_swing()
        sl, sl_type = StopLossManager.structure_based(
            entry=43200.0, direction=Direction.LONG,
            candles=candles, atr=200.0,
        )
        swing_low = min(c.low for c in candles)
        buffer = 200.0 * 0.1
        assert sl == pytest.approx(swing_low - buffer)
        assert sl_type == StopLossType.STRUCTURE_BASED

    def test_short_uses_swing_high(self):
        candles = _make_candles_with_swing()
        sl, sl_type = StopLossManager.structure_based(
            entry=43200.0, direction=Direction.SHORT,
            candles=candles, atr=200.0,
        )
        swing_high = max(c.high for c in candles)
        buffer = 200.0 * 0.1
        assert sl == pytest.approx(swing_high + buffer)

    def test_insufficient_candles_fallback(self):
        candles = [_make_candle(43200.0)]
        sl, sl_type = StopLossManager.structure_based(
            entry=43200.0, direction=Direction.LONG,
            candles=candles, atr=200.0,
        )
        assert sl_type == StopLossType.PERCENTAGE
        assert sl == pytest.approx(43200.0 * (1 - MAX_SL_PERCENT))

    def test_lookback_window(self):
        candles = _make_candles_with_swing(50)
        sl_20, _ = StopLossManager.structure_based(
            entry=43200.0, direction=Direction.LONG,
            candles=candles, atr=200.0, lookback=20,
        )
        sl_50, _ = StopLossManager.structure_based(
            entry=43200.0, direction=Direction.LONG,
            candles=candles, atr=200.0, lookback=50,
        )
        # 50 lookback sees lower swing low (earlier candles), so SL is lower
        assert sl_50 < sl_20


class TestCombined:
    def test_long_picks_most_protective(self):
        """For LONG, combined should pick the HIGHER SL."""
        candles = _make_candles_with_swing()
        sl_combined, sl_type = StopLossManager.combined(
            entry=43200.0, direction=Direction.LONG,
            candles=candles, atr=200.0,
        )
        assert sl_type == StopLossType.COMBINED

        sl_atr, _ = StopLossManager.atr_based(
            entry=43200.0, direction=Direction.LONG, atr=200.0,
        )
        sl_struct, _ = StopLossManager.structure_based(
            entry=43200.0, direction=Direction.LONG,
            candles=candles, atr=200.0,
        )
        assert sl_combined == max(sl_atr, sl_struct)

    def test_short_picks_most_protective(self):
        """For SHORT, combined should pick the LOWER SL."""
        candles = _make_candles_with_swing()
        sl_combined, _ = StopLossManager.combined(
            entry=43200.0, direction=Direction.SHORT,
            candles=candles, atr=200.0,
        )
        sl_atr, _ = StopLossManager.atr_based(
            entry=43200.0, direction=Direction.SHORT, atr=200.0,
        )
        sl_struct, _ = StopLossManager.structure_based(
            entry=43200.0, direction=Direction.SHORT,
            candles=candles, atr=200.0,
        )
        assert sl_combined == min(sl_atr, sl_struct)


class TestTrailingStop:
    def test_long_trailing(self):
        ts = StopLossManager.trailing_stop(
            current_price=44000.0, direction=Direction.LONG,
            highest_since_entry=44500.0, lowest_since_entry=43000.0,
            atr=200.0,
        )
        assert ts == pytest.approx(44500.0 - 200.0)

    def test_short_trailing(self):
        ts = StopLossManager.trailing_stop(
            current_price=42500.0, direction=Direction.SHORT,
            highest_since_entry=44000.0, lowest_since_entry=42000.0,
            atr=200.0,
        )
        assert ts == pytest.approx(42000.0 + 200.0)

    def test_custom_multiplier(self):
        ts = StopLossManager.trailing_stop(
            current_price=44000.0, direction=Direction.LONG,
            highest_since_entry=44500.0, lowest_since_entry=43000.0,
            atr=200.0, multiplier=1.5,
        )
        assert ts == pytest.approx(44500.0 - 300.0)


class TestMoveToBreakeven:
    def test_move_to_be_after_tp1_long(self):
        new_sl = StopLossManager.should_move_to_breakeven(
            entry=43200.0, current_sl=42900.0,
            direction=Direction.LONG, tp1_hit=True,
        )
        assert new_sl == 43200.0

    def test_move_to_be_after_tp1_short(self):
        new_sl = StopLossManager.should_move_to_breakeven(
            entry=43200.0, current_sl=43500.0,
            direction=Direction.SHORT, tp1_hit=True,
        )
        assert new_sl == 43200.0

    def test_no_move_if_tp1_not_hit(self):
        result = StopLossManager.should_move_to_breakeven(
            entry=43200.0, current_sl=42900.0,
            direction=Direction.LONG, tp1_hit=False,
        )
        assert result is None

    def test_no_move_if_sl_already_better(self):
        """If SL is already above entry for LONG, don't move."""
        result = StopLossManager.should_move_to_breakeven(
            entry=43200.0, current_sl=43300.0,
            direction=Direction.LONG, tp1_hit=True,
        )
        assert result is None
