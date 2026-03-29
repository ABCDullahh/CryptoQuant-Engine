"""Unit tests for XGBoost signal classifier."""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.models.base import ModelState
from app.ml.models.xgboost_model import (
    LABEL_LONG,
    LABEL_NEUTRAL,
    LABEL_SHORT,
    XGBoostSignalModel,
)


def _make_data(n: int = 200, n_features: int = 37, seed: int = 42):
    """Generate synthetic training data."""
    rng = np.random.RandomState(seed)
    X = rng.randn(n, n_features).astype(np.float32)
    # Labels based on first feature for determinism
    y = np.where(X[:, 0] > 0.5, LABEL_LONG,
                 np.where(X[:, 0] < -0.5, LABEL_SHORT, LABEL_NEUTRAL))
    return X, y


class TestInit:
    def test_default_params(self):
        model = XGBoostSignalModel()
        assert model.name == "xgboost_signal"
        assert model.state == ModelState.UNTRAINED
        assert not model.is_ready

    def test_custom_params(self):
        model = XGBoostSignalModel(n_estimators=100, max_depth=4)
        assert model._params["n_estimators"] == 100
        assert model._params["max_depth"] == 4


class TestTrain:
    def test_train_basic(self):
        model = XGBoostSignalModel(n_estimators=10, max_depth=3)
        X, y = _make_data(100)
        metrics = model.train(X, y)
        assert model.is_ready
        assert "accuracy" in metrics
        assert metrics["accuracy"] > 0.3  # Better than random

    def test_train_with_validation(self):
        model = XGBoostSignalModel(n_estimators=20, max_depth=3)
        X, y = _make_data(200)
        X_val, y_val = _make_data(50, seed=99)
        metrics = model.train(X, y, X_val=X_val, y_val=y_val)
        assert "val_accuracy" in metrics

    def test_feature_importance_set(self):
        model = XGBoostSignalModel(n_estimators=10)
        X, y = _make_data(100)
        model.train(X, y)
        assert model.feature_importance is not None
        assert len(model.feature_importance) == 37

    def test_n_samples_in_metrics(self):
        model = XGBoostSignalModel(n_estimators=10)
        X, y = _make_data(80)
        metrics = model.train(X, y)
        assert metrics["n_samples"] == 80


class TestPredict:
    def test_predict_single(self):
        model = XGBoostSignalModel(n_estimators=10)
        X, y = _make_data(100)
        model.train(X, y)
        preds = model.predict(X[0])
        assert len(preds) == 1
        assert preds[0].label in (LABEL_SHORT, LABEL_NEUTRAL, LABEL_LONG)
        assert 0.0 <= preds[0].confidence <= 1.0

    def test_predict_batch(self):
        model = XGBoostSignalModel(n_estimators=10)
        X, y = _make_data(100)
        model.train(X, y)
        preds = model.predict(X[:5])
        assert len(preds) == 5

    def test_probabilities_sum_to_one(self):
        model = XGBoostSignalModel(n_estimators=10)
        X, y = _make_data(100)
        model.train(X, y)
        preds = model.predict(X[0])
        np.testing.assert_allclose(preds[0].probabilities.sum(), 1.0, atol=1e-5)

    def test_label_name_metadata(self):
        model = XGBoostSignalModel(n_estimators=10)
        X, y = _make_data(100)
        model.train(X, y)
        preds = model.predict(X[0])
        assert preds[0].metadata["label_name"] in ("SHORT", "NEUTRAL", "LONG")

    def test_predict_untrained_raises(self):
        model = XGBoostSignalModel()
        with pytest.raises(RuntimeError):
            model.predict(np.zeros(37))

    def test_direction_confidence_shortcut(self):
        model = XGBoostSignalModel(n_estimators=10)
        X, y = _make_data(100)
        model.train(X, y)
        label, conf = model.predict_direction_confidence(X[0])
        assert label in (0, 1, 2)
        assert 0.0 <= conf <= 1.0


class TestSaveLoad:
    def test_save_and_load(self, tmp_path):
        model = XGBoostSignalModel(n_estimators=10)
        X, y = _make_data(100)
        model.train(X, y)
        model.save(tmp_path / "model")

        model2 = XGBoostSignalModel()
        model2.load(tmp_path / "model")
        assert model2.is_ready

    def test_loaded_predictions_match(self, tmp_path):
        model = XGBoostSignalModel(n_estimators=10)
        X, y = _make_data(100)
        model.train(X, y)
        preds1 = model.predict(X[:5])
        model.save(tmp_path / "model")

        model2 = XGBoostSignalModel()
        model2.load(tmp_path / "model")
        preds2 = model2.predict(X[:5])

        for p1, p2 in zip(preds1, preds2):
            assert p1.label == p2.label
            np.testing.assert_allclose(p1.confidence, p2.confidence, atol=1e-5)

    def test_load_missing_model(self, tmp_path):
        model = XGBoostSignalModel()
        model.load(tmp_path / "nonexistent")
        assert model.state == ModelState.FAILED

    def test_feature_importance_persisted(self, tmp_path):
        model = XGBoostSignalModel(n_estimators=10)
        X, y = _make_data(100)
        model.train(X, y)
        model.save(tmp_path / "model")

        model2 = XGBoostSignalModel()
        model2.load(tmp_path / "model")
        # Feature importance is stored in meta.json
        assert model2.feature_importance is not None
