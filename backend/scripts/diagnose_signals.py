"""Diagnose signal pipeline — run strategies on current data and show results."""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.data.providers.binance import BinanceProvider
from app.data.normalization.normalizer import DataNormalizer
from app.indicators.base import IndicatorPipeline
from app.signals.regime import MarketRegimeDetector
from app.strategies import STRATEGY_REGISTRY
from app.config.constants import MIN_STRATEGY_AGREEMENT


async def main():
    provider = BinanceProvider()
    normalizer = DataNormalizer()
    pipeline = IndicatorPipeline()
    regime_detector = MarketRegimeDetector()

    await provider.connect()

    for symbol in ["BTC/USDT", "ETH/USDT"]:
        print(f"\n{'='*60}")
        print(f"  Diagnosing: {symbol} 1m")
        print(f"{'='*60}")

        # Fetch candles
        raw = await provider.fetch_ohlcv(symbol, "1m", limit=200)
        candles = normalizer.normalize_candles(raw, symbol, "1m")
        print(f"Candles loaded: {len(candles)}")
        if candles:
            print(f"  Last candle: close={candles[-1].close}, time={candles[-1].time}")
            print(f"  Volume: {candles[-1].volume}")

        # Compute indicators
        indicators = pipeline.compute(candles)
        print(f"\nIndicators:")
        print(f"  EMA 9:  {indicators.ema_9}")
        print(f"  EMA 21: {indicators.ema_21}")
        print(f"  EMA 55: {indicators.ema_55}")
        print(f"  RSI:    {indicators.rsi_14}")
        print(f"  MACD H: {indicators.macd_histogram}")
        print(f"  ADX:    {indicators.adx}")
        print(f"  ATR:    {indicators.atr_14}")
        print(f"  OBV:    {indicators.obv}")
        print(f"  VWAP:   {indicators.vwap}")
        print(f"  VolSMA: {indicators.volume_sma_20}")
        print(f"  BB W:   {indicators.bb_width}")

        # Detect regime
        context = regime_detector.detect(candles, indicators)
        print(f"\nRegime: {context.regime}")
        print(f"  Trend: {context.trend_1h}")
        print(f"  Volatility: {context.volatility}")
        print(f"  Volume: {context.volume_profile}")

        # Run each strategy
        print(f"\nStrategy Results (MIN_AGREEMENT={MIN_STRATEGY_AGREEMENT}):")
        strategies_to_test = ["momentum", "mean_reversion", "smc", "volume_analysis"]
        signals = []
        for name in strategies_to_test:
            cls = STRATEGY_REGISTRY.get(name)
            if not cls:
                print(f"  {name}: NOT FOUND in registry")
                continue
            strategy = cls()
            try:
                sig = strategy.evaluate(candles, indicators, context)
                if sig:
                    signals.append(sig)
                    print(f"  {name}: {sig.direction} (strength={sig.strength:.3f}) conditions={sig.conditions}")
                else:
                    print(f"  {name}: None (no signal)")
            except Exception as e:
                print(f"  {name}: ERROR - {e}")

        print(f"\nTotal signals: {len(signals)}")
        if signals:
            from collections import Counter
            dir_counts = Counter(s.direction for s in signals)
            print(f"Direction counts: {dict(dir_counts)}")
            dominant_dir, dominant_count = dir_counts.most_common(1)[0]
            print(f"Dominant: {dominant_dir} x {dominant_count}")
            if dominant_count >= MIN_STRATEGY_AGREEMENT:
                agreeing = [s for s in signals if s.direction == dominant_dir]
                avg_strength = sum(abs(s.strength) for s in agreeing) / len(agreeing)
                grade = "A" if avg_strength >= 0.80 else "B" if avg_strength >= 0.60 else "C" if avg_strength >= 0.40 else "D"
                print(f"Would produce: {dominant_dir} grade={grade} strength={avg_strength:.3f}")
            else:
                print(f"NOT ENOUGH: {dominant_count} < {MIN_STRATEGY_AGREEMENT}")

    await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
