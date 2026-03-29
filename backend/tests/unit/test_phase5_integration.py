"""Phase 5 Integration Tests - ML pipeline end-to-end flow."""

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
from app.ml import (
    ALL_FEATURE_NAMES,
    AnomalyDetector,
    FeatureEngineer,
    FeatureScaler,
    MLEnhancer,
    ModelTrainer,
    RegimeClassifier,
    XGBoostSignalModel,
)
from app.ml.models.base import ModelState
from app.ml.models.xgboost_model import LABEL_LONG, LABEL_NEUTRAL, LABEL_SHORT


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


class TestFeatureToModel:
    def test_feature_engineer_to_xgboost(self):
        """FeatureEngineer output feeds into XGBoost model."""
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)

        # Generate training data from features
        rng = np.random.RandomState(42)
        X = np.vstack([
            fe.extract(candles, indicators, MarketContext(regime=r))
            for r in MarketRegime
            for _ in range(30)
        ])
        y = rng.choice([0, 1, 2], size=len(X))

        model = XGBoostSignalModel(n_estimators=10, max_depth=3)
        metrics = model.train(X, y)
        assert model.is_ready
        assert metrics["accuracy"] > 0.0

        # Predict on same features
        preds = model.predict(fe.extract(candles, indicators))
        assert preds[0].label in (LABEL_SHORT, LABEL_NEUTRAL, LABEL_LONG)

    def test_feature_engineer_to_regime(self):
        """FeatureEngineer output feeds into RegimeClassifier."""
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)

        rng = np.random.RandomState(42)
        X = np.vstack([fe.extract(candles, indicators) for _ in range(120)])
        y = rng.choice(range(6), size=120)

        model = RegimeClassifier(n_estimators=10)
        model.train(X, y)
        regime, conf = model.predict_regime(fe.extract(candles, indicators))
        assert isinstance(regime, MarketRegime)


class TestScalerPipeline:
    def test_scaler_with_features(self):
        """FeatureScaler integrates with FeatureEngineer."""
        fe = FeatureEngineer()
        scaler = FeatureScaler(n_features=fe.n_features)

        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)

        # Fit scaler on multiple feature extractions
        for _ in range(10):
            features = fe.extract(candles, indicators)
            scaler.partial_fit(features)

        assert scaler.is_fitted
        scaled = scaler.transform(features)
        assert scaled.shape == (fe.n_features,)
        assert scaled.dtype == np.float32


class TestTrainerPipeline:
    def test_full_training_flow(self, tmp_path):
        """ModelTrainer trains, evaluates, and saves artifacts."""
        model = XGBoostSignalModel(n_estimators=10, max_depth=3)
        trainer = ModelTrainer(model, output_dir=tmp_path, val_split=0.2)

        rng = np.random.RandomState(42)
        X = rng.randn(150, 37).astype(np.float32)
        y = rng.choice([0, 1, 2], size=150)

        result = trainer.train(X, y)
        assert result.model_name == "xgboost_signal"
        assert result.n_train == 120
        assert result.n_val == 30
        assert "accuracy" in result.metrics
        assert result.artifact_dir is not None

        # Verify scaler saved
        assert trainer.scaler is not None
        assert trainer.scaler.is_fitted

    def test_anomaly_training_flow(self):
        """ModelTrainer handles unsupervised anomaly training."""
        model = AnomalyDetector(n_estimators=20)
        trainer = ModelTrainer(model)
        X = np.random.RandomState(42).randn(100, 37).astype(np.float32)
        result = trainer.train_unsupervised(X)
        assert model.is_ready
        assert result.n_val == 0


class TestMLEnhancerPipeline:
    def test_enhancer_full_pipeline(self):
        """Full pipeline: features → models → signal enhancement."""
        # Train models
        rng = np.random.RandomState(42)
        X = rng.randn(150, 37).astype(np.float32)
        y_signal = rng.choice([0, 1, 2], size=150)
        y_regime = rng.choice(range(6), size=150)

        signal_model = XGBoostSignalModel(n_estimators=10, max_depth=3)
        signal_model.train(X, y_signal)

        regime_model = RegimeClassifier(n_estimators=10)
        regime_model.train(X, y_regime)

        anomaly_model = AnomalyDetector(n_estimators=20)
        anomaly_model.train(X)

        scaler = FeatureScaler(n_features=37)
        scaler.partial_fit(X)

        # Create enhancer
        enhancer = MLEnhancer(
            signal_model=signal_model,
            regime_model=regime_model,
            anomaly_model=anomaly_model,
            feature_scaler=scaler,
            ml_weight=0.3,
        )

        assert enhancer.is_ready
        assert enhancer.has_regime_model
        assert enhancer.has_anomaly_model

        # Enhance a signal
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)
        signal = _make_signal(Direction.LONG)

        enhanced = enhancer.enhance_signal(signal, candles, indicators)
        assert enhanced.ml_confidence is not None
        assert 0.0 <= enhanced.ml_confidence <= 1.0

    def test_enhancer_status(self):
        """MLEnhancer.get_status() returns correct information."""
        model = XGBoostSignalModel(n_estimators=10)
        rng = np.random.RandomState(42)
        X = rng.randn(50, 37).astype(np.float32)
        y = rng.choice([0, 1, 2], size=50)
        model.train(X, y)

        enhancer = MLEnhancer(signal_model=model)
        status = enhancer.get_status()
        assert status["is_ready"] is True
        assert status["signal_model"]["state"] == "READY"


class TestPhase1ModelsInML:
    def test_composite_signal_ml_confidence(self):
        """Phase 1 CompositeSignal.ml_confidence populated by ML pipeline."""
        signal = _make_signal()
        assert signal.ml_confidence is None

        updated = signal.model_copy(update={"ml_confidence": 0.85})
        assert updated.ml_confidence == 0.85

    def test_market_context_in_features(self):
        """Phase 1 MarketContext feeds into feature extraction."""
        fe = FeatureEngineer()
        candles = _make_candles(30)
        indicators = _make_indicators(candles[-1].close)

        ctx_up = MarketContext(regime=MarketRegime.TRENDING_UP)
        ctx_down = MarketContext(regime=MarketRegime.TRENDING_DOWN)

        f_up = fe.extract(candles, indicators, ctx_up)
        f_down = fe.extract(candles, indicators, ctx_down)

        # Regime features should differ
        assert not np.array_equal(f_up[-6:], f_down[-6:])


class TestImportsClean:
    def test_ml_package_imports(self):
        """All ML classes importable from app.ml package."""
        from app.ml import (
            ALL_FEATURE_NAMES,
            AnomalyDetector,
            FeatureEngineer,
            FeatureScaler,
            MLEnhancer,
            MLPrediction,
            ModelState,
            ModelTrainer,
            ONNXPredictor,
            RegimeClassifier,
            TrainResult,
            XGBoostSignalModel,
        )
        assert len(ALL_FEATURE_NAMES) == 37
