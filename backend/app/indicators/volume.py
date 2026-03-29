"""Volume indicator calculations - pure numpy, no I/O."""

from __future__ import annotations

import numpy as np


def calc_vwap(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
) -> np.ndarray:
    """Volume Weighted Average Price (VWAP).

    Cumulative VWAP: sum(TP * Volume) / sum(Volume)
    where TP = (High + Low + Close) / 3
    """
    n = len(closes)
    if n == 0:
        return np.array([], dtype=float)

    typical_price = (highs + lows + closes) / 3.0
    tp_volume = typical_price * volumes
    cum_tp_vol = np.cumsum(tp_volume)
    cum_vol = np.cumsum(volumes)

    result = np.full(n, np.nan, dtype=float)
    nonzero = cum_vol != 0
    result[nonzero] = cum_tp_vol[nonzero] / cum_vol[nonzero]

    return result


def calc_vwap_bands(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    num_std: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """VWAP with standard deviation bands.

    Returns (vwap, upper_band, lower_band).
    Uses volume-weighted standard deviation of typical price.
    """
    n = len(closes)
    if n == 0:
        empty = np.array([], dtype=float)
        return empty, empty, empty

    typical_price = (highs + lows + closes) / 3.0
    tp_volume = typical_price * volumes
    cum_tp_vol = np.cumsum(tp_volume)
    cum_vol = np.cumsum(volumes)

    vwap = np.full(n, np.nan, dtype=float)
    upper = np.full(n, np.nan, dtype=float)
    lower = np.full(n, np.nan, dtype=float)

    nonzero = cum_vol != 0
    vwap[nonzero] = cum_tp_vol[nonzero] / cum_vol[nonzero]

    # Volume-weighted variance: E[X^2] - E[X]^2
    tp_sq_volume = (typical_price ** 2) * volumes
    cum_tp_sq_vol = np.cumsum(tp_sq_volume)
    variance = np.full(n, np.nan, dtype=float)
    variance[nonzero] = cum_tp_sq_vol[nonzero] / cum_vol[nonzero] - vwap[nonzero] ** 2
    variance = np.maximum(variance, 0)  # numerical safety
    std_dev = np.sqrt(variance)

    upper[nonzero] = vwap[nonzero] + num_std * std_dev[nonzero]
    lower[nonzero] = vwap[nonzero] - num_std * std_dev[nonzero]

    return vwap, upper, lower


def calc_obv(closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    """On-Balance Volume (OBV).

    Cumulative volume; added when close > prev close, subtracted when close < prev.
    """
    n = len(closes)
    if n == 0:
        return np.array([], dtype=float)

    result = np.zeros(n, dtype=float)
    result[0] = volumes[0]

    for i in range(1, n):
        if closes[i] > closes[i - 1]:
            result[i] = result[i - 1] + volumes[i]
        elif closes[i] < closes[i - 1]:
            result[i] = result[i - 1] - volumes[i]
        else:
            result[i] = result[i - 1]

    return result


def calc_mfi(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Money Flow Index (MFI).

    Volume-weighted RSI using typical price and volume.
    """
    n = len(closes)
    if n < period + 1:
        return np.full(n, np.nan, dtype=float)

    result = np.full(n, np.nan, dtype=float)
    typical_price = (highs + lows + closes) / 3.0
    money_flow = typical_price * volumes

    for i in range(period, n):
        pos_flow = 0.0
        neg_flow = 0.0
        for j in range(i - period + 1, i + 1):
            if typical_price[j] > typical_price[j - 1]:
                pos_flow += money_flow[j]
            elif typical_price[j] < typical_price[j - 1]:
                neg_flow += money_flow[j]

        if neg_flow == 0:
            result[i] = 100.0
        else:
            mf_ratio = pos_flow / neg_flow
            result[i] = 100.0 - 100.0 / (1.0 + mf_ratio)

    return result


def calc_volume_sma(volumes: np.ndarray, period: int = 20) -> np.ndarray:
    """Simple Moving Average of Volume."""
    n = len(volumes)
    if n < period:
        return np.full(n, np.nan, dtype=float)

    result = np.full(n, np.nan, dtype=float)
    cumsum = np.cumsum(volumes)
    result[period - 1 :] = (
        cumsum[period - 1 :] - np.concatenate(([0], cumsum[:-period]))
    ) / period
    return result
