"""ML Enhancer - integrates ML predictions into signal pipeline."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.config.constants import Direction, MarketRegime
from app.core.models import Candle, CompositeSignal, IndicatorValues, MarketContext
from app.ml.features.engineer import FeatureEngineer
from app.ml.features.scaler import FeatureScaler
from app.ml.models.base import BaseMLModel, ModelState
from app.ml.models.xgboost_model import LABEL_LONG, LABEL_NEUTRAL, LABEL_SHORT


class MLEnhancer:
    """Enhances trading signals with ML predictions.

    Integrates with the signal aggregation pipeline to:
    1. Extract features from market data
    2. Predict signal direction confidence via classifier
    3. Predict market regime via regime model
    4. Detect anomalous conditions
    5. Adjust signal confidence based on ML outputs
    """

    def __init__(
        self,
        signal_model: BaseMLModel | None = None,
        regime_model: BaseMLModel | None = None,
        anomaly_model: BaseMLModel | None = None,
        feature_scaler: FeatureScaler | None = None,
        ml_weight: float = 0.3,
        anomaly_threshold: float = 0.7,
    ) -> None:
        self._feature_engineer = FeatureEngineer()
        self._signal_model = signal_model
        self._regime_model = regime_model
        self._anomaly_model = anomaly_model
        self._scaler = feature_scaler
        self._ml_weight = ml_weight
        self._anomaly_threshold = anomaly_threshold

    @property
    def is_ready(self) -> bool:
        """True if at least the signal model is trained/loaded."""
        return (
            self._signal_model is not None
            and self._signal_model.is_ready
        )

    @property
    def has_regime_model(self) -> bool:
        return self._regime_model is not None and self._regime_model.is_ready

    @property
    def has_anomaly_model(self) -> bool:
        return self._anomaly_model is not None and self._anomaly_model.is_ready

    def extract_features(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
        context: MarketContext | None = None,
    ) -> np.ndarray:
        """Extract and scale features from market data."""
        raw = self._feature_engineer.extract(candles, indicators, context)
        if self._scaler is not None and self._scaler.is_fitted:
            return self._scaler.transform(raw)
        return raw

    def predict_direction(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
        context: MarketContext | None = None,
    ) -> tuple[Direction, float]:
        """Predict signal direction from market data.

        Returns:
            (direction, confidence) tuple.
        """
        if not self.is_ready:
            return Direction.NEUTRAL, 0.0

        features = self.extract_features(candles, indicators, context)
        preds = self._signal_model.predict(features)

        label = preds[0].label
        confidence = preds[0].confidence

        label_to_dir = {
            LABEL_LONG: Direction.LONG,
            LABEL_SHORT: Direction.SHORT,
            LABEL_NEUTRAL: Direction.NEUTRAL,
        }
        return label_to_dir.get(label, Direction.NEUTRAL), confidence

    def predict_regime(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
    ) -> tuple[MarketRegime, float]:
        """Predict market regime using ML model."""
        if not self.has_regime_model:
            return MarketRegime.RANGING, 0.0

        features = self.extract_features(candles, indicators)
        preds = self._regime_model.predict(features)
        regime_name = preds[0].metadata.get("regime", MarketRegime.RANGING.value)
        try:
            regime = MarketRegime(regime_name)
        except ValueError:
            regime = MarketRegime.RANGING
        return regime, preds[0].confidence

    def is_anomalous(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
    ) -> tuple[bool, float]:
        """Check if current market conditions are anomalous."""
        if not self.has_anomaly_model:
            return False, 0.0

        features = self.extract_features(candles, indicators)
        preds = self._anomaly_model.predict(features)
        score = preds[0].confidence
        return score >= self._anomaly_threshold, score

    def enhance_signal(
        self,
        signal: CompositeSignal,
        candles: list[Candle],
        indicators: IndicatorValues,
        context: MarketContext | None = None,
    ) -> CompositeSignal:
        """Enhance a CompositeSignal with ML confidence.

        Adjusts the signal's ml_confidence field based on:
        - Direction agreement between strategy and ML model
        - Anomaly detection (reduces confidence if anomalous)
        - ML model confidence level

        Returns:
            Updated CompositeSignal with ml_confidence set.
        """
        if not self.is_ready:
            return signal

        ml_dir, ml_conf = self.predict_direction(candles, indicators, context)

        # Direction agreement check
        if ml_dir == signal.direction:
            # ML agrees → boost confidence
            adjusted_conf = ml_conf
        elif ml_dir == Direction.NEUTRAL:
            # ML neutral → moderate confidence
            adjusted_conf = ml_conf * 0.5
        else:
            # ML disagrees → reduce confidence
            adjusted_conf = ml_conf * 0.2

        # Anomaly penalty
        if self.has_anomaly_model:
            is_anom, anom_score = self.is_anomalous(candles, indicators)
            if is_anom:
                adjusted_conf *= (1.0 - anom_score * 0.5)

        # Blend: ml_weight * ml_conf + (1-ml_weight) * strategy_strength
        blended = (
            self._ml_weight * adjusted_conf
            + (1.0 - self._ml_weight) * signal.strength
        )
        blended = max(0.0, min(1.0, blended))

        return signal.model_copy(update={"ml_confidence": blended})

    def get_status(self) -> dict[str, Any]:
        """Return status of all ML models."""
        return {
            "is_ready": self.is_ready,
            "signal_model": self._signal_model.get_info() if self._signal_model else None,
            "regime_model": self._regime_model.get_info() if self._regime_model else None,
            "anomaly_model": self._anomaly_model.get_info() if self._anomaly_model else None,
            "ml_weight": self._ml_weight,
            "scaler_fitted": self._scaler.is_fitted if self._scaler else False,
        }
