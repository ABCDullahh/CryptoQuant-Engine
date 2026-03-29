"""Random Forest regime classifier - predicts market regime."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from app.config.constants import MarketRegime
from app.ml.models.base import BaseMLModel, MLPrediction, ModelState

# Regime label mapping
REGIME_LABELS = {
    0: MarketRegime.TRENDING_UP,
    1: MarketRegime.TRENDING_DOWN,
    2: MarketRegime.RANGING,
    3: MarketRegime.HIGH_VOLATILITY,
    4: MarketRegime.LOW_VOLATILITY,
    5: MarketRegime.CHOPPY,
}
REGIME_TO_INT = {v: k for k, v in REGIME_LABELS.items()}


class RegimeClassifier(BaseMLModel):
    """Random Forest classifier for market regime detection.

    Predicts one of 6 MarketRegime values with confidence scores.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 8,
        min_samples_leaf: int = 10,
    ) -> None:
        super().__init__(name="regime_classifier", version="1.0")
        self._params = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "min_samples_leaf": min_samples_leaf,
        }

    def train(self, X: np.ndarray, y: np.ndarray, **kwargs: Any) -> dict[str, float]:
        """Train Random Forest classifier.

        Args:
            X: Features (n_samples, n_features).
            y: Regime labels as ints 0-5 (n_samples,).
        """
        from sklearn.ensemble import RandomForestClassifier

        self.state = ModelState.TRAINING

        clf = RandomForestClassifier(
            random_state=42,
            n_jobs=1,
            **self._params,
        )
        clf.fit(X, y)
        self._model = clf
        self.state = ModelState.READY

        train_preds = clf.predict(X)
        accuracy = float(np.mean(train_preds == y))
        return {"accuracy": accuracy, "n_samples": len(y)}

    def predict(self, X: np.ndarray) -> list[MLPrediction]:
        """Predict market regime."""
        if self._model is None:
            raise RuntimeError("Model not trained or loaded")

        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(1, -1)

        proba = self._model.predict_proba(X)
        labels = np.argmax(proba, axis=1)

        predictions = []
        for i in range(len(labels)):
            label = int(labels[i])
            regime = REGIME_LABELS.get(label, MarketRegime.RANGING)
            predictions.append(MLPrediction(
                label=label,
                confidence=float(proba[i, label]),
                probabilities=proba[i].copy(),
                metadata={"regime": regime.value},
            ))
        return predictions

    def predict_regime(self, X: np.ndarray) -> tuple[MarketRegime, float]:
        """Convenience: predict single sample regime and confidence."""
        preds = self.predict(X)
        label = preds[0].label
        return REGIME_LABELS.get(label, MarketRegime.RANGING), preds[0].confidence

    def save(self, directory: str | Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        if self._model is not None:
            with open(directory / "regime_rf.pkl", "wb") as f:
                pickle.dump(self._model, f)
        meta = {
            "name": self.name, "version": self.version,
            "state": self.state.value, "params": self._params,
        }
        (directory / "meta.json").write_text(json.dumps(meta, indent=2))

    def load(self, directory: str | Path) -> None:
        directory = Path(directory)
        pkl_path = directory / "regime_rf.pkl"
        if not pkl_path.exists():
            self.state = ModelState.FAILED
            return
        with open(pkl_path, "rb") as f:
            self._model = pickle.load(f)  # noqa: S301
        self.state = ModelState.READY
