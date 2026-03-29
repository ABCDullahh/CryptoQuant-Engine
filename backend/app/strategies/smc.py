"""Smart Money Concepts (SMC) Strategy.

Detects institutional order flow via structure breaks, order blocks,
fair value gaps, and liquidity sweeps.
"""

from __future__ import annotations

from app.config.constants import Direction, MarketRegime
from app.core.models import Candle, IndicatorValues, MarketContext, RawSignal
from app.strategies.base import BaseStrategy

# Used for reference only — regime adaptation handled by aggregator
_BLOCKED_REGIMES = {MarketRegime.HIGH_VOLATILITY}


class SmartMoneyStrategy(BaseStrategy):
    """Smart Money Concepts strategy (highest weight).

    LONG conditions:
    - Bullish structure break (higher high after series of lower lows)
    - Bullish order block nearby (large bullish candle at support)
    - Fair value gap above (unfilled gap as target)
    - Price in discount zone (below 50% of recent range)

    SHORT conditions:
    - Bearish structure break (lower low after series of higher highs)
    - Bearish order block nearby
    - Fair value gap below
    - Price in premium zone (above 50% of recent range)
    """

    name = "smart_money"
    weight = 0.25
    min_candles = 100

    # Lookback for swing detection
    SWING_LOOKBACK = 5
    # Minimum body-to-range ratio for order block candle
    OB_BODY_RATIO = 0.6
    # Number of recent candles to search for order blocks
    OB_SEARCH_WINDOW = 20

    def evaluate(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
        context: MarketContext | None = None,
    ) -> RawSignal | None:
        if len(candles) < self.min_candles:
            return None

        adx = indicators.adx
        atr = indicators.atr_14
        if atr is None:
            return None

        close = candles[-1].close
        symbol = candles[-1].symbol
        timeframe = candles[-1].timeframe

        # Detect structures
        structure = self._detect_structure_break(candles)
        order_blocks = self._find_order_blocks(candles)
        fvgs = self._find_fair_value_gaps(candles)
        sweep = self._detect_liquidity_sweep(candles)

        # Price zone (discount/premium)
        recent = candles[-50:]
        range_high = max(c.high for c in recent)
        range_low = min(c.low for c in recent)
        range_size = range_high - range_low
        if range_size == 0:
            return None
        price_zone = (close - range_low) / range_size  # 0=bottom, 1=top

        # --- LONG scoring ---
        long_conditions = []
        long_score = 0.0

        if structure == "bullish":
            long_conditions.append("BULLISH_STRUCTURE_BREAK")
            long_score += 0.30

        if any(ob["type"] == "bullish" for ob in order_blocks):
            long_conditions.append("BULLISH_ORDER_BLOCK")
            long_score += 0.25

        if any(fvg["type"] == "bullish" for fvg in fvgs):
            long_conditions.append("BULLISH_FVG")
            long_score += 0.15

        if price_zone < 0.4:
            long_conditions.append("DISCOUNT_ZONE")
            long_score += 0.20

        if sweep == "bearish_sweep":
            long_conditions.append("LIQUIDITY_SWEEP_DOWN")
            long_score += 0.10

        # --- SHORT scoring ---
        short_conditions = []
        short_score = 0.0

        if structure == "bearish":
            short_conditions.append("BEARISH_STRUCTURE_BREAK")
            short_score += 0.30

        if any(ob["type"] == "bearish" for ob in order_blocks):
            short_conditions.append("BEARISH_ORDER_BLOCK")
            short_score += 0.25

        if any(fvg["type"] == "bearish" for fvg in fvgs):
            short_conditions.append("BEARISH_FVG")
            short_score += 0.15

        if price_zone > 0.6:
            short_conditions.append("PREMIUM_ZONE")
            short_score += 0.20

        if sweep == "bullish_sweep":
            short_conditions.append("LIQUIDITY_SWEEP_UP")
            short_score += 0.10

        if long_score >= 0.50 and long_score > short_score:
            return self._create_signal(
                direction=Direction.LONG,
                strength=long_score,
                entry_price=close,
                symbol=symbol,
                timeframe=timeframe,
                conditions=long_conditions,
                metadata={
                    "price_zone": price_zone,
                    "structure": structure,
                    "order_blocks": len(order_blocks),
                    "fvgs": len(fvgs),
                },
            )

        if short_score >= 0.50 and short_score > long_score:
            return self._create_signal(
                direction=Direction.SHORT,
                strength=-short_score,
                entry_price=close,
                symbol=symbol,
                timeframe=timeframe,
                conditions=short_conditions,
                metadata={
                    "price_zone": price_zone,
                    "structure": structure,
                    "order_blocks": len(order_blocks),
                    "fvgs": len(fvgs),
                },
            )

        return None

    def _detect_structure_break(self, candles: list[Candle]) -> str | None:
        """Detect market structure break.

        Bullish: price breaks above recent swing high.
        Bearish: price breaks below recent swing low.
        """
        lb = self.SWING_LOOKBACK
        if len(candles) < lb * 3:
            return None

        # Find swing highs and lows in recent candles
        swing_highs = []
        swing_lows = []
        search = candles[-(lb * 6):]

        for i in range(lb, len(search) - lb):
            if all(search[i].high >= search[i - j].high for j in range(1, lb + 1)) and \
               all(search[i].high >= search[i + j].high for j in range(1, lb + 1)):
                swing_highs.append(search[i].high)

            if all(search[i].low <= search[i - j].low for j in range(1, lb + 1)) and \
               all(search[i].low <= search[i + j].low for j in range(1, lb + 1)):
                swing_lows.append(search[i].low)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return None

        last_close = candles[-1].close

        # Bullish break: close above last swing high
        if last_close > swing_highs[-1]:
            return "bullish"

        # Bearish break: close below last swing low
        if last_close < swing_lows[-1]:
            return "bearish"

        return None

    def _find_order_blocks(self, candles: list[Candle]) -> list[dict]:
        """Find order blocks (large institutional candles).

        An order block is a large-body candle before a strong move in the
        opposite direction. They represent institutional entry points.
        """
        blocks = []
        window = candles[-self.OB_SEARCH_WINDOW:]

        for i in range(len(window) - 1):
            c = window[i]
            body = abs(c.close - c.open)
            total_range = c.high - c.low

            if total_range == 0:
                continue

            body_ratio = body / total_range

            if body_ratio >= self.OB_BODY_RATIO:
                if c.close > c.open:
                    blocks.append({
                        "type": "bullish",
                        "high": c.high,
                        "low": c.low,
                    })
                else:
                    blocks.append({
                        "type": "bearish",
                        "high": c.high,
                        "low": c.low,
                    })

        return blocks

    def _find_fair_value_gaps(self, candles: list[Candle]) -> list[dict]:
        """Find Fair Value Gaps (FVGs).

        Bullish FVG: candle[i-1].high < candle[i+1].low (gap up)
        Bearish FVG: candle[i-1].low > candle[i+1].high (gap down)
        """
        fvgs = []
        window = candles[-self.OB_SEARCH_WINDOW:]

        for i in range(1, len(window) - 1):
            prev_high = window[i - 1].high
            next_low = window[i + 1].low
            prev_low = window[i - 1].low
            next_high = window[i + 1].high

            if prev_high < next_low:
                fvgs.append({
                    "type": "bullish",
                    "top": next_low,
                    "bottom": prev_high,
                })

            if prev_low > next_high:
                fvgs.append({
                    "type": "bearish",
                    "top": prev_low,
                    "bottom": next_high,
                })

        return fvgs

    def _detect_liquidity_sweep(self, candles: list[Candle]) -> str | None:
        """Detect liquidity sweep (stop hunt).

        Bearish sweep: price wicks below recent low then closes above it.
        Bullish sweep: price wicks above recent high then closes below it.
        """
        if len(candles) < 20:
            return None

        recent = candles[-20:-1]  # Exclude last candle
        last = candles[-1]

        recent_low = min(c.low for c in recent)
        recent_high = max(c.high for c in recent)

        # Bearish sweep → bullish reversal signal
        if last.low < recent_low and last.close > recent_low:
            return "bearish_sweep"

        # Bullish sweep → bearish reversal signal
        if last.high > recent_high and last.close < recent_high:
            return "bullish_sweep"

        return None
