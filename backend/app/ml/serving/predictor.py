"""ONNX Runtime predictor for fast inference."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from app.ml.models.base import MLPrediction


class ONNXPredictor:
    """Fast inference via ONNX Runtime.

    Wraps an ONNX model for low-latency prediction.
    Supports classification models with softmax/probability output.
    """

    def __init__(self) -> None:
        self._session: Any = None
        self._input_name: str = ""
        self._output_names: list[str] = []
        self._label_map: dict[int, str] = {}
        self._model_name: str = ""
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_name(self) -> str:
        return self._model_name

    def load(self, model_path: str | Path, meta_path: str | Path | None = None) -> None:
        """Load ONNX model for inference.

        Args:
            model_path: Path to .onnx model file.
            meta_path: Optional path to meta.json with label mappings.
        """
        import onnxruntime as ort

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"ONNX model not found: {model_path}")

        self._session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )

        self._input_name = self._session.get_inputs()[0].name
        self._output_names = [o.name for o in self._session.get_outputs()]
        self._model_name = model_path.stem

        if meta_path is not None:
            meta_path = Path(meta_path)
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                raw_map = meta.get("label_map", {})
                self._label_map = {int(k): v for k, v in raw_map.items()}
                self._model_name = meta.get("name", self._model_name)

        self._loaded = True

    def predict(self, X: np.ndarray) -> list[MLPrediction]:
        """Run ONNX inference.

        Args:
            X: Features (n_features,) or (n_samples, n_features).

        Returns:
            List of MLPrediction objects.
        """
        if not self._loaded:
            raise RuntimeError("ONNX model not loaded")

        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(1, -1)

        X = X.astype(np.float32)
        outputs = self._session.run(
            self._output_names,
            {self._input_name: X},
        )

        # Handle different output formats
        # Format 1: [labels, probabilities] (sklearn-style)
        # Format 2: [probabilities] (raw model)
        if len(outputs) == 2:
            labels = outputs[0]
            proba = outputs[1]
            # sklearn ONNX returns list of dicts for probabilities
            if isinstance(proba, list) and isinstance(proba[0], dict):
                proba = np.array([
                    [d.get(k, 0.0) for k in sorted(d.keys())]
                    for d in proba
                ])
            elif isinstance(proba, np.ndarray) and proba.ndim == 2:
                pass
            else:
                proba = np.array(proba)
        elif len(outputs) == 1:
            proba = outputs[0] if isinstance(outputs[0], np.ndarray) else np.array(outputs[0])
            if proba.ndim == 2:
                labels = np.argmax(proba, axis=1)
            else:
                labels = proba
                proba = None
        else:
            labels = outputs[0]
            proba = None

        predictions = []
        n = len(labels) if hasattr(labels, '__len__') else 1
        for i in range(n):
            label = int(labels[i]) if hasattr(labels, '__getitem__') else int(labels)
            conf = float(proba[i, label]) if proba is not None and proba.ndim == 2 else 1.0
            prob_arr = proba[i].copy() if proba is not None and proba.ndim == 2 else None
            predictions.append(MLPrediction(
                label=label,
                confidence=conf,
                probabilities=prob_arr,
                metadata={"label_name": self._label_map.get(label, str(label))},
            ))

        return predictions

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return raw probability array."""
        preds = self.predict(X)
        if preds[0].probabilities is not None:
            return np.vstack([p.probabilities for p in preds])
        raise RuntimeError("Model does not output probabilities")

    def get_info(self) -> dict[str, Any]:
        """Return model metadata."""
        if not self._loaded:
            return {"loaded": False}
        return {
            "loaded": True,
            "model_name": self._model_name,
            "input_name": self._input_name,
            "output_names": self._output_names,
            "n_labels": len(self._label_map),
        }
