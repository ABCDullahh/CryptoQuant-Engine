"""Unit tests for FeatureEngineer - ML feature extraction."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from app.config.constants import MarketRegime
from app.core.models import Candle, IndicatorValues, MarketContext
from app.ml.features.engineer import (
    ALL_FEATURE_NAMES,
    FeatureEngineer,
)


def _make_candles(n: int = 30, base_price: float = 43000.0) -> list[Candle]:
    np.random.seed(42)
    candles = []
    price = base_price
    for i in range(n):
        price += np.random.randn() * 30
        candles.append(Candle(
            time=datetime(2024, 1, 1 + i // 24, i % 24, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=price - 10, high=price + 30, low=price - 30, close=price,
            volume=100.0 + np.random.randn() * 20,
        ))
    return candles


def _make_indicators(close: float = 43200.0) -> IndicatorValues:
    return IndicatorValues(
        symbol="BTC/USDT", timeframe="1h",
        timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
        ema_9=close + 50, ema_21=close - 20, ema_55=close - 80,
        ema_200=close - 200,
        macd=50.0, macd_signal=30.0, macd_histogram=20.0, adx=28.0,
        rsi_14=55.0, stoch_k=60.0, stoch_d=58.0,
        atr_14=200.0, bb_upper=close + 300, bb_middle=close,
        bb_lower=close - 300, bb_width=0.028,
        vwap=close - 50, obv=50000.0, volume_sma_20=120.0,
    )


class TestExtract:
    def test_output_shape(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        features = fe.extract(candles, indicators)
        assert features.shape == (fe.n_features,)
        assert features.dtype == np.float32

    def test_feature_count_matches_names(self):
        fe = FeatureEngineer()
        assert fe.n_features == len(ALL_FEATURE_NAMES)
        assert fe.n_features == 37

    def test_no_nan_with_full_data(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        features = fe.extract(candles, indicators)
        assert not np.any(np.isnan(features))

    def test_with_market_context(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        context = MarketContext(regime=MarketRegime.TRENDING_UP)
        features = fe.extract(candles, indicators, context)
        assert features.shape == (fe.n_features,)

    def test_without_market_context(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        features = fe.extract(candles, indicators, None)
        # Regime features should be all zeros
        regime_start = len(ALL_FEATURE_NAMES) - 6
        assert np.all(features[regime_start:] == 0.0)

    def test_minimal_candles(self):
        """2 candles is the minimum for returns."""
        fe = FeatureEngineer()
        candles = _make_candles(2)
        indicators = _make_indicators(candles[-1].close)
        features = fe.extract(candles, indicators)
        assert features.shape == (fe.n_features,)
        assert not np.any(np.isnan(features))


class TestExtractBatch:
    def test_batch_output_shape(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        batch = fe.extract_batch(
            [candles, candles],
            [indicators, indicators],
        )
        assert batch.shape == (2, fe.n_features)

    def test_batch_with_contexts(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        contexts = [
            MarketContext(regime=MarketRegime.TRENDING_UP),
            MarketContext(regime=MarketRegime.RANGING),
        ]
        batch = fe.extract_batch([candles, candles], [indicators, indicators], contexts)
        assert batch.shape == (2, fe.n_features)
        # Different regimes → different regime features
        assert not np.array_equal(batch[0, -6:], batch[1, -6:])


class TestPriceFeatures:
    def test_returns_positive_uptrend(self):
        fe = FeatureEngineer()
        candles = []
        for i in range(30):
            price = 43000.0 + i * 50  # Clear uptrend
            candles.append(Candle(
                time=datetime(2024, 1, 1, i % 24, 0, tzinfo=UTC),
                symbol="BTC/USDT", timeframe="1h",
                open=price - 10, high=price + 30, low=price - 30, close=price,
                volume=100.0,
            ))
        indicators = _make_indicators(candles[-1].close)
        features = fe.extract(candles, indicators)
        # return_1 should be positive
        assert features[0] > 0  # return_1

    def test_close_position_range(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        features = fe.extract(candles, indicators)
        close_pos = features[8]  # close_position
        assert 0.0 <= close_pos <= 1.0


class TestIndicatorFeatures:
    def test_rsi_normalized(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        features = fe.extract(candles, indicators)
        # RSI is at index 9+8 = 17 (after 9 price features)
        rsi_idx = 9 + 8  # rsi_14 in indicator features
        assert 0.0 <= features[rsi_idx] <= 1.0

    def test_ema_alignment_bullish(self):
        """When EMA9 > EMA21 > EMA55 > EMA200, alignment = 1.0."""
        fe = FeatureEngineer()
        candles = _make_candles(30)
        close = candles[-1].close
        indicators = _make_indicators(close)
        # Override to ensure perfect alignment
        indicators.ema_9 = close + 100
        indicators.ema_21 = close + 50
        indicators.ema_55 = close
        indicators.ema_200 = close - 100
        features = fe.extract(candles, indicators)
        ema_align_idx = 9 + 4  # ema_alignment
        assert features[ema_align_idx] == pytest.approx(1.0)

    def test_bb_position_range(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        features = fe.extract(candles, indicators)
        bb_pos_idx = 9 + 12  # bb_position
        assert 0.0 <= features[bb_pos_idx] <= 1.0

    def test_none_indicators_handled(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        # All None indicators
        indicators = IndicatorValues(
            symbol="BTC/USDT", timeframe="1h",
            timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
        )
        features = fe.extract(candles, indicators)
        assert not np.any(np.isnan(features))


class TestTemporalFeatures:
    def test_cyclical_encoding_range(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        features = fe.extract(candles, indicators)
        # Temporal features start after price(9)+indicator(14)+volume(3)=26
        temporal_start = 26
        for i in range(4):  # sin/cos features
            assert -1.0 <= features[temporal_start + i] <= 1.0

    def test_weekend_flag(self):
        fe = FeatureEngineer()
        # Create candle on a Saturday (2024-01-06 is Saturday)
        candles = [Candle(
            time=datetime(2024, 1, 6, 12, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=43190.0, high=43230.0, low=43170.0, close=43200.0,
            volume=100.0,
        )] * 2
        indicators = _make_indicators(43200.0)
        features = fe.extract(candles, indicators)
        is_weekend_idx = 26 + 4  # is_weekend
        assert features[is_weekend_idx] == 1.0


class TestRegimeFeatures:
    def test_one_hot_trending_up(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        context = MarketContext(regime=MarketRegime.TRENDING_UP)
        features = fe.extract(candles, indicators, context)
        regime_start = 31  # After price(9)+ind(14)+vol(3)+temp(5)
        assert features[regime_start] == 1.0  # trending_up
        assert features[regime_start + 1] == 0.0  # trending_down
        assert sum(features[regime_start:regime_start + 6]) == 1.0

    def test_all_regimes_one_hot(self):
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        regime_start = 31
        for regime in MarketRegime:
            context = MarketContext(regime=regime)
            features = fe.extract(candles, indicators, context)
            assert sum(features[regime_start:regime_start + 6]) == 1.0


class TestFeatureNames:
    def test_names_match_output(self):
        fe = FeatureEngineer()
        assert len(fe.feature_names) == fe.n_features

    def test_names_are_unique(self):
        fe = FeatureEngineer()
        assert len(set(fe.feature_names)) == len(fe.feature_names)
