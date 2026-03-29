"""Unit tests for Isolation Forest anomaly detector."""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.models.base import ModelState
from app.ml.models.anomaly_model import AnomalyDetector


def _make_normal_data(n: int = 200, n_features: int = 37, seed: int = 42):
    rng = np.random.RandomState(seed)
    return rng.randn(n, n_features).astype(np.float32)


def _make_anomaly(n_features: int = 37):
    """Create an obvious outlier."""
    return np.full(n_features, 10.0, dtype=np.float32)


class TestInit:
    def test_default_state(self):
        model = AnomalyDetector()
        assert model.name == "anomaly_detector"
        assert model.state == ModelState.UNTRAINED

    def test_custom_params(self):
        model = AnomalyDetector(contamination=0.1, n_estimators=50)
        assert model._params["contamination"] == 0.1


class TestTrain:
    def test_train_unsupervised(self):
        model = AnomalyDetector(n_estimators=20)
        X = _make_normal_data(100)
        metrics = model.train(X)
        assert model.is_ready
        assert "n_anomalies" in metrics
        assert "anomaly_rate" in metrics

    def test_y_ignored(self):
        model = AnomalyDetector(n_estimators=20)
        X = _make_normal_data(100)
        y = np.zeros(100)  # Should be ignored
        metrics = model.train(X, y)
        assert model.is_ready

    def test_contamination_rate(self):
        model = AnomalyDetector(n_estimators=50, contamination=0.1)
        X = _make_normal_data(200)
        metrics = model.train(X)
        # Anomaly rate should be approximately contamination
        assert 0.0 <= metrics["anomaly_rate"] <= 0.3


class TestPredict:
    def test_predict_single(self):
        model = AnomalyDetector(n_estimators=20)
        X = _make_normal_data(100)
        model.train(X)
        preds = model.predict(X[0])
        assert len(preds) == 1
        assert preds[0].label in (1, -1)

    def test_predict_batch(self):
        model = AnomalyDetector(n_estimators=20)
        X = _make_normal_data(100)
        model.train(X)
        preds = model.predict(X[:10])
        assert len(preds) == 10

    def test_anomaly_score_range(self):
        model = AnomalyDetector(n_estimators=20)
        X = _make_normal_data(100)
        model.train(X)
        preds = model.predict(X[0])
        assert 0.0 <= preds[0].confidence <= 1.0

    def test_anomaly_metadata(self):
        model = AnomalyDetector(n_estimators=20)
        X = _make_normal_data(100)
        model.train(X)
        preds = model.predict(X[0])
        assert "is_anomaly" in preds[0].metadata
        assert "raw_score" in preds[0].metadata

    def test_obvious_anomaly_detected(self):
        model = AnomalyDetector(n_estimators=50, contamination=0.05)
        X = _make_normal_data(200)
        model.train(X)
        anomaly = _make_anomaly()
        preds = model.predict(anomaly)
        # Extreme outlier should have high anomaly score
        assert preds[0].confidence > 0.4

    def test_is_anomalous_shortcut(self):
        model = AnomalyDetector(n_estimators=50)
        X = _make_normal_data(200)
        model.train(X)
        normal = X[0]
        anomaly = _make_anomaly()
        # Normal point shouldn't be anomalous
        assert not model.is_anomalous(normal, threshold=0.8)
        # Extreme outlier should be anomalous at reasonable threshold
        assert model.is_anomalous(anomaly, threshold=0.5)

    def test_predict_untrained_raises(self):
        model = AnomalyDetector()
        with pytest.raises(RuntimeError):
            model.predict(np.zeros(37))


class TestSaveLoad:
    def test_save_and_load(self, tmp_path):
        model = AnomalyDetector(n_estimators=20)
        X = _make_normal_data(100)
        model.train(X)
        model.save(tmp_path / "model")

        model2 = AnomalyDetector()
        model2.load(tmp_path / "model")
        assert model2.is_ready

    def test_loaded_predictions_match(self, tmp_path):
        model = AnomalyDetector(n_estimators=20)
        X = _make_normal_data(100)
        model.train(X)
        preds1 = model.predict(X[:3])
        model.save(tmp_path / "model")

        model2 = AnomalyDetector()
        model2.load(tmp_path / "model")
        preds2 = model2.predict(X[:3])
        for p1, p2 in zip(preds1, preds2):
            assert p1.label == p2.label

    def test_load_missing(self, tmp_path):
        model = AnomalyDetector()
        model.load(tmp_path / "nonexistent")
        assert model.state == ModelState.FAILED
