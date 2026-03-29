"""Volatility indicator calculations - pure numpy, no I/O."""

from __future__ import annotations

import numpy as np


def calc_atr(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Average True Range (ATR).

    Uses Wilder's smoothing method.
    Returns array same length as input; first `period` values are NaN.
    """
    n = len(closes)
    if n < period + 1:
        return np.full(n, np.nan, dtype=float)

    result = np.full(n, np.nan, dtype=float)

    # True Range
    tr = np.empty(n, dtype=float)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    # Initial ATR = SMA of first `period` TR values
    result[period] = np.mean(tr[1 : period + 1])

    # Wilder's smoothing
    for i in range(period + 1, n):
        result[i] = (result[i - 1] * (period - 1) + tr[i]) / period

    return result


def calc_bollinger_bands(
    closes: np.ndarray,
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger Bands.

    Returns (upper, middle, lower) bands.
    Middle = SMA(period), Upper/Lower = Middle +/- std_dev * StdDev.
    """
    n = len(closes)
    upper = np.full(n, np.nan, dtype=float)
    middle = np.full(n, np.nan, dtype=float)
    lower = np.full(n, np.nan, dtype=float)

    if n < period:
        return upper, middle, lower

    for i in range(period - 1, n):
        window = closes[i - period + 1 : i + 1]
        sma = np.mean(window)
        std = np.std(window, ddof=0)

        middle[i] = sma
        upper[i] = sma + std_dev * std
        lower[i] = sma - std_dev * std

    return upper, middle, lower
