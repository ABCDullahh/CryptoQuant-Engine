"""Unit tests for trend indicators: SMA, EMA, MACD, ADX."""

from __future__ import annotations

import numpy as np
import pytest

from app.indicators.trend import calc_adx, calc_ema, calc_macd, calc_sma


# ---------------------------------------------------------------------------
# SMA Tests
# ---------------------------------------------------------------------------


class TestSMA:
    def test_sma_basic(self):
        closes = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = calc_sma(closes, 3)
        assert np.isnan(result[0])
        assert np.isnan(result[1])
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(3.0)
        assert result[4] == pytest.approx(4.0)

    def test_sma_period_equals_length(self):
        closes = np.array([2.0, 4.0, 6.0])
        result = calc_sma(closes, 3)
        assert result[2] == pytest.approx(4.0)
        assert np.isnan(result[0])

    def test_sma_insufficient_data(self):
        closes = np.array([1.0, 2.0])
        result = calc_sma(closes, 5)
        assert all(np.isnan(result))

    def test_sma_period_1(self):
        closes = np.array([10.0, 20.0, 30.0])
        result = calc_sma(closes, 1)
        np.testing.assert_array_almost_equal(result, closes)

    def test_sma_constant_values(self):
        closes = np.full(10, 5.0)
        result = calc_sma(closes, 3)
        assert result[2] == pytest.approx(5.0)
        assert result[9] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# EMA Tests
# ---------------------------------------------------------------------------


class TestEMA:
    def test_ema_basic(self):
        closes = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        result = calc_ema(closes, 3)
        # First 2 values should be NaN
        assert np.isnan(result[0])
        assert np.isnan(result[1])
        # Seed = SMA(1,2,3) = 2.0
        assert result[2] == pytest.approx(2.0)
        # EMA(3) = 3 * (2/4) + 2.0 * (2/4) ... wait, multiplier = 2/(3+1) = 0.5
        # result[3] = 4 * 0.5 + 2.0 * 0.5 = 3.0
        assert result[3] == pytest.approx(3.0)

    def test_ema_insufficient_data(self):
        closes = np.array([1.0, 2.0])
        result = calc_ema(closes, 5)
        assert all(np.isnan(result))

    def test_ema_period_1(self):
        closes = np.array([10.0, 20.0, 30.0])
        result = calc_ema(closes, 1)
        # With period 1, multiplier = 2/2 = 1.0, so EMA = close itself
        np.testing.assert_array_almost_equal(result, closes)

    def test_ema_constant_values(self):
        closes = np.full(20, 42.0)
        result = calc_ema(closes, 5)
        # EMA of constant = constant
        assert result[4] == pytest.approx(42.0)
        assert result[19] == pytest.approx(42.0)

    def test_ema_responds_faster_than_sma(self):
        closes = np.array([10.0] * 10 + [20.0] * 5)
        ema = calc_ema(closes, 5)
        sma = calc_sma(closes, 5)
        # After jump, EMA should be closer to 20 than SMA
        assert ema[11] > sma[11]

    def test_ema_seed_is_sma(self):
        closes = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        result = calc_ema(closes, 5)
        # Seed at index 4 = mean(2,4,6,8,10) = 6.0
        assert result[4] == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# MACD Tests
# ---------------------------------------------------------------------------


class TestMACD:
    def test_macd_returns_three_arrays(self):
        closes = np.random.uniform(40000, 45000, 50)
        macd_line, signal, histogram = calc_macd(closes)
        assert len(macd_line) == 50
        assert len(signal) == 50
        assert len(histogram) == 50

    def test_macd_insufficient_data(self):
        closes = np.array([1.0, 2.0, 3.0])
        macd_line, signal, histogram = calc_macd(closes)
        assert all(np.isnan(macd_line))

    def test_macd_histogram_equals_line_minus_signal(self):
        closes = np.random.uniform(100, 200, 60)
        macd_line, signal, histogram = calc_macd(closes)
        # Where both are valid, histogram = line - signal
        valid = ~np.isnan(macd_line) & ~np.isnan(signal)
        np.testing.assert_array_almost_equal(
            histogram[valid], (macd_line - signal)[valid]
        )

    def test_macd_constant_price_zero_macd(self):
        closes = np.full(60, 100.0)
        macd_line, signal, histogram = calc_macd(closes)
        valid = ~np.isnan(macd_line)
        np.testing.assert_array_almost_equal(macd_line[valid], 0.0, decimal=10)

    def test_macd_trending_up_positive(self):
        closes = np.linspace(100, 200, 60)
        macd_line, _, _ = calc_macd(closes)
        # In strong uptrend, MACD line should be positive
        assert macd_line[-1] > 0


# ---------------------------------------------------------------------------
# ADX Tests
# ---------------------------------------------------------------------------


class TestADX:
    def test_adx_returns_correct_length(self):
        n = 50
        h = np.random.uniform(101, 105, n)
        l = np.random.uniform(95, 99, n)
        c = np.random.uniform(98, 103, n)
        result = calc_adx(h, l, c, period=14)
        assert len(result) == n

    def test_adx_insufficient_data(self):
        h = np.array([1.0, 2.0])
        l = np.array([0.5, 1.5])
        c = np.array([0.8, 1.8])
        result = calc_adx(h, l, c, period=14)
        assert all(np.isnan(result))

    def test_adx_range_0_to_100(self):
        np.random.seed(42)
        n = 100
        c = np.cumsum(np.random.randn(n)) + 100
        h = c + np.random.uniform(0.5, 2, n)
        l = c - np.random.uniform(0.5, 2, n)
        result = calc_adx(h, l, c)
        valid = result[~np.isnan(result)]
        assert all(v >= 0 for v in valid)
        assert all(v <= 100 for v in valid)

    def test_adx_strong_trend(self):
        n = 100
        c = np.linspace(100, 200, n)
        h = c + 1
        l = c - 1
        result = calc_adx(h, l, c)
        valid = result[~np.isnan(result)]
        if len(valid) > 0:
            # Strong uptrend should produce high ADX
            assert valid[-1] > 20
