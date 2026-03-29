"""Feature scaling for ML models - online incremental scaler."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class FeatureScaler:
    """Online feature scaler using running mean/variance (Welford's algorithm).

    Supports incremental updates without storing all data points.
    Serializes to JSON for persistence.
    """

    def __init__(self, n_features: int) -> None:
        self._n_features = n_features
        self._count = 0
        self._mean = np.zeros(n_features, dtype=np.float64)
        self._m2 = np.zeros(n_features, dtype=np.float64)
        self._min = np.full(n_features, np.inf, dtype=np.float64)
        self._max = np.full(n_features, -np.inf, dtype=np.float64)

    @property
    def n_features(self) -> int:
        return self._n_features

    @property
    def count(self) -> int:
        return self._count

    @property
    def mean(self) -> np.ndarray:
        return self._mean.copy()

    @property
    def std(self) -> np.ndarray:
        if self._count < 2:
            return np.ones(self._n_features, dtype=np.float64)
        variance = self._m2 / self._count
        return np.sqrt(np.maximum(variance, 1e-10))

    @property
    def is_fitted(self) -> bool:
        return self._count >= 2

    def partial_fit(self, X: np.ndarray) -> None:
        """Update running statistics with new samples.

        Args:
            X: Array of shape (n_features,) or (n_samples, n_features).
        """
        if X.ndim == 1:
            X = X.reshape(1, -1)

        for row in X:
            self._count += 1
            delta = row - self._mean
            self._mean += delta / self._count
            delta2 = row - self._mean
            self._m2 += delta * delta2
            self._min = np.minimum(self._min, row)
            self._max = np.maximum(self._max, row)

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Standardize features using running mean and std.

        Args:
            X: Array of shape (n_features,) or (n_samples, n_features).

        Returns:
            Scaled array of same shape, dtype float32.
        """
        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(1, -1)

        std = self.std
        result = ((X - self._mean) / std).astype(np.float32)

        # Clip extreme values
        result = np.clip(result, -5.0, 5.0)

        if squeeze:
            return result.squeeze(0)
        return result

    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        """Reverse standardization."""
        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(1, -1)

        std = self.std
        result = (X * std + self._mean).astype(np.float32)

        if squeeze:
            return result.squeeze(0)
        return result

    def save(self, path: str | Path) -> None:
        """Save scaler state to JSON file."""
        state = {
            "n_features": self._n_features,
            "count": self._count,
            "mean": self._mean.tolist(),
            "m2": self._m2.tolist(),
            "min": self._min.tolist(),
            "max": self._max.tolist(),
        }
        Path(path).write_text(json.dumps(state, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> FeatureScaler:
        """Load scaler state from JSON file."""
        state = json.loads(Path(path).read_text())
        scaler = cls(n_features=state["n_features"])
        scaler._count = state["count"]
        scaler._mean = np.array(state["mean"], dtype=np.float64)
        scaler._m2 = np.array(state["m2"], dtype=np.float64)
        scaler._min = np.array(state["min"], dtype=np.float64)
        scaler._max = np.array(state["max"], dtype=np.float64)
        return scaler
