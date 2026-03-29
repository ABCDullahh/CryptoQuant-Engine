"""Base class for all ML models in the pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np


class ModelState(StrEnum):
    """ML model lifecycle states."""
    UNTRAINED = "UNTRAINED"
    TRAINING = "TRAINING"
    READY = "READY"
    FAILED = "FAILED"


class MLPrediction:
    """Container for ML model prediction output."""

    __slots__ = ("label", "confidence", "probabilities", "metadata")

    def __init__(
        self,
        label: int | str,
        confidence: float,
        probabilities: np.ndarray | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.label = label
        self.confidence = confidence
        self.probabilities = probabilities
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"MLPrediction(label={self.label}, confidence={self.confidence:.3f})"


class BaseMLModel(ABC):
    """Abstract base for all ML models.

    Subclasses must implement train, predict, save, and load.
    """

    def __init__(self, name: str, version: str = "1.0") -> None:
        self.name = name
        self.version = version
        self.state = ModelState.UNTRAINED
        self._model: Any = None

    @property
    def is_ready(self) -> bool:
        return self.state == ModelState.READY

    @abstractmethod
    def train(self, X: np.ndarray, y: np.ndarray, **kwargs: Any) -> dict[str, float]:
        """Train the model.

        Args:
            X: Feature matrix (n_samples, n_features).
            y: Labels (n_samples,).

        Returns:
            Dict of training metrics.
        """

    @abstractmethod
    def predict(self, X: np.ndarray) -> list[MLPrediction]:
        """Make predictions.

        Args:
            X: Feature matrix (n_samples, n_features) or (n_features,).

        Returns:
            List of MLPrediction objects.
        """

    @abstractmethod
    def save(self, directory: str | Path) -> None:
        """Save model artifacts to directory."""

    @abstractmethod
    def load(self, directory: str | Path) -> None:
        """Load model artifacts from directory."""

    def get_info(self) -> dict[str, Any]:
        """Return model metadata."""
        return {
            "name": self.name,
            "version": self.version,
            "state": self.state.value,
        }
