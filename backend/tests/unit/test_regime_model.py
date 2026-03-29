"""Unit tests for Random Forest regime classifier."""

from __future__ import annotations

import numpy as np
import pytest

from app.config.constants import MarketRegime
from app.ml.models.base import ModelState
from app.ml.models.regime_model import (
    REGIME_LABELS,
    REGIME_TO_INT,
    RegimeClassifier,
)


def _make_regime_data(n: int = 300, n_features: int = 37, seed: int = 42):
    """Generate synthetic regime classification data."""
    rng = np.random.RandomState(seed)
    X = rng.randn(n, n_features).astype(np.float32)
    # 6 regimes based on feature clusters
    y = np.zeros(n, dtype=np.int64)
    per = n // 6
    for i in range(6):
        y[i * per:(i + 1) * per] = i
        X[i * per:(i + 1) * per, 0] += i * 2  # Separable by feature 0
    return X, y


class TestInit:
    def test_default_state(self):
        model = RegimeClassifier()
        assert model.name == "regime_classifier"
        assert model.state == ModelState.UNTRAINED

    def test_custom_params(self):
        model = RegimeClassifier(n_estimators=50, max_depth=5)
        assert model._params["n_estimators"] == 50


class TestTrain:
    def test_train_basic(self):
        model = RegimeClassifier(n_estimators=20, max_depth=4)
        X, y = _make_regime_data(120)
        metrics = model.train(X, y)
        assert model.is_ready
        assert metrics["accuracy"] > 0.3

    def test_n_samples_metric(self):
        model = RegimeClassifier(n_estimators=10)
        X, y = _make_regime_data(60)
        metrics = model.train(X, y)
        assert metrics["n_samples"] == 60


class TestPredict:
    def test_predict_single(self):
        model = RegimeClassifier(n_estimators=20)
        X, y = _make_regime_data(120)
        model.train(X, y)
        preds = model.predict(X[0])
        assert len(preds) == 1
        assert preds[0].label in range(6)

    def test_predict_batch(self):
        model = RegimeClassifier(n_estimators=20)
        X, y = _make_regime_data(120)
        model.train(X, y)
        preds = model.predict(X[:10])
        assert len(preds) == 10

    def test_probabilities_sum_to_one(self):
        model = RegimeClassifier(n_estimators=20)
        X, y = _make_regime_data(120)
        model.train(X, y)
        preds = model.predict(X[0])
        np.testing.assert_allclose(preds[0].probabilities.sum(), 1.0, atol=1e-5)

    def test_regime_metadata(self):
        model = RegimeClassifier(n_estimators=20)
        X, y = _make_regime_data(120)
        model.train(X, y)
        preds = model.predict(X[0])
        assert "regime" in preds[0].metadata

    def test_predict_regime_shortcut(self):
        model = RegimeClassifier(n_estimators=20)
        X, y = _make_regime_data(120)
        model.train(X, y)
        regime, conf = model.predict_regime(X[0])
        assert isinstance(regime, MarketRegime)
        assert 0.0 <= conf <= 1.0

    def test_predict_untrained_raises(self):
        model = RegimeClassifier()
        with pytest.raises(RuntimeError):
            model.predict(np.zeros(37))


class TestSaveLoad:
    def test_save_and_load(self, tmp_path):
        model = RegimeClassifier(n_estimators=10)
        X, y = _make_regime_data(120)
        model.train(X, y)
        model.save(tmp_path / "model")

        model2 = RegimeClassifier()
        model2.load(tmp_path / "model")
        assert model2.is_ready

    def test_loaded_predictions_match(self, tmp_path):
        model = RegimeClassifier(n_estimators=10)
        X, y = _make_regime_data(120)
        model.train(X, y)
        preds1 = model.predict(X[:3])
        model.save(tmp_path / "model")

        model2 = RegimeClassifier()
        model2.load(tmp_path / "model")
        preds2 = model2.predict(X[:3])
        for p1, p2 in zip(preds1, preds2):
            assert p1.label == p2.label

    def test_load_missing(self, tmp_path):
        model = RegimeClassifier()
        model.load(tmp_path / "nonexistent")
        assert model.state == ModelState.FAILED


class TestLabelMapping:
    def test_all_regimes_mapped(self):
        assert len(REGIME_LABELS) == 6
        for regime in MarketRegime:
            assert regime in REGIME_TO_INT

    def test_roundtrip(self):
        for i, regime in REGIME_LABELS.items():
            assert REGIME_TO_INT[regime] == i
