"""Unit tests for ML model base classes."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.ml.models.base import BaseMLModel, MLPrediction, ModelState


class DummyModel(BaseMLModel):
    """Concrete model for testing the ABC."""

    def train(self, X, y, **kwargs):
        self.state = ModelState.READY
        self._model = "trained"
        return {"accuracy": 0.85}

    def predict(self, X):
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return [
            MLPrediction(label=1, confidence=0.9)
            for _ in range(X.shape[0])
        ]

    def save(self, directory):
        Path(directory).mkdir(parents=True, exist_ok=True)
        (Path(directory) / "model.txt").write_text("dummy")

    def load(self, directory):
        if (Path(directory) / "model.txt").exists():
            self.state = ModelState.READY
            self._model = "loaded"


class TestModelState:
    def test_initial_untrained(self):
        model = DummyModel(name="test")
        assert model.state == ModelState.UNTRAINED
        assert not model.is_ready

    def test_ready_after_train(self):
        model = DummyModel(name="test")
        model.train(np.zeros((10, 5)), np.zeros(10))
        assert model.state == ModelState.READY
        assert model.is_ready

    def test_all_states_exist(self):
        assert ModelState.UNTRAINED == "UNTRAINED"
        assert ModelState.TRAINING == "TRAINING"
        assert ModelState.READY == "READY"
        assert ModelState.FAILED == "FAILED"


class TestMLPrediction:
    def test_basic_prediction(self):
        pred = MLPrediction(label=1, confidence=0.85)
        assert pred.label == 1
        assert pred.confidence == 0.85
        assert pred.probabilities is None
        assert pred.metadata == {}

    def test_with_probabilities(self):
        probs = np.array([0.15, 0.85])
        pred = MLPrediction(label=1, confidence=0.85, probabilities=probs)
        np.testing.assert_allclose(pred.probabilities, probs)

    def test_with_metadata(self):
        pred = MLPrediction(label="BUY", confidence=0.7, metadata={"model": "xgb"})
        assert pred.metadata["model"] == "xgb"

    def test_repr(self):
        pred = MLPrediction(label=1, confidence=0.85)
        assert "0.850" in repr(pred)


class TestBaseMLModel:
    def test_name_version(self):
        model = DummyModel(name="test_model", version="2.0")
        assert model.name == "test_model"
        assert model.version == "2.0"

    def test_default_version(self):
        model = DummyModel(name="test")
        assert model.version == "1.0"

    def test_train_returns_metrics(self):
        model = DummyModel(name="test")
        metrics = model.train(np.zeros((10, 5)), np.zeros(10))
        assert "accuracy" in metrics
        assert metrics["accuracy"] == 0.85

    def test_predict_single(self):
        model = DummyModel(name="test")
        model.train(np.zeros((10, 5)), np.zeros(10))
        preds = model.predict(np.zeros(5))
        assert len(preds) == 1
        assert preds[0].label == 1

    def test_predict_batch(self):
        model = DummyModel(name="test")
        model.train(np.zeros((10, 5)), np.zeros(10))
        preds = model.predict(np.zeros((3, 5)))
        assert len(preds) == 3

    def test_save_load(self, tmp_path):
        model = DummyModel(name="test")
        model.train(np.zeros((10, 5)), np.zeros(10))
        model.save(tmp_path / "model")

        model2 = DummyModel(name="test")
        model2.load(tmp_path / "model")
        assert model2.is_ready

    def test_get_info(self):
        model = DummyModel(name="my_model", version="1.5")
        info = model.get_info()
        assert info["name"] == "my_model"
        assert info["version"] == "1.5"
        assert info["state"] == "UNTRAINED"

    def test_abc_enforcement(self):
        with pytest.raises(TypeError):
            BaseMLModel(name="abstract")  # type: ignore[abstract]
