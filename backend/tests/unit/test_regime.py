"""Unit tests for MarketRegimeDetector."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config.constants import MarketRegime
from app.core.models import Candle, IndicatorValues, MarketContext
from app.signals.regime import MarketRegimeDetector


def _make_candle(close: float = 43200.0, volume: float = 100.0) -> Candle:
    return Candle(
        time=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        symbol="BTC/USDT", timeframe="1h",
        open=43000.0, high=43500.0, low=42900.0, close=close,
        volume=volume,
    )


def _make_indicators(**overrides) -> IndicatorValues:
    defaults = dict(
        symbol="BTC/USDT", timeframe="1h",
        timestamp=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        ema_9=43200.0, ema_21=43100.0, ema_55=43000.0,
        adx=30.0, bb_width=0.025, atr_14=200.0,
        volume_sma_20=100.0,
    )
    defaults.update(overrides)
    return IndicatorValues(**defaults)


class TestMarketRegimeDetector:
    def test_detect_returns_market_context(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle()]
        indicators = _make_indicators()
        result = detector.detect(candles, indicators)
        assert isinstance(result, MarketContext)

    def test_trending_up(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle()]
        indicators = _make_indicators(
            adx=30.0, ema_9=43200.0, ema_21=43100.0, bb_width=0.025,
        )
        result = detector.detect(candles, indicators)
        assert result.regime == MarketRegime.TRENDING_UP

    def test_trending_down(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle()]
        indicators = _make_indicators(
            adx=30.0, ema_9=43000.0, ema_21=43100.0, bb_width=0.025,
        )
        result = detector.detect(candles, indicators)
        assert result.regime == MarketRegime.TRENDING_DOWN

    def test_ranging(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle()]
        indicators = _make_indicators(adx=15.0, bb_width=0.025)
        result = detector.detect(candles, indicators)
        assert result.regime == MarketRegime.RANGING

    def test_high_volatility(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle()]
        indicators = _make_indicators(bb_width=0.06)
        result = detector.detect(candles, indicators)
        assert result.regime == MarketRegime.HIGH_VOLATILITY

    def test_low_volatility(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle()]
        indicators = _make_indicators(bb_width=0.01)
        result = detector.detect(candles, indicators)
        assert result.regime == MarketRegime.LOW_VOLATILITY

    def test_choppy_strong_adx_no_alignment(self):
        """Strong ADX but EMAs are None → choppy."""
        detector = MarketRegimeDetector()
        candles = [_make_candle()]
        indicators = _make_indicators(
            adx=30.0, ema_9=None, ema_21=None, bb_width=0.025,
        )
        result = detector.detect(candles, indicators)
        assert result.regime == MarketRegime.CHOPPY

    def test_choppy_middle_adx(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle()]
        indicators = _make_indicators(adx=22.0, bb_width=0.025)
        result = detector.detect(candles, indicators)
        assert result.regime == MarketRegime.CHOPPY

    def test_trend_direction_strong_up(self):
        detector = MarketRegimeDetector()
        indicators = _make_indicators(
            ema_9=43300.0, ema_21=43200.0, ema_55=43100.0,
        )
        result = detector._detect_trend_direction(indicators)
        assert result == "STRONG_UP"

    def test_trend_direction_strong_down(self):
        detector = MarketRegimeDetector()
        indicators = _make_indicators(
            ema_9=43000.0, ema_21=43100.0, ema_55=43200.0,
        )
        result = detector._detect_trend_direction(indicators)
        assert result == "STRONG_DOWN"

    def test_trend_direction_up(self):
        detector = MarketRegimeDetector()
        indicators = _make_indicators(ema_9=43200.0, ema_21=43100.0, ema_55=None)
        result = detector._detect_trend_direction(indicators)
        assert result == "UP"

    def test_trend_direction_neutral(self):
        detector = MarketRegimeDetector()
        indicators = _make_indicators(ema_9=None, ema_21=None)
        result = detector._detect_trend_direction(indicators)
        assert result == "NEUTRAL"

    def test_volatility_high(self):
        detector = MarketRegimeDetector()
        indicators = _make_indicators(bb_width=0.06)
        assert detector._classify_volatility(indicators) == "HIGH"

    def test_volatility_low(self):
        detector = MarketRegimeDetector()
        indicators = _make_indicators(bb_width=0.01)
        assert detector._classify_volatility(indicators) == "LOW"

    def test_volatility_medium(self):
        detector = MarketRegimeDetector()
        indicators = _make_indicators(bb_width=0.025)
        assert detector._classify_volatility(indicators) == "MEDIUM"

    def test_volatility_none(self):
        detector = MarketRegimeDetector()
        indicators = _make_indicators(bb_width=None)
        assert detector._classify_volatility(indicators) == "MEDIUM"

    def test_volume_very_high(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle(volume=250.0)]
        indicators = _make_indicators(volume_sma_20=100.0)
        assert detector._classify_volume(candles, indicators) == "VERY_HIGH"

    def test_volume_high(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle(volume=160.0)]
        indicators = _make_indicators(volume_sma_20=100.0)
        assert detector._classify_volume(candles, indicators) == "HIGH"

    def test_volume_low(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle(volume=40.0)]
        indicators = _make_indicators(volume_sma_20=100.0)
        assert detector._classify_volume(candles, indicators) == "LOW"

    def test_volume_average(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle(volume=100.0)]
        indicators = _make_indicators(volume_sma_20=100.0)
        assert detector._classify_volume(candles, indicators) == "AVERAGE"

    def test_volume_no_sma(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle()]
        indicators = _make_indicators(volume_sma_20=None)
        assert detector._classify_volume(candles, indicators) == "AVERAGE"

    def test_full_detect_populates_all_fields(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle(volume=200.0)]
        indicators = _make_indicators()
        result = detector.detect(candles, indicators)
        assert result.regime is not None
        assert result.trend_1h is not None
        assert result.volatility is not None
        assert result.volume_profile is not None

    def test_adx_none_defaults_to_choppy(self):
        detector = MarketRegimeDetector()
        candles = [_make_candle()]
        indicators = _make_indicators(adx=None, bb_width=0.025)
        result = detector.detect(candles, indicators)
        assert result.regime == MarketRegime.CHOPPY
