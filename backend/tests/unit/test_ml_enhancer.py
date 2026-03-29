"""Unit tests for MLEnhancer - signal pipeline integration."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from app.config.constants import Direction, MarketRegime, SignalGrade, StopLossType
from app.core.models import (
    Candle,
    CompositeSignal,
    IndicatorValues,
    MarketContext,
    PositionSize,
    RiskReward,
    TakeProfit,
)
from app.ml.enhancer import MLEnhancer
from app.ml.features.scaler import FeatureScaler
from app.ml.models.base import BaseMLModel, MLPrediction, ModelState


# -- Helpers --

def _make_candles(n: int = 30) -> list[Candle]:
    np.random.seed(42)
    candles = []
    price = 43000.0
    for i in range(n):
        price += np.random.randn() * 30
        candles.append(Candle(
            time=datetime(2024, 1, 1 + i // 24, i % 24, 0, tzinfo=UTC),
            symbol="BTC/USDT", timeframe="1h",
            open=price - 10, high=price + 30, low=price - 30, close=price,
            volume=100.0,
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


def _make_signal(direction=Direction.LONG) -> CompositeSignal:
    return CompositeSignal(
        symbol="BTC/USDT", direction=direction,
        grade=SignalGrade.B, strength=0.70,
        entry_price=43200.0, entry_zone=(43100.0, 43300.0),
        stop_loss=42900.0, sl_type=StopLossType.ATR_BASED,
        take_profits=[
            TakeProfit(level="TP1", price=43650.0, close_pct=50, rr_ratio=1.5),
        ],
        risk_reward=RiskReward(rr_tp1=1.5, rr_tp2=3.0, rr_tp3=5.0, weighted_rr=2.65),
        position_size=PositionSize(
            quantity=0.5, notional=21600.0, margin=7200.0,
            risk_amount=150.0, risk_pct=0.02, leverage=3,
        ),
        strategy_scores={"momentum": 0.8},
        market_context=MarketContext(),
    )


class MockSignalModel(BaseMLModel):
    """Mock signal model for testing."""

    def __init__(self, label: int = 2, confidence: float = 0.85):
        super().__init__(name="mock_signal", version="1.0")
        self._label = label
        self._conf = confidence
        self.state = ModelState.READY

    def train(self, X, y, **kw):
        return {"accuracy": 0.9}

    def predict(self, X):
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return [
            MLPrediction(label=self._label, confidence=self._conf,
                         probabilities=np.array([0.05, 0.10, 0.85]),
                         metadata={"label_name": "LONG"})
            for _ in range(X.shape[0])
        ]

    def save(self, d): pass
    def load(self, d): pass


class MockRegimeModel(BaseMLModel):
    def __init__(self, regime=MarketRegime.TRENDING_UP, conf=0.8):
        super().__init__(name="mock_regime", version="1.0")
        self._regime = regime
        self._conf = conf
        self.state = ModelState.READY

    def train(self, X, y, **kw):
        return {}

    def predict(self, X):
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return [
            MLPrediction(label=0, confidence=self._conf,
                         metadata={"regime": self._regime.value})
            for _ in range(X.shape[0])
        ]

    def save(self, d): pass
    def load(self, d): pass


class MockAnomalyModel(BaseMLModel):
    def __init__(self, score=0.3):
        super().__init__(name="mock_anomaly", version="1.0")
        self._score = score
        self.state = ModelState.READY

    def train(self, X, y=None, **kw):
        return {}

    def predict(self, X):
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return [
            MLPrediction(label=1, confidence=self._score,
                         metadata={"is_anomaly": self._score >= 0.7})
            for _ in range(X.shape[0])
        ]

    def save(self, d): pass
    def load(self, d): pass


# -- Tests --

class TestIsReady:
    def test_not_ready_no_models(self):
        enhancer = MLEnhancer()
        assert not enhancer.is_ready

    def test_ready_with_signal_model(self):
        enhancer = MLEnhancer(signal_model=MockSignalModel())
        assert enhancer.is_ready

    def test_has_regime_model(self):
        enhancer = MLEnhancer(regime_model=MockRegimeModel())
        assert enhancer.has_regime_model

    def test_has_anomaly_model(self):
        enhancer = MLEnhancer(anomaly_model=MockAnomalyModel())
        assert enhancer.has_anomaly_model


class TestExtractFeatures:
    def test_feature_extraction(self):
        enhancer = MLEnhancer()
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        features = enhancer.extract_features(candles, indicators)
        assert features.shape == (37,)

    def test_with_scaler(self):
        scaler = FeatureScaler(n_features=37)
        data = np.random.RandomState(42).randn(50, 37).astype(np.float32)
        scaler.partial_fit(data)

        enhancer = MLEnhancer(feature_scaler=scaler)
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        features = enhancer.extract_features(candles, indicators)
        assert features.shape == (37,)


class TestPredictDirection:
    def test_predict_long(self):
        enhancer = MLEnhancer(signal_model=MockSignalModel(label=2, confidence=0.85))
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        direction, conf = enhancer.predict_direction(candles, indicators)
        assert direction == Direction.LONG
        assert conf == pytest.approx(0.85)

    def test_predict_short(self):
        enhancer = MLEnhancer(signal_model=MockSignalModel(label=0, confidence=0.7))
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        direction, _ = enhancer.predict_direction(candles, indicators)
        assert direction == Direction.SHORT

    def test_predict_neutral_no_model(self):
        enhancer = MLEnhancer()
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        direction, conf = enhancer.predict_direction(candles, indicators)
        assert direction == Direction.NEUTRAL
        assert conf == 0.0


class TestPredictRegime:
    def test_predict_regime(self):
        enhancer = MLEnhancer(
            regime_model=MockRegimeModel(regime=MarketRegime.HIGH_VOLATILITY, conf=0.75)
        )
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        regime, conf = enhancer.predict_regime(candles, indicators)
        assert regime == MarketRegime.HIGH_VOLATILITY
        assert conf == pytest.approx(0.75)

    def test_no_regime_model_default(self):
        enhancer = MLEnhancer()
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        regime, conf = enhancer.predict_regime(candles, indicators)
        assert regime == MarketRegime.RANGING
        assert conf == 0.0


class TestIsAnomalous:
    def test_normal_conditions(self):
        enhancer = MLEnhancer(anomaly_model=MockAnomalyModel(score=0.3))
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        is_anom, score = enhancer.is_anomalous(candles, indicators)
        assert not is_anom
        assert score == pytest.approx(0.3)

    def test_anomalous_conditions(self):
        enhancer = MLEnhancer(anomaly_model=MockAnomalyModel(score=0.85))
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        is_anom, score = enhancer.is_anomalous(candles, indicators)
        assert is_anom


class TestEnhanceSignal:
    def test_enhance_agrees_long(self):
        """ML agrees with LONG → high ml_confidence."""
        enhancer = MLEnhancer(
            signal_model=MockSignalModel(label=2, confidence=0.9),
            ml_weight=0.3,
        )
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        signal = _make_signal(Direction.LONG)
        enhanced = enhancer.enhance_signal(signal, candles, indicators)
        assert enhanced.ml_confidence is not None
        assert enhanced.ml_confidence > 0.5

    def test_enhance_disagrees(self):
        """ML disagrees with direction → lower ml_confidence."""
        enhancer = MLEnhancer(
            signal_model=MockSignalModel(label=0, confidence=0.9),  # SHORT
            ml_weight=0.3,
        )
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        signal = _make_signal(Direction.LONG)
        enhanced = enhancer.enhance_signal(signal, candles, indicators)
        assert enhanced.ml_confidence is not None
        agree = MLEnhancer(
            signal_model=MockSignalModel(label=2, confidence=0.9),
            ml_weight=0.3,
        ).enhance_signal(signal, candles, indicators)
        assert enhanced.ml_confidence < agree.ml_confidence

    def test_enhance_with_anomaly_penalty(self):
        """Anomaly detected → confidence reduced."""
        enhancer = MLEnhancer(
            signal_model=MockSignalModel(label=2, confidence=0.9),
            anomaly_model=MockAnomalyModel(score=0.8),
            ml_weight=0.3,
        )
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        signal = _make_signal(Direction.LONG)
        enhanced = enhancer.enhance_signal(signal, candles, indicators)
        normal = MLEnhancer(
            signal_model=MockSignalModel(label=2, confidence=0.9),
            anomaly_model=MockAnomalyModel(score=0.2),
            ml_weight=0.3,
        ).enhance_signal(signal, candles, indicators)
        assert enhanced.ml_confidence < normal.ml_confidence

    def test_enhance_no_model_returns_unchanged(self):
        enhancer = MLEnhancer()
        signal = _make_signal()
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        enhanced = enhancer.enhance_signal(signal, candles, indicators)
        assert enhanced.ml_confidence is None

    def test_ml_confidence_bounded(self):
        enhancer = MLEnhancer(
            signal_model=MockSignalModel(label=2, confidence=1.0),
            ml_weight=0.5,
        )
        candles = _make_candles()
        indicators = _make_indicators(candles[-1].close)
        signal = _make_signal(Direction.LONG)
        enhanced = enhancer.enhance_signal(signal, candles, indicators)
        assert 0.0 <= enhanced.ml_confidence <= 1.0


class TestGetStatus:
    def test_status_no_models(self):
        enhancer = MLEnhancer()
        status = enhancer.get_status()
        assert status["is_ready"] is False
        assert status["signal_model"] is None

    def test_status_with_models(self):
        enhancer = MLEnhancer(
            signal_model=MockSignalModel(),
            regime_model=MockRegimeModel(),
        )
        status = enhancer.get_status()
        assert status["is_ready"] is True
        assert status["signal_model"]["name"] == "mock_signal"
