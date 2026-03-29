"""Export ML models to ONNX format."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def export_xgboost_to_onnx(
    model,
    n_features: int,
    output_path: str | Path,
    model_name: str = "xgb_signal",
    label_map: dict[int, str] | None = None,
) -> Path:
    """Export trained XGBoost model to ONNX format.

    Args:
        model: Trained XGBClassifier instance.
        n_features: Number of input features.
        output_path: Directory to save ONNX model.
        model_name: Name for the model file.
        label_map: Optional label name mapping.

    Returns:
        Path to saved ONNX model file.
    """
    from onnxmltools import convert_xgboost
    from onnxmltools.convert.common.data_types import FloatTensorType

    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    initial_type = [("features", FloatTensorType([None, n_features]))]
    onnx_model = convert_xgboost(model, initial_types=initial_type)

    onnx_path = output_path / f"{model_name}.onnx"
    with open(onnx_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    # Save metadata
    meta = {"name": model_name, "n_features": n_features}
    if label_map:
        meta["label_map"] = {str(k): v for k, v in label_map.items()}
    (output_path / "meta.json").write_text(json.dumps(meta, indent=2))

    return onnx_path


def export_sklearn_to_onnx(
    model,
    n_features: int,
    output_path: str | Path,
    model_name: str = "sklearn_model",
    label_map: dict[int, str] | None = None,
) -> Path:
    """Export trained sklearn model to ONNX format.

    Args:
        model: Trained sklearn classifier instance.
        n_features: Number of input features.
        output_path: Directory to save ONNX model.
        model_name: Name for the model file.
        label_map: Optional label name mapping.

    Returns:
        Path to saved ONNX model file.
    """
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    initial_type = [("features", FloatTensorType([None, n_features]))]
    onnx_model = convert_sklearn(model, initial_types=initial_type)

    onnx_path = output_path / f"{model_name}.onnx"
    with open(onnx_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    meta = {"name": model_name, "n_features": n_features}
    if label_map:
        meta["label_map"] = {str(k): v for k, v in label_map.items()}
    (output_path / "meta.json").write_text(json.dumps(meta, indent=2))

    return onnx_path
