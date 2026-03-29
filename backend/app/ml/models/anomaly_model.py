"""Isolation Forest anomaly detector - flags abnormal market conditions."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from app.ml.models.base import BaseMLModel, MLPrediction, ModelState


class AnomalyDetector(BaseMLModel):
    """Isolation Forest for detecting anomalous market conditions.

    Returns anomaly score (higher = more anomalous) and binary label.
    Label: 1 = normal, -1 = anomaly.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        contamination: float = 0.05,
        max_samples: int | str = "auto",
    ) -> None:
        super().__init__(name="anomaly_detector", version="1.0")
        self._params = {
            "n_estimators": n_estimators,
            "contamination": contamination,
            "max_samples": max_samples,
        }

    def train(self, X: np.ndarray, y: np.ndarray | None = None, **kwargs: Any) -> dict[str, float]:
        """Fit Isolation Forest (unsupervised - y is ignored).

        Args:
            X: Features (n_samples, n_features).
            y: Ignored (kept for interface compatibility).
        """
        from sklearn.ensemble import IsolationForest

        self.state = ModelState.TRAINING

        clf = IsolationForest(
            random_state=42,
            n_jobs=1,
            **self._params,
        )
        clf.fit(X)
        self._model = clf
        self.state = ModelState.READY

        labels = clf.predict(X)
        n_anomalies = int(np.sum(labels == -1))
        return {
            "n_samples": len(X),
            "n_anomalies": n_anomalies,
            "anomaly_rate": n_anomalies / len(X),
        }

    def predict(self, X: np.ndarray) -> list[MLPrediction]:
        """Predict anomaly status.

        Returns MLPrediction with:
          - label: 1 (normal) or -1 (anomaly)
          - confidence: anomaly score (0-1, higher = more anomalous)
        """
        if self._model is None:
            raise RuntimeError("Model not trained or loaded")

        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(1, -1)

        labels = self._model.predict(X)
        scores = self._model.decision_function(X)
        # Convert decision function to 0-1 anomaly score
        # Lower decision_function = more anomalous
        # Normalize: clip to [-1, 1] then invert and scale to [0, 1]
        norm_scores = np.clip(scores, -1.0, 1.0)
        anomaly_scores = (1.0 - norm_scores) / 2.0

        predictions = []
        for i in range(len(labels)):
            predictions.append(MLPrediction(
                label=int(labels[i]),
                confidence=float(anomaly_scores[i]),
                metadata={
                    "is_anomaly": bool(labels[i] == -1),
                    "raw_score": float(scores[i]),
                },
            ))
        return predictions

    def is_anomalous(self, X: np.ndarray, threshold: float = 0.7) -> bool:
        """Convenience: check if single sample is anomalous."""
        preds = self.predict(X)
        return preds[0].confidence >= threshold

    def save(self, directory: str | Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        if self._model is not None:
            with open(directory / "anomaly_iforest.pkl", "wb") as f:
                pickle.dump(self._model, f)
        meta = {
            "name": self.name, "version": self.version,
            "state": self.state.value, "params": self._params,
        }
        (directory / "meta.json").write_text(json.dumps(meta, indent=2))

    def load(self, directory: str | Path) -> None:
        directory = Path(directory)
        pkl_path = directory / "anomaly_iforest.pkl"
        if not pkl_path.exists():
            self.state = ModelState.FAILED
            return
        with open(pkl_path, "rb") as f:
            self._model = pickle.load(f)  # noqa: S301
        self.state = ModelState.READY
