"""Training pipeline for ML models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.ml.features.engineer import FeatureEngineer
from app.ml.features.scaler import FeatureScaler
from app.ml.models.base import BaseMLModel, ModelState


@dataclass
class TrainResult:
    """Training run result."""
    model_name: str
    metrics: dict[str, float]
    n_train: int
    n_val: int
    duration_secs: float
    artifact_dir: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class ModelTrainer:
    """Orchestrates model training with data splitting and evaluation.

    Handles:
    - Train/validation split
    - Feature scaling (fit on train, apply to val)
    - Model training with early stopping
    - Metric computation
    - Artifact saving (model + scaler + metrics)
    """

    def __init__(
        self,
        model: BaseMLModel,
        feature_engineer: FeatureEngineer | None = None,
        val_split: float = 0.2,
        output_dir: str | Path | None = None,
    ) -> None:
        self._model = model
        self._feature_engineer = feature_engineer or FeatureEngineer()
        self._val_split = val_split
        self._output_dir = Path(output_dir) if output_dir else None
        self._scaler: FeatureScaler | None = None

    @property
    def model(self) -> BaseMLModel:
        return self._model

    @property
    def scaler(self) -> FeatureScaler | None:
        return self._scaler

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        scale_features: bool = True,
        **train_kwargs: Any,
    ) -> TrainResult:
        """Train model with automatic split and scaling.

        Args:
            X: Feature matrix (n_samples, n_features).
            y: Labels (n_samples,).
            scale_features: Whether to apply feature scaling.
            **train_kwargs: Passed to model.train().

        Returns:
            TrainResult with metrics and metadata.
        """
        import time
        start = time.monotonic()

        # Split data
        n = len(X)
        n_val = max(1, int(n * self._val_split))
        n_train = n - n_val

        X_train, X_val = X[:n_train], X[n_train:]
        y_train, y_val = y[:n_train], y[n_train:]

        # Scale features
        if scale_features:
            self._scaler = FeatureScaler(n_features=X.shape[1])
            self._scaler.partial_fit(X_train)
            X_train = self._scaler.transform(X_train)
            X_val = self._scaler.transform(X_val)

        # Train
        metrics = self._model.train(
            X_train, y_train,
            X_val=X_val, y_val=y_val,
            **train_kwargs,
        )

        # Evaluate on validation set
        if self._model.is_ready and len(X_val) > 0:
            preds = self._model.predict(X_val)
            pred_labels = np.array([p.label for p in preds])
            if y_val.dtype in (np.int32, np.int64, np.float64, np.float32):
                val_acc = float(np.mean(pred_labels == y_val.astype(int)))
                metrics["val_accuracy_computed"] = val_acc

        duration = time.monotonic() - start

        # Save artifacts
        artifact_dir = None
        if self._output_dir is not None:
            artifact_dir = str(self._save_artifacts(metrics))

        return TrainResult(
            model_name=self._model.name,
            metrics=metrics,
            n_train=n_train,
            n_val=n_val,
            duration_secs=round(duration, 2),
            artifact_dir=artifact_dir,
        )

    def train_unsupervised(
        self,
        X: np.ndarray,
        scale_features: bool = True,
        **train_kwargs: Any,
    ) -> TrainResult:
        """Train unsupervised model (e.g., anomaly detector).

        Args:
            X: Feature matrix (n_samples, n_features).
            scale_features: Whether to apply feature scaling.
        """
        import time
        start = time.monotonic()

        if scale_features:
            self._scaler = FeatureScaler(n_features=X.shape[1])
            self._scaler.partial_fit(X)
            X_scaled = self._scaler.transform(X)
        else:
            X_scaled = X

        metrics = self._model.train(X_scaled, **train_kwargs)

        duration = time.monotonic() - start

        artifact_dir = None
        if self._output_dir is not None:
            artifact_dir = str(self._save_artifacts(metrics))

        return TrainResult(
            model_name=self._model.name,
            metrics=metrics,
            n_train=len(X),
            n_val=0,
            duration_secs=round(duration, 2),
            artifact_dir=artifact_dir,
        )

    def _save_artifacts(self, metrics: dict[str, float]) -> Path:
        """Save model, scaler, and metrics to output directory."""
        out = self._output_dir / self._model.name
        out.mkdir(parents=True, exist_ok=True)

        self._model.save(out)

        if self._scaler is not None:
            self._scaler.save(out / "scaler.json")

        (out / "train_metrics.json").write_text(
            json.dumps(metrics, indent=2, default=str)
        )

        return out
