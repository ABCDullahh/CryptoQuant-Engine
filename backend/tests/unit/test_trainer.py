"""Unit tests for ModelTrainer - training pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.ml.models.base import ModelState
from app.ml.models.xgboost_model import XGBoostSignalModel
from app.ml.models.anomaly_model import AnomalyDetector
from app.ml.training.trainer import ModelTrainer, TrainResult


def _make_data(n: int = 200, n_features: int = 37, seed: int = 42):
    rng = np.random.RandomState(seed)
    X = rng.randn(n, n_features).astype(np.float32)
    y = np.where(X[:, 0] > 0.5, 2, np.where(X[:, 0] < -0.5, 0, 1)).astype(np.int64)
    return X, y


class TestTrainSupervised:
    def test_basic_train(self):
        model = XGBoostSignalModel(n_estimators=10, max_depth=3)
        trainer = ModelTrainer(model, val_split=0.2)
        X, y = _make_data(100)
        result = trainer.train(X, y)
        assert isinstance(result, TrainResult)
        assert result.model_name == "xgboost_signal"
        assert result.n_train == 80
        assert result.n_val == 20
        assert model.is_ready

    def test_metrics_populated(self):
        model = XGBoostSignalModel(n_estimators=10)
        trainer = ModelTrainer(model, val_split=0.2)
        X, y = _make_data(100)
        result = trainer.train(X, y)
        assert "accuracy" in result.metrics
        assert "val_accuracy_computed" in result.metrics
        assert result.duration_secs >= 0

    def test_scaler_fitted(self):
        model = XGBoostSignalModel(n_estimators=10)
        trainer = ModelTrainer(model, val_split=0.2)
        X, y = _make_data(100)
        trainer.train(X, y, scale_features=True)
        assert trainer.scaler is not None
        assert trainer.scaler.is_fitted

    def test_no_scaling(self):
        model = XGBoostSignalModel(n_estimators=10)
        trainer = ModelTrainer(model, val_split=0.2)
        X, y = _make_data(100)
        trainer.train(X, y, scale_features=False)
        assert trainer.scaler is None

    def test_val_split_ratio(self):
        model = XGBoostSignalModel(n_estimators=10)
        trainer = ModelTrainer(model, val_split=0.3)
        X, y = _make_data(100)
        result = trainer.train(X, y)
        assert result.n_val == 30
        assert result.n_train == 70


class TestTrainUnsupervised:
    def test_anomaly_training(self):
        model = AnomalyDetector(n_estimators=20)
        trainer = ModelTrainer(model, val_split=0.2)
        X = np.random.RandomState(42).randn(100, 37).astype(np.float32)
        result = trainer.train_unsupervised(X)
        assert result.model_name == "anomaly_detector"
        assert result.n_train == 100
        assert result.n_val == 0
        assert model.is_ready

    def test_anomaly_metrics(self):
        model = AnomalyDetector(n_estimators=20)
        trainer = ModelTrainer(model)
        X = np.random.RandomState(42).randn(100, 37).astype(np.float32)
        result = trainer.train_unsupervised(X)
        assert "n_anomalies" in result.metrics


class TestSaveArtifacts:
    def test_saves_model_and_scaler(self, tmp_path):
        model = XGBoostSignalModel(n_estimators=10)
        trainer = ModelTrainer(model, output_dir=tmp_path)
        X, y = _make_data(100)
        result = trainer.train(X, y)
        assert result.artifact_dir is not None
        artifact_path = Path(result.artifact_dir)
        assert (artifact_path / "scaler.json").exists()
        assert (artifact_path / "train_metrics.json").exists()

    def test_metrics_json_valid(self, tmp_path):
        model = XGBoostSignalModel(n_estimators=10)
        trainer = ModelTrainer(model, output_dir=tmp_path)
        X, y = _make_data(100)
        result = trainer.train(X, y)
        metrics_path = Path(result.artifact_dir) / "train_metrics.json"
        metrics = json.loads(metrics_path.read_text())
        assert "accuracy" in metrics

    def test_no_save_without_output_dir(self):
        model = XGBoostSignalModel(n_estimators=10)
        trainer = ModelTrainer(model)
        X, y = _make_data(100)
        result = trainer.train(X, y)
        assert result.artifact_dir is None


class TestTrainResult:
    def test_timestamp_populated(self):
        model = XGBoostSignalModel(n_estimators=10)
        trainer = ModelTrainer(model)
        X, y = _make_data(50)
        result = trainer.train(X, y)
        assert result.timestamp is not None
        assert "T" in result.timestamp  # ISO format
