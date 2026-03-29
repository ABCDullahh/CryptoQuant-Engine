"""Unit tests for volume indicators: VWAP, OBV, MFI, Volume SMA."""

from __future__ import annotations

import numpy as np
import pytest

from app.indicators.volume import calc_mfi, calc_obv, calc_volume_sma, calc_vwap


# ---------------------------------------------------------------------------
# VWAP Tests
# ---------------------------------------------------------------------------


class TestVWAP:
    def test_vwap_basic(self):
        h = np.array([102.0, 104.0, 106.0])
        l = np.array([98.0, 96.0, 94.0])
        c = np.array([100.0, 100.0, 100.0])
        v = np.array([1000.0, 1000.0, 1000.0])
        result = calc_vwap(h, l, c, v)
        assert len(result) == 3
        assert not np.isnan(result[0])

    def test_vwap_equal_volume_is_avg_typical_price(self):
        h = np.array([103.0, 106.0])
        l = np.array([97.0, 94.0])
        c = np.array([100.0, 100.0])
        v = np.array([100.0, 100.0])
        result = calc_vwap(h, l, c, v)
        tp1 = (103 + 97 + 100) / 3
        tp2 = (106 + 94 + 100) / 3
        expected = (tp1 * 100 + tp2 * 100) / 200
        assert result[1] == pytest.approx(expected)

    def test_vwap_empty_input(self):
        result = calc_vwap(
            np.array([]), np.array([]), np.array([]), np.array([])
        )
        assert len(result) == 0

    def test_vwap_single_bar(self):
        h = np.array([105.0])
        l = np.array([95.0])
        c = np.array([100.0])
        v = np.array([500.0])
        result = calc_vwap(h, l, c, v)
        tp = (105 + 95 + 100) / 3
        assert result[0] == pytest.approx(tp)

    def test_vwap_zero_volume_is_nan(self):
        h = np.array([100.0])
        l = np.array([90.0])
        c = np.array([95.0])
        v = np.array([0.0])
        result = calc_vwap(h, l, c, v)
        assert np.isnan(result[0])


# ---------------------------------------------------------------------------
# OBV Tests
# ---------------------------------------------------------------------------


class TestOBV:
    def test_obv_all_up(self):
        closes = np.array([100.0, 101.0, 102.0, 103.0])
        volumes = np.array([100.0, 200.0, 300.0, 400.0])
        result = calc_obv(closes, volumes)
        # 100, 100+200, 300+300, 600+400
        assert result[0] == 100.0
        assert result[1] == 300.0
        assert result[2] == 600.0
        assert result[3] == 1000.0

    def test_obv_all_down(self):
        closes = np.array([103.0, 102.0, 101.0, 100.0])
        volumes = np.array([100.0, 200.0, 300.0, 400.0])
        result = calc_obv(closes, volumes)
        # 100, 100-200, -100-300, -400-400
        assert result[0] == 100.0
        assert result[1] == -100.0
        assert result[2] == -400.0
        assert result[3] == -800.0

    def test_obv_flat_unchanged(self):
        closes = np.array([100.0, 100.0, 100.0])
        volumes = np.array([100.0, 200.0, 300.0])
        result = calc_obv(closes, volumes)
        assert result[0] == 100.0
        assert result[1] == 100.0
        assert result[2] == 100.0

    def test_obv_empty_input(self):
        result = calc_obv(np.array([]), np.array([]))
        assert len(result) == 0

    def test_obv_mixed_direction(self):
        closes = np.array([100.0, 101.0, 99.0, 100.0])
        volumes = np.array([100.0, 200.0, 300.0, 400.0])
        result = calc_obv(closes, volumes)
        assert result[0] == 100.0
        assert result[1] == 300.0   # +200
        assert result[2] == 0.0     # -300
        assert result[3] == 400.0   # +400


# ---------------------------------------------------------------------------
# MFI Tests
# ---------------------------------------------------------------------------


class TestMFI:
    def test_mfi_basic_range(self):
        np.random.seed(42)
        n = 30
        c = np.cumsum(np.random.randn(n)) + 100
        h = c + 1
        l = c - 1
        v = np.random.uniform(100, 1000, n)
        result = calc_mfi(h, l, c, v, period=14)
        valid = result[~np.isnan(result)]
        assert all(0 <= x <= 100 for x in valid)

    def test_mfi_insufficient_data(self):
        h = np.array([10.0, 11.0])
        l = np.array([9.0, 10.0])
        c = np.array([9.5, 10.5])
        v = np.array([100.0, 200.0])
        result = calc_mfi(h, l, c, v, period=14)
        assert all(np.isnan(result))

    def test_mfi_all_positive_flow(self):
        n = 20
        c = np.arange(100.0, 100.0 + n)
        h = c + 1
        l = c - 1
        v = np.full(n, 1000.0)
        result = calc_mfi(h, l, c, v, period=14)
        # All positive flow → MFI should be 100
        valid = result[~np.isnan(result)]
        assert all(v == pytest.approx(100.0) for v in valid)

    def test_mfi_first_n_values_nan(self):
        np.random.seed(42)
        n = 30
        c = np.random.uniform(99, 101, n)
        h = c + 1
        l = c - 1
        v = np.random.uniform(100, 500, n)
        result = calc_mfi(h, l, c, v, period=14)
        assert all(np.isnan(result[:14]))

    def test_mfi_length_matches(self):
        n = 25
        c = np.random.uniform(99, 101, n)
        h = c + 1
        l = c - 1
        v = np.random.uniform(100, 500, n)
        result = calc_mfi(h, l, c, v, period=14)
        assert len(result) == n


# ---------------------------------------------------------------------------
# Volume SMA Tests
# ---------------------------------------------------------------------------


class TestVolumeSMA:
    def test_volume_sma_basic(self):
        volumes = np.array([float(i) for i in range(1, 26)])
        result = calc_volume_sma(volumes, period=20)
        assert all(np.isnan(result[:19]))
        assert result[19] == pytest.approx(np.mean(volumes[:20]))

    def test_volume_sma_insufficient_data(self):
        volumes = np.array([100.0, 200.0])
        result = calc_volume_sma(volumes, period=20)
        assert all(np.isnan(result))

    def test_volume_sma_constant_volume(self):
        volumes = np.full(25, 500.0)
        result = calc_volume_sma(volumes, period=20)
        assert result[19] == pytest.approx(500.0)
        assert result[24] == pytest.approx(500.0)

    def test_volume_sma_period_1(self):
        volumes = np.array([100.0, 200.0, 300.0])
        result = calc_volume_sma(volumes, period=1)
        np.testing.assert_array_almost_equal(result, volumes)
