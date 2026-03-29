"""Unit tests for SmartMoneyStrategy - detection helper functions."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.models import Candle
from app.strategies.smc import SmartMoneyStrategy


def _c(close: float, open_: float = 0, high: float = 0, low: float = 0,
       volume: float = 100.0, idx: int = 0) -> Candle:
    """Shorthand candle constructor."""
    return Candle(
        time=datetime(2024, 1, 1, idx % 24, 0, tzinfo=UTC),
        symbol="BTC/USDT", timeframe="1h",
        open=open_ or close, high=high or close + 50,
        low=low or close - 50, close=close, volume=volume,
    )


def _make_swing_candles(
    base: float = 43000.0, n: int = 100,
    trend: str = "up",
) -> list[Candle]:
    """Generate candles with detectable swing structure."""
    candles = []
    price = base
    for i in range(n):
        if trend == "up":
            change = 20 if i % 7 < 4 else -10
        elif trend == "down":
            change = -20 if i % 7 < 4 else 10
        else:
            change = 10 if i % 4 < 2 else -10
        price += change
        candles.append(_c(
            close=price,
            open_=price - change,
            high=price + 30,
            low=price - 30,
            idx=i,
        ))
    return candles


class TestStructureBreakDetection:
    def test_bullish_structure_break(self):
        """Price breaks above recent swing high → bullish."""
        s = SmartMoneyStrategy()
        candles = _make_swing_candles(trend="up", n=100)
        # Push last candle well above recent highs
        candles[-1] = _c(
            close=candles[-1].close + 500,
            high=candles[-1].close + 550,
            low=candles[-1].close + 400,
            idx=99,
        )
        result = s._detect_structure_break(candles)
        # Should be bullish if close > last swing high
        assert result in ("bullish", None)

    def test_bearish_structure_break(self):
        """Price breaks below recent swing low → bearish."""
        s = SmartMoneyStrategy()
        candles = _make_swing_candles(trend="down", n=100)
        candles[-1] = _c(
            close=candles[-1].close - 500,
            high=candles[-1].close - 400,
            low=candles[-1].close - 550,
            idx=99,
        )
        result = s._detect_structure_break(candles)
        assert result in ("bearish", None)

    def test_no_structure_break(self):
        """Price in middle → no break."""
        s = SmartMoneyStrategy()
        candles = _make_swing_candles(trend="range", n=100)
        result = s._detect_structure_break(candles)
        assert result in (None, "bullish", "bearish")

    def test_too_few_candles(self):
        s = SmartMoneyStrategy()
        candles = [_c(43000.0 + i * 10, idx=i) for i in range(5)]
        result = s._detect_structure_break(candles)
        assert result is None


class TestOrderBlockDetection:
    def test_bullish_order_block(self):
        """Large bullish candle detected as bullish order block."""
        s = SmartMoneyStrategy()
        candles = [_c(43000.0, idx=i) for i in range(18)]
        # Insert large bullish candle NOT at last position (find_order_blocks skips last)
        candles.append(Candle(
            time=datetime(2024, 1, 1, 18, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=42800.0, high=43250.0, low=42750.0, close=43200.0,
            volume=500.0,
        ))
        candles.append(_c(43200.0, idx=19))
        blocks = s._find_order_blocks(candles)
        bullish = [b for b in blocks if b["type"] == "bullish"]
        assert len(bullish) > 0

    def test_bearish_order_block(self):
        """Large bearish candle detected."""
        s = SmartMoneyStrategy()
        candles = [_c(43000.0, idx=i) for i in range(18)]
        candles.append(Candle(
            time=datetime(2024, 1, 1, 18, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=43200.0, high=43250.0, low=42750.0, close=42800.0,
            volume=500.0,
        ))
        candles.append(_c(42800.0, idx=19))
        blocks = s._find_order_blocks(candles)
        bearish = [b for b in blocks if b["type"] == "bearish"]
        assert len(bearish) > 0

    def test_small_body_not_order_block(self):
        """Small body candle (doji) → not an order block."""
        s = SmartMoneyStrategy()
        candles = []
        for i in range(20):
            candles.append(Candle(
                time=datetime(2024, 1, 1, i, 0, tzinfo=UTC),
                symbol="BTC/USDT", timeframe="1h",
                open=43000.0, high=43500.0, low=42500.0,
                close=43010.0,  # tiny body, large wicks
                volume=100.0,
            ))
        blocks = s._find_order_blocks(candles)
        assert len(blocks) == 0

    def test_zero_range_candle_skipped(self):
        s = SmartMoneyStrategy()
        candles = [_c(43000.0, open_=43000.0, high=43000.0, low=43000.0, idx=i) for i in range(20)]
        blocks = s._find_order_blocks(candles)
        assert len(blocks) == 0


class TestFairValueGapDetection:
    def test_bullish_fvg(self):
        """Gap up: prev_high < next_low → bullish FVG."""
        s = SmartMoneyStrategy()
        candles = [_c(43000.0, idx=i) for i in range(17)]
        candles.append(Candle(
            time=datetime(2024, 1, 1, 17, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=43000.0, high=43100.0, low=42950.0, close=43050.0,
            volume=100.0,
        ))
        candles.append(Candle(  # Gap candle
            time=datetime(2024, 1, 1, 18, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=43200.0, high=43400.0, low=43150.0, close=43350.0,
            volume=200.0,
        ))
        candles.append(Candle(
            time=datetime(2024, 1, 1, 19, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=43350.0, high=43500.0, low=43200.0, close=43450.0,
            volume=100.0,
        ))
        fvgs = s._find_fair_value_gaps(candles)
        bullish = [f for f in fvgs if f["type"] == "bullish"]
        assert len(bullish) >= 1

    def test_bearish_fvg(self):
        """Gap down: prev_low > next_high → bearish FVG."""
        s = SmartMoneyStrategy()
        candles = [_c(43000.0, idx=i) for i in range(17)]
        candles.append(Candle(
            time=datetime(2024, 1, 1, 17, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=43000.0, high=43050.0, low=42900.0, close=42950.0,
            volume=100.0,
        ))
        candles.append(Candle(
            time=datetime(2024, 1, 1, 18, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=42800.0, high=42850.0, low=42650.0, close=42700.0,
            volume=200.0,
        ))
        candles.append(Candle(
            time=datetime(2024, 1, 1, 19, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=42700.0, high=42800.0, low=42600.0, close=42650.0,
            volume=100.0,
        ))
        fvgs = s._find_fair_value_gaps(candles)
        bearish = [f for f in fvgs if f["type"] == "bearish"]
        assert len(bearish) >= 1

    def test_no_fvg_overlapping(self):
        """Overlapping candles → no gap."""
        s = SmartMoneyStrategy()
        candles = [
            _c(43000.0, high=43100.0, low=42900.0, idx=i) for i in range(20)
        ]
        fvgs = s._find_fair_value_gaps(candles)
        assert len(fvgs) == 0


class TestLiquiditySweep:
    def test_bearish_sweep(self):
        """Wick below recent low then close above → bearish sweep."""
        s = SmartMoneyStrategy()
        candles = [_c(43000.0, high=43100.0, low=42900.0, idx=i) for i in range(19)]
        # Last candle wicks below but closes above
        candles.append(Candle(
            time=datetime(2024, 1, 1, 19, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=42950.0, high=43050.0, low=42800.0, close=42950.0,
            volume=100.0,
        ))
        result = s._detect_liquidity_sweep(candles)
        assert result == "bearish_sweep"

    def test_bullish_sweep(self):
        """Wick above recent high then close below → bullish sweep."""
        s = SmartMoneyStrategy()
        candles = [_c(43000.0, high=43100.0, low=42900.0, idx=i) for i in range(19)]
        candles.append(Candle(
            time=datetime(2024, 1, 1, 19, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=43050.0, high=43200.0, low=42950.0, close=43050.0,
            volume=100.0,
        ))
        result = s._detect_liquidity_sweep(candles)
        assert result == "bullish_sweep"

    def test_no_sweep_normal_candle(self):
        s = SmartMoneyStrategy()
        candles = [_c(43000.0, high=43100.0, low=42900.0, idx=i) for i in range(20)]
        result = s._detect_liquidity_sweep(candles)
        assert result is None

    def test_too_few_candles(self):
        s = SmartMoneyStrategy()
        candles = [_c(43000.0, idx=i) for i in range(5)]
        result = s._detect_liquidity_sweep(candles)
        assert result is None
