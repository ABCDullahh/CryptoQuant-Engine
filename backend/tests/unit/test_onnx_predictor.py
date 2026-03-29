"""Unit tests for ONNX predictor and model export."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.ml.models.base import MLPrediction
from app.ml.serving.predictor import ONNXPredictor


def _create_sklearn_onnx(tmp_path: Path, n_features: int = 10) -> Path:
    """Create a simple sklearn model and export to ONNX."""
    from sklearn.ensemble import RandomForestClassifier
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    rng = np.random.RandomState(42)
    X = rng.randn(100, n_features).astype(np.float32)
    y = (X[:, 0] > 0).astype(int)

    clf = RandomForestClassifier(n_estimators=10, random_state=42)
    clf.fit(X, y)

    initial_type = [("features", FloatTensorType([None, n_features]))]
    onnx_model = convert_sklearn(clf, initial_types=initial_type)

    onnx_path = tmp_path / "model.onnx"
    with open(onnx_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    meta = {"name": "test_model", "label_map": {"0": "NO", "1": "YES"}}
    (tmp_path / "meta.json").write_text(json.dumps(meta))

    return onnx_path


class TestInit:
    def test_initial_state(self):
        pred = ONNXPredictor()
        assert not pred.is_loaded
        assert pred.model_name == ""

    def test_get_info_unloaded(self):
        pred = ONNXPredictor()
        info = pred.get_info()
        assert info["loaded"] is False


class TestLoad:
    def test_load_valid_model(self, tmp_path):
        onnx_path = _create_sklearn_onnx(tmp_path)
        pred = ONNXPredictor()
        pred.load(onnx_path, meta_path=tmp_path / "meta.json")
        assert pred.is_loaded
        assert pred.model_name == "test_model"

    def test_load_missing_raises(self, tmp_path):
        pred = ONNXPredictor()
        with pytest.raises(FileNotFoundError):
            pred.load(tmp_path / "nonexistent.onnx")

    def test_load_without_meta(self, tmp_path):
        onnx_path = _create_sklearn_onnx(tmp_path)
        pred = ONNXPredictor()
        pred.load(onnx_path)
        assert pred.is_loaded

    def test_get_info_loaded(self, tmp_path):
        onnx_path = _create_sklearn_onnx(tmp_path)
        pred = ONNXPredictor()
        pred.load(onnx_path, meta_path=tmp_path / "meta.json")
        info = pred.get_info()
        assert info["loaded"] is True
        assert "input_name" in info


class TestPredict:
    def test_predict_single(self, tmp_path):
        onnx_path = _create_sklearn_onnx(tmp_path)
        pred = ONNXPredictor()
        pred.load(onnx_path, meta_path=tmp_path / "meta.json")
        result = pred.predict(np.zeros(10, dtype=np.float32))
        assert len(result) == 1
        assert isinstance(result[0], MLPrediction)

    def test_predict_batch(self, tmp_path):
        onnx_path = _create_sklearn_onnx(tmp_path)
        pred = ONNXPredictor()
        pred.load(onnx_path)
        X = np.zeros((5, 10), dtype=np.float32)
        result = pred.predict(X)
        assert len(result) == 5

    def test_confidence_range(self, tmp_path):
        onnx_path = _create_sklearn_onnx(tmp_path)
        pred = ONNXPredictor()
        pred.load(onnx_path)
        result = pred.predict(np.zeros(10, dtype=np.float32))
        assert 0.0 <= result[0].confidence <= 1.0

    def test_probabilities_available(self, tmp_path):
        onnx_path = _create_sklearn_onnx(tmp_path)
        pred = ONNXPredictor()
        pred.load(onnx_path)
        result = pred.predict(np.zeros(10, dtype=np.float32))
        assert result[0].probabilities is not None
        np.testing.assert_allclose(result[0].probabilities.sum(), 1.0, atol=1e-5)

    def test_label_map_in_metadata(self, tmp_path):
        onnx_path = _create_sklearn_onnx(tmp_path)
        pred = ONNXPredictor()
        pred.load(onnx_path, meta_path=tmp_path / "meta.json")
        result = pred.predict(np.zeros(10, dtype=np.float32))
        assert result[0].metadata["label_name"] in ("NO", "YES")

    def test_predict_not_loaded_raises(self):
        pred = ONNXPredictor()
        with pytest.raises(RuntimeError):
            pred.predict(np.zeros(10))

    def test_predict_proba(self, tmp_path):
        onnx_path = _create_sklearn_onnx(tmp_path)
        pred = ONNXPredictor()
        pred.load(onnx_path)
        proba = pred.predict_proba(np.zeros((3, 10), dtype=np.float32))
        assert proba.shape == (3, 2)


class TestExporter:
    def test_export_sklearn(self, tmp_path):
        from sklearn.ensemble import RandomForestClassifier
        from app.ml.serving.exporter import export_sklearn_to_onnx

        rng = np.random.RandomState(42)
        X = rng.randn(50, 5).astype(np.float32)
        y = (X[:, 0] > 0).astype(int)
        clf = RandomForestClassifier(n_estimators=5, random_state=42)
        clf.fit(X, y)

        onnx_path = export_sklearn_to_onnx(
            clf, n_features=5, output_path=tmp_path / "exported",
            model_name="rf_test", label_map={0: "NO", 1: "YES"},
        )
        assert onnx_path.exists()
        assert (tmp_path / "exported" / "meta.json").exists()

        # Verify it loads in predictor
        pred = ONNXPredictor()
        pred.load(onnx_path)
        result = pred.predict(X[0])
        assert len(result) == 1

    def test_export_xgboost(self, tmp_path):
        from app.ml.serving.exporter import export_xgboost_to_onnx
        import xgboost as xgb

        rng = np.random.RandomState(42)
        X = rng.randn(50, 5).astype(np.float32)
        y = (X[:, 0] > 0).astype(int)
        clf = xgb.XGBClassifier(n_estimators=5, verbosity=0)
        clf.fit(X, y)

        onnx_path = export_xgboost_to_onnx(
            clf, n_features=5, output_path=tmp_path / "xgb_exported",
            model_name="xgb_test",
        )
        assert onnx_path.exists()

        # Verify it loads in predictor
        pred = ONNXPredictor()
        pred.load(onnx_path)
        result = pred.predict(X[0])
        assert len(result) == 1
