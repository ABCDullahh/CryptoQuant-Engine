"""Feature engineering pipeline for ML models."""

from __future__ import annotations

import math

import numpy as np

from app.config.constants import MarketRegime
from app.core.models import Candle, IndicatorValues, MarketContext


# Feature group names for documentation and selection
PRICE_FEATURES = [
    "return_1", "return_5", "return_10", "return_20",
    "log_return_1", "volatility_10", "volatility_20",
    "high_low_range", "close_position",
]
INDICATOR_FEATURES = [
    "ema_9_dist", "ema_21_dist", "ema_55_dist", "ema_200_dist",
    "ema_alignment", "macd_norm", "macd_hist_norm", "adx",
    "rsi_14", "stoch_k", "stoch_d",
    "atr_pct", "bb_position", "bb_width",
]
VOLUME_FEATURES = [
    "volume_ratio", "obv_slope", "vwap_dist",
]
TEMPORAL_FEATURES = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend",
]
REGIME_FEATURES = [
    "regime_trending_up", "regime_trending_down", "regime_ranging",
    "regime_high_vol", "regime_low_vol", "regime_choppy",
]

ALL_FEATURE_NAMES = (
    PRICE_FEATURES + INDICATOR_FEATURES + VOLUME_FEATURES
    + TEMPORAL_FEATURES + REGIME_FEATURES
)


class FeatureEngineer:
    """Extracts ML features from candles, indicators, and market context.

    Produces a numpy array of 37 features per sample.
    """

    @property
    def feature_names(self) -> list[str]:
        return list(ALL_FEATURE_NAMES)

    @property
    def n_features(self) -> int:
        return len(ALL_FEATURE_NAMES)

    def extract(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
        context: MarketContext | None = None,
    ) -> np.ndarray:
        """Extract feature vector from current market state.

        Returns 1D numpy array of shape (n_features,).
        """
        features: list[float] = []

        closes = np.array([c.close for c in candles])
        highs = np.array([c.high for c in candles])
        lows = np.array([c.low for c in candles])
        volumes = np.array([c.volume for c in candles])

        # Price features
        features.extend(self._price_features(closes, highs, lows))

        # Indicator features
        features.extend(self._indicator_features(closes[-1], indicators))

        # Volume features
        features.extend(self._volume_features(closes[-1], volumes, indicators))

        # Temporal features
        features.extend(self._temporal_features(candles[-1]))

        # Regime features
        features.extend(self._regime_features(context))

        return np.array(features, dtype=np.float32)

    def extract_batch(
        self,
        candle_windows: list[list[Candle]],
        indicators_list: list[IndicatorValues],
        contexts: list[MarketContext | None] | None = None,
    ) -> np.ndarray:
        """Extract features for multiple samples.

        Returns 2D numpy array of shape (n_samples, n_features).
        """
        if contexts is None:
            contexts = [None] * len(candle_windows)

        rows = []
        for candles, ind, ctx in zip(candle_windows, indicators_list, contexts):
            rows.append(self.extract(candles, ind, ctx))

        return np.vstack(rows)

    # ----------------------------------------------------------------
    # Feature groups
    # ----------------------------------------------------------------

    @staticmethod
    def _price_features(
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
    ) -> list[float]:
        """Extract price-based features (9 features)."""
        n = len(closes)
        current = closes[-1]

        # Returns at different lookbacks
        ret_1 = (current / closes[-2] - 1) if n >= 2 else 0.0
        ret_5 = (current / closes[-6] - 1) if n >= 6 else 0.0
        ret_10 = (current / closes[-11] - 1) if n >= 11 else 0.0
        ret_20 = (current / closes[-21] - 1) if n >= 21 else 0.0

        # Log return
        log_ret = math.log(closes[-1] / closes[-2]) if n >= 2 and closes[-2] > 0 else 0.0

        # Realized volatility
        if n >= 11:
            rets = np.diff(closes[-11:]) / closes[-11:-1]
            vol_10 = float(np.std(rets)) if len(rets) > 0 else 0.0
        else:
            vol_10 = 0.0

        if n >= 21:
            rets = np.diff(closes[-21:]) / closes[-21:-1]
            vol_20 = float(np.std(rets)) if len(rets) > 0 else 0.0
        else:
            vol_20 = 0.0

        # High-low range (normalized)
        hl_range = (highs[-1] - lows[-1]) / current if current > 0 else 0.0

        # Close position within day range
        day_range = highs[-1] - lows[-1]
        close_pos = (current - lows[-1]) / day_range if day_range > 0 else 0.5

        return [ret_1, ret_5, ret_10, ret_20, log_ret, vol_10, vol_20,
                hl_range, close_pos]

    @staticmethod
    def _indicator_features(
        close: float,
        ind: IndicatorValues,
    ) -> list[float]:
        """Extract indicator-based features (14 features)."""
        # EMA distances (normalized by close price)
        def _dist(ema_val):
            if ema_val is None or close == 0:
                return 0.0
            return (close - ema_val) / close

        ema_9_dist = _dist(ind.ema_9)
        ema_21_dist = _dist(ind.ema_21)
        ema_55_dist = _dist(ind.ema_55)
        ema_200_dist = _dist(ind.ema_200)

        # EMA alignment score (-1 to 1): bullish if 9>21>55>200
        emas = [ind.ema_9, ind.ema_21, ind.ema_55, ind.ema_200]
        if all(e is not None for e in emas):
            aligned = 0
            for i in range(len(emas) - 1):
                if emas[i] > emas[i + 1]:
                    aligned += 1
                else:
                    aligned -= 1
            ema_alignment = aligned / 3.0
        else:
            ema_alignment = 0.0

        # MACD normalized by close
        macd_norm = (ind.macd / close * 100) if ind.macd is not None and close > 0 else 0.0
        macd_hist_norm = (ind.macd_histogram / close * 100) if ind.macd_histogram is not None and close > 0 else 0.0

        # ADX (already 0-100 scale)
        adx = ind.adx if ind.adx is not None else 0.0

        # RSI (0-100 scale, normalize to 0-1)
        rsi = (ind.rsi_14 / 100.0) if ind.rsi_14 is not None else 0.5

        # Stochastic
        stoch_k = (ind.stoch_k / 100.0) if ind.stoch_k is not None else 0.5
        stoch_d = (ind.stoch_d / 100.0) if ind.stoch_d is not None else 0.5

        # ATR as percentage of close
        atr_pct = (ind.atr_14 / close) if ind.atr_14 is not None and close > 0 else 0.0

        # Bollinger Band position: where is close relative to bands
        if ind.bb_upper is not None and ind.bb_lower is not None:
            bb_range = ind.bb_upper - ind.bb_lower
            bb_pos = (close - ind.bb_lower) / bb_range if bb_range > 0 else 0.5
        else:
            bb_pos = 0.5

        bb_width = ind.bb_width if ind.bb_width is not None else 0.0

        return [ema_9_dist, ema_21_dist, ema_55_dist, ema_200_dist,
                ema_alignment, macd_norm, macd_hist_norm, adx,
                rsi, stoch_k, stoch_d, atr_pct, bb_pos, bb_width]

    @staticmethod
    def _volume_features(
        close: float,
        volumes: np.ndarray,
        ind: IndicatorValues,
    ) -> list[float]:
        """Extract volume-based features (3 features)."""
        # Volume ratio vs SMA
        if ind.volume_sma_20 is not None and ind.volume_sma_20 > 0:
            vol_ratio = volumes[-1] / ind.volume_sma_20
        else:
            avg = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else float(np.mean(volumes))
            vol_ratio = volumes[-1] / avg if avg > 0 else 1.0

        # OBV slope (normalized)
        obv_slope = 0.0
        if ind.obv is not None and close > 0:
            obv_slope = ind.obv / (close * 1000)  # Rough normalization

        # VWAP distance
        vwap_dist = 0.0
        if ind.vwap is not None and close > 0:
            vwap_dist = (close - ind.vwap) / close

        return [float(vol_ratio), obv_slope, vwap_dist]

    @staticmethod
    def _temporal_features(candle: Candle) -> list[float]:
        """Extract temporal features with cyclical encoding (5 features)."""
        hour = candle.time.hour
        dow = candle.time.weekday()  # 0=Monday, 6=Sunday

        # Sine/cosine encoding for cyclical features
        hour_sin = math.sin(2 * math.pi * hour / 24)
        hour_cos = math.cos(2 * math.pi * hour / 24)
        dow_sin = math.sin(2 * math.pi * dow / 7)
        dow_cos = math.cos(2 * math.pi * dow / 7)
        is_weekend = 1.0 if dow >= 5 else 0.0

        return [hour_sin, hour_cos, dow_sin, dow_cos, is_weekend]

    @staticmethod
    def _regime_features(context: MarketContext | None) -> list[float]:
        """One-hot encode market regime (6 features)."""
        if context is None:
            return [0.0] * 6

        regime = context.regime
        return [
            1.0 if regime == MarketRegime.TRENDING_UP else 0.0,
            1.0 if regime == MarketRegime.TRENDING_DOWN else 0.0,
            1.0 if regime == MarketRegime.RANGING else 0.0,
            1.0 if regime == MarketRegime.HIGH_VOLATILITY else 0.0,
            1.0 if regime == MarketRegime.LOW_VOLATILITY else 0.0,
            1.0 if regime == MarketRegime.CHOPPY else 0.0,
        ]
