"""XGBoost signal classifier - predicts direction confidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from app.ml.models.base import BaseMLModel, MLPrediction, ModelState

# Class labels: 0=SHORT, 1=NEUTRAL, 2=LONG
LABEL_SHORT = 0
LABEL_NEUTRAL = 1
LABEL_LONG = 2
LABEL_NAMES = {LABEL_SHORT: "SHORT", LABEL_NEUTRAL: "NEUTRAL", LABEL_LONG: "LONG"}


class XGBoostSignalModel(BaseMLModel):
    """XGBoost-based signal classifier.

    Predicts: SHORT (0), NEUTRAL (1), LONG (2) with confidence scores.
    """

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = 6,
        learning_rate: float = 0.05,
        min_child_weight: int = 5,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
    ) -> None:
        super().__init__(name="xgboost_signal", version="1.0")
        self._params = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "min_child_weight": min_child_weight,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
        }
        self._feature_importance: np.ndarray | None = None

    @property
    def feature_importance(self) -> np.ndarray | None:
        return self._feature_importance

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
        **kwargs: Any,
    ) -> dict[str, float]:
        """Train XGBoost classifier.

        Args:
            X: Training features (n_samples, n_features).
            y: Labels (n_samples,) with values in {0, 1, 2}.
            X_val: Validation features (optional).
            y_val: Validation labels (optional).

        Returns:
            Training metrics dict.
        """
        try:
            import xgboost as xgb
        except ImportError as e:
            self.state = ModelState.FAILED
            raise ImportError("xgboost is required: pip install xgboost") from e

        self.state = ModelState.TRAINING

        n_classes = len(np.unique(y))
        clf = xgb.XGBClassifier(
            objective="multi:softprob",
            num_class=max(n_classes, 3),
            eval_metric="mlogloss",
            early_stopping_rounds=20 if X_val is not None else None,
            verbosity=0,
            **self._params,
        )

        fit_kwargs: dict[str, Any] = {}
        if X_val is not None and y_val is not None:
            fit_kwargs["eval_set"] = [(X_val, y_val)]

        clf.fit(X, y, **fit_kwargs)

        self._model = clf
        self._feature_importance = clf.feature_importances_
        self.state = ModelState.READY

        # Compute metrics
        train_preds = clf.predict(X)
        accuracy = float(np.mean(train_preds == y))

        metrics = {"accuracy": accuracy, "n_samples": len(y)}
        if X_val is not None and y_val is not None:
            val_preds = clf.predict(X_val)
            metrics["val_accuracy"] = float(np.mean(val_preds == y_val))

        return metrics

    def predict(self, X: np.ndarray) -> list[MLPrediction]:
        """Predict signal direction with confidence.

        Args:
            X: Features (n_features,) or (n_samples, n_features).

        Returns:
            List of MLPrediction with label, confidence, probabilities.
        """
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
            predictions.append(MLPrediction(
                label=label,
                confidence=float(proba[i, label]),
                probabilities=proba[i].copy(),
                metadata={"label_name": LABEL_NAMES.get(label, str(label))},
            ))

        return predictions

    def predict_direction_confidence(self, X: np.ndarray) -> tuple[int, float]:
        """Convenience: predict single sample direction and confidence.

        Returns:
            (label, confidence) tuple.
        """
        preds = self.predict(X)
        return preds[0].label, preds[0].confidence

    def save(self, directory: str | Path) -> None:
        """Save model to directory."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        if self._model is not None:
            self._model.save_model(str(directory / "xgb_signal.json"))

        meta = {
            "name": self.name,
            "version": self.version,
            "state": self.state.value,
            "params": self._params,
        }
        if self._feature_importance is not None:
            meta["feature_importance"] = self._feature_importance.tolist()

        (directory / "meta.json").write_text(json.dumps(meta, indent=2))

    def load(self, directory: str | Path) -> None:
        """Load model from directory."""
        directory = Path(directory)

        try:
            import xgboost as xgb
        except ImportError as e:
            self.state = ModelState.FAILED
            raise ImportError("xgboost is required") from e

        model_path = directory / "xgb_signal.json"
        if not model_path.exists():
            self.state = ModelState.FAILED
            return

        clf = xgb.XGBClassifier()
        clf.load_model(str(model_path))
        self._model = clf
        self.state = ModelState.READY

        meta_path = directory / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            self._params = meta.get("params", self._params)
            if "feature_importance" in meta:
                self._feature_importance = np.array(meta["feature_importance"])
