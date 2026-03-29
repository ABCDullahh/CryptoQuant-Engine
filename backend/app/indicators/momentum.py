"""Momentum indicator calculations - pure numpy, no I/O."""

from __future__ import annotations

import numpy as np


def calc_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index.

    Uses Wilder's smoothing (exponential moving average of gains/losses).
    Returns array same length as input; first `period` values are NaN.
    """
    n = len(closes)
    if n < period + 1:
        return np.full(n, np.nan, dtype=float)

    result = np.full(n, np.nan, dtype=float)
    deltas = np.diff(closes)

    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # Initial average gain/loss
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - 100.0 / (1.0 + rs)

    # Wilder's smoothing for subsequent values
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            result[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i + 1] = 100.0 - 100.0 / (1.0 + rs)

    return result


def calc_stochastic(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    k_period: int = 14,
    d_period: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """Stochastic Oscillator (%K and %D).

    %K = (Close - Lowest Low) / (Highest High - Lowest Low) * 100
    %D = SMA(%K, d_period)
    """
    n = len(closes)
    if n < k_period:
        return np.full(n, np.nan, dtype=float), np.full(n, np.nan, dtype=float)

    stoch_k = np.full(n, np.nan, dtype=float)

    for i in range(k_period - 1, n):
        window_high = np.max(highs[i - k_period + 1 : i + 1])
        window_low = np.min(lows[i - k_period + 1 : i + 1])
        range_hl = window_high - window_low

        if range_hl == 0:
            stoch_k[i] = 50.0  # Midpoint when no range
        else:
            stoch_k[i] = (closes[i] - window_low) / range_hl * 100.0

    # %D = SMA of %K
    stoch_d = np.full(n, np.nan, dtype=float)
    valid_k_start = k_period - 1
    for i in range(valid_k_start + d_period - 1, n):
        stoch_d[i] = np.mean(stoch_k[i - d_period + 1 : i + 1])

    return stoch_k, stoch_d
