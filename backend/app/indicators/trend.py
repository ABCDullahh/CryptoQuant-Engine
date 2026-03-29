"""Trend indicator calculations - pure numpy, no I/O."""

from __future__ import annotations

import numpy as np


def calc_sma(closes: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average.

    Returns array same length as input; positions before `period` are NaN.
    """
    if len(closes) < period:
        return np.full_like(closes, np.nan, dtype=float)

    result = np.full_like(closes, np.nan, dtype=float)
    # Cumulative sum trick for O(n) SMA
    cumsum = np.cumsum(closes)
    result[period - 1 :] = (cumsum[period - 1 :] - np.concatenate(([0], cumsum[:-period]))) / period
    return result


def calc_ema(closes: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average.

    Uses SMA of first `period` values as seed, then applies EMA formula.
    Returns array same length as input; positions before `period` are NaN.
    """
    if len(closes) < period:
        return np.full_like(closes, np.nan, dtype=float)

    result = np.full(len(closes), np.nan, dtype=float)
    multiplier = 2.0 / (period + 1)

    # Seed with SMA of first `period` values
    result[period - 1] = np.mean(closes[:period])

    for i in range(period, len(closes)):
        result[i] = closes[i] * multiplier + result[i - 1] * (1 - multiplier)

    return result


def calc_macd(
    closes: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD (Moving Average Convergence Divergence).

    Returns (macd_line, signal_line, histogram).
    """
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)

    macd_line = ema_fast - ema_slow

    # Signal line = EMA of MACD line (only from where MACD is valid)
    valid_start = slow - 1  # First valid MACD value
    signal_line = np.full_like(closes, np.nan, dtype=float)

    if len(closes) >= valid_start + signal_period:
        macd_valid = macd_line[valid_start:]
        signal_ema = calc_ema(macd_valid, signal_period)
        signal_line[valid_start:] = signal_ema

    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calc_adx(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Average Directional Index (ADX).

    Measures trend strength regardless of direction.
    Returns array same length as input; early values are NaN.
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

    # Directional Movement
    plus_dm = np.zeros(n, dtype=float)
    minus_dm = np.zeros(n, dtype=float)
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Smoothed TR, +DM, -DM using Wilder's smoothing
    atr_s = np.sum(tr[1 : period + 1])
    plus_dm_s = np.sum(plus_dm[1 : period + 1])
    minus_dm_s = np.sum(minus_dm[1 : period + 1])

    # +DI, -DI, DX series
    dx_values = []

    for i in range(period, n):
        if i == period:
            pass  # Use initial sums
        else:
            atr_s = atr_s - atr_s / period + tr[i]
            plus_dm_s = plus_dm_s - plus_dm_s / period + plus_dm[i]
            minus_dm_s = minus_dm_s - minus_dm_s / period + minus_dm[i]

        if atr_s == 0:
            dx_values.append(0.0)
            continue

        plus_di = 100.0 * plus_dm_s / atr_s
        minus_di = 100.0 * minus_dm_s / atr_s

        di_sum = plus_di + minus_di
        if di_sum == 0:
            dx_values.append(0.0)
        else:
            dx_values.append(100.0 * abs(plus_di - minus_di) / di_sum)

    # ADX = smoothed average of DX
    if len(dx_values) < period:
        return result

    adx_val = np.mean(dx_values[:period])
    result[2 * period - 1] = adx_val

    for i in range(period, len(dx_values)):
        adx_val = (adx_val * (period - 1) + dx_values[i]) / period
        result[period + i] = adx_val

    return result
