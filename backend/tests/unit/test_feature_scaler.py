"""Unit tests for FeatureScaler - online incremental scaler."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.ml.features.scaler import FeatureScaler


class TestInit:
    def test_initial_state(self):
        scaler = FeatureScaler(n_features=5)
        assert scaler.n_features == 5
        assert scaler.count == 0
        assert not scaler.is_fitted

    def test_initial_mean_zeros(self):
        scaler = FeatureScaler(n_features=3)
        assert np.all(scaler.mean == 0.0)

    def test_initial_std_ones(self):
        """Before fitting, std returns ones (safe default)."""
        scaler = FeatureScaler(n_features=3)
        assert np.allclose(scaler.std, 1.0)


class TestPartialFit:
    def test_single_sample(self):
        scaler = FeatureScaler(n_features=3)
        scaler.partial_fit(np.array([1.0, 2.0, 3.0]))
        assert scaler.count == 1
        np.testing.assert_allclose(scaler.mean, [1.0, 2.0, 3.0])

    def test_multiple_samples_1d(self):
        scaler = FeatureScaler(n_features=2)
        scaler.partial_fit(np.array([2.0, 4.0]))
        scaler.partial_fit(np.array([4.0, 6.0]))
        assert scaler.count == 2
        np.testing.assert_allclose(scaler.mean, [3.0, 5.0])

    def test_batch_2d(self):
        scaler = FeatureScaler(n_features=2)
        data = np.array([[2.0, 4.0], [4.0, 6.0], [6.0, 8.0]])
        scaler.partial_fit(data)
        assert scaler.count == 3
        np.testing.assert_allclose(scaler.mean, [4.0, 6.0])

    def test_std_correct(self):
        scaler = FeatureScaler(n_features=1)
        data = np.array([[10.0], [20.0], [30.0]])
        scaler.partial_fit(data)
        expected_std = np.std([10.0, 20.0, 30.0])
        np.testing.assert_allclose(scaler.std, [expected_std], atol=1e-6)

    def test_is_fitted_after_two_samples(self):
        scaler = FeatureScaler(n_features=2)
        scaler.partial_fit(np.array([1.0, 2.0]))
        assert not scaler.is_fitted
        scaler.partial_fit(np.array([3.0, 4.0]))
        assert scaler.is_fitted


class TestTransform:
    def test_standardizes_1d(self):
        scaler = FeatureScaler(n_features=2)
        scaler.partial_fit(np.array([[0.0, 0.0], [10.0, 20.0]]))
        result = scaler.transform(np.array([5.0, 10.0]))
        # Mean=[5,10], std=[5,10] → (5-5)/5=0, (10-10)/10=0
        np.testing.assert_allclose(result, [0.0, 0.0], atol=1e-5)

    def test_standardizes_2d(self):
        scaler = FeatureScaler(n_features=2)
        scaler.partial_fit(np.array([[0.0, 0.0], [10.0, 20.0]]))
        result = scaler.transform(np.array([[5.0, 10.0], [10.0, 20.0]]))
        assert result.shape == (2, 2)
        np.testing.assert_allclose(result[0], [0.0, 0.0], atol=1e-5)

    def test_clips_extreme(self):
        scaler = FeatureScaler(n_features=1)
        scaler.partial_fit(np.array([[0.0], [1.0]]))
        result = scaler.transform(np.array([100.0]))
        assert result[0] <= 5.0

    def test_output_dtype_float32(self):
        scaler = FeatureScaler(n_features=2)
        scaler.partial_fit(np.array([[0.0, 0.0], [10.0, 20.0]]))
        result = scaler.transform(np.array([5.0, 10.0]))
        assert result.dtype == np.float32


class TestInverseTransform:
    def test_roundtrip(self):
        scaler = FeatureScaler(n_features=3)
        data = np.random.RandomState(42).randn(100, 3)
        scaler.partial_fit(data)
        original = np.array([1.5, -0.5, 2.0], dtype=np.float32)
        scaled = scaler.transform(original)
        recovered = scaler.inverse_transform(scaled)
        np.testing.assert_allclose(recovered, original, atol=1e-4)


class TestSaveLoad:
    def test_save_and_load(self, tmp_path):
        scaler = FeatureScaler(n_features=3)
        data = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
        scaler.partial_fit(data)

        path = tmp_path / "scaler.json"
        scaler.save(path)

        loaded = FeatureScaler.load(path)
        assert loaded.n_features == 3
        assert loaded.count == 3
        np.testing.assert_allclose(loaded.mean, scaler.mean)
        np.testing.assert_allclose(loaded.std, scaler.std)

    def test_save_creates_json(self, tmp_path):
        scaler = FeatureScaler(n_features=2)
        scaler.partial_fit(np.array([1.0, 2.0]))
        path = tmp_path / "scaler.json"
        scaler.save(path)
        state = json.loads(path.read_text())
        assert "n_features" in state
        assert "mean" in state

    def test_loaded_transform_matches(self, tmp_path):
        scaler = FeatureScaler(n_features=2)
        data = np.array([[0.0, 0.0], [10.0, 20.0]])
        scaler.partial_fit(data)
        path = tmp_path / "scaler.json"
        scaler.save(path)

        loaded = FeatureScaler.load(path)
        sample = np.array([5.0, 10.0])
        np.testing.assert_allclose(
            scaler.transform(sample),
            loaded.transform(sample),
        )
