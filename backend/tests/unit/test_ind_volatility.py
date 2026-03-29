"""Unit tests for volatility indicators: ATR, Bollinger Bands."""

from __future__ import annotations

import numpy as np
import pytest

from app.indicators.volatility import calc_atr, calc_bollinger_bands


# ---------------------------------------------------------------------------
# ATR Tests
# ---------------------------------------------------------------------------


class TestATR:
    def test_atr_basic(self):
        np.random.seed(42)
        n = 30
        c = np.cumsum(np.random.randn(n)) + 100
        h = c + np.random.uniform(0.5, 2, n)
        l = c - np.random.uniform(0.5, 2, n)
        result = calc_atr(h, l, c, period=14)
        assert len(result) == n
        valid = result[~np.isnan(result)]
        assert all(v > 0 for v in valid)

    def test_atr_insufficient_data(self):
        h = np.array([10.0, 11.0])
        l = np.array([9.0, 10.0])
        c = np.array([9.5, 10.5])
        result = calc_atr(h, l, c, period=14)
        assert all(np.isnan(result))

    def test_atr_first_n_values_nan(self):
        np.random.seed(42)
        n = 30
        c = np.cumsum(np.random.randn(n)) + 100
        h = c + 1
        l = c - 1
        result = calc_atr(h, l, c, period=14)
        assert all(np.isnan(result[:14]))
        assert not np.isnan(result[14])

    def test_atr_constant_range(self):
        n = 30
        c = np.full(n, 100.0)
        h = np.full(n, 102.0)
        l = np.full(n, 98.0)
        result = calc_atr(h, l, c, period=14)
        # True Range = 4.0 for every bar
        assert result[14] == pytest.approx(4.0)
        assert result[-1] == pytest.approx(4.0)

    def test_atr_includes_gap(self):
        """ATR should consider gap between prev close and current high/low."""
        n = 20
        c = np.full(n, 100.0)
        h = np.full(n, 101.0)
        l = np.full(n, 99.0)
        # Create a gap: bar 15 opens much higher
        c[15] = 110.0
        h[15] = 111.0
        l[15] = 109.0
        result = calc_atr(h, l, c, period=5)
        # TR at bar 15 = max(111-109, |111-100|, |109-100|) = 11
        # ATR should spike
        assert result[-1] > 2.0

    def test_atr_always_positive(self):
        np.random.seed(42)
        n = 50
        c = np.cumsum(np.random.randn(n)) + 100
        h = c + np.abs(np.random.randn(n))
        l = c - np.abs(np.random.randn(n))
        result = calc_atr(h, l, c)
        valid = result[~np.isnan(result)]
        assert all(v >= 0 for v in valid)

    def test_atr_custom_period(self):
        n = 30
        c = np.random.uniform(99, 101, n)
        h = c + 1
        l = c - 1
        result = calc_atr(h, l, c, period=5)
        assert all(np.isnan(result[:5]))
        assert not np.isnan(result[5])


# ---------------------------------------------------------------------------
# Bollinger Bands Tests
# ---------------------------------------------------------------------------


class TestBollingerBands:
    def test_bb_basic(self):
        closes = np.random.uniform(95, 105, 30)
        upper, middle, lower = calc_bollinger_bands(closes, period=20)
        assert len(upper) == 30

    def test_bb_insufficient_data(self):
        closes = np.array([1.0, 2.0, 3.0])
        upper, middle, lower = calc_bollinger_bands(closes, period=20)
        assert all(np.isnan(upper))
        assert all(np.isnan(middle))
        assert all(np.isnan(lower))

    def test_bb_upper_above_middle_above_lower(self):
        np.random.seed(42)
        closes = np.random.uniform(95, 105, 30)
        upper, middle, lower = calc_bollinger_bands(closes, period=20)
        for i in range(19, 30):
            assert upper[i] >= middle[i] >= lower[i]

    def test_bb_middle_is_sma(self):
        closes = np.array([float(i) for i in range(1, 26)])
        upper, middle, lower = calc_bollinger_bands(closes, period=20)
        # Middle at index 19 = SMA of first 20 values = mean(1..20)
        expected = np.mean(closes[:20])
        assert middle[19] == pytest.approx(expected)

    def test_bb_constant_price_bands_collapse(self):
        closes = np.full(30, 100.0)
        upper, middle, lower = calc_bollinger_bands(closes, period=20)
        # Std dev = 0, so upper = middle = lower = 100
        assert upper[19] == pytest.approx(100.0)
        assert middle[19] == pytest.approx(100.0)
        assert lower[19] == pytest.approx(100.0)

    def test_bb_wider_with_higher_std_dev(self):
        np.random.seed(42)
        closes = np.random.uniform(95, 105, 30)
        u1, m1, l1 = calc_bollinger_bands(closes, period=20, std_dev=1.0)
        u2, m2, l2 = calc_bollinger_bands(closes, period=20, std_dev=3.0)
        # 3 std dev should be wider than 1 std dev
        width1 = u1[25] - l1[25]
        width2 = u2[25] - l2[25]
        assert width2 > width1

    def test_bb_symmetry_around_middle(self):
        np.random.seed(42)
        closes = np.random.uniform(95, 105, 30)
        upper, middle, lower = calc_bollinger_bands(closes, period=20)
        for i in range(19, 30):
            assert upper[i] - middle[i] == pytest.approx(middle[i] - lower[i])
