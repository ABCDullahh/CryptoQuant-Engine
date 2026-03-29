"""IndicatorPipeline - orchestrates all indicator calculations."""

from __future__ import annotations

import numpy as np

from app.core.models import Candle, IndicatorValues
from app.indicators.momentum import calc_rsi, calc_stochastic
from app.indicators.trend import calc_adx, calc_ema, calc_macd, calc_sma
from app.indicators.volatility import calc_atr, calc_bollinger_bands
from app.indicators.volume import calc_mfi, calc_obv, calc_volume_sma, calc_vwap


class IndicatorPipeline:
    """Computes all technical indicators from a list of candles."""

    def compute(self, candles: list[Candle]) -> IndicatorValues:
        """Extract OHLCV arrays, run all indicators, return IndicatorValues."""
        if not candles:
            raise ValueError("Cannot compute indicators from empty candle list")

        last = candles[-1]
        opens = np.array([c.open for c in candles], dtype=float)
        highs = np.array([c.high for c in candles], dtype=float)
        lows = np.array([c.low for c in candles], dtype=float)
        closes = np.array([c.close for c in candles], dtype=float)
        volumes = np.array([c.volume for c in candles], dtype=float)

        # Trend
        ema_9 = calc_ema(closes, 9)
        ema_21 = calc_ema(closes, 21)
        ema_55 = calc_ema(closes, 55)
        ema_200 = calc_ema(closes, 200)
        macd_line, macd_signal, macd_hist = calc_macd(closes)
        adx = calc_adx(highs, lows, closes)

        # Momentum
        rsi_14 = calc_rsi(closes)
        stoch_k, stoch_d = calc_stochastic(highs, lows, closes)

        # Volatility
        atr_14 = calc_atr(highs, lows, closes)
        bb_upper, bb_middle, bb_lower = calc_bollinger_bands(closes)

        # Volume
        vwap = calc_vwap(highs, lows, closes, volumes)
        obv = calc_obv(closes, volumes)
        vol_sma_20 = calc_volume_sma(volumes)
        mfi = calc_mfi(highs, lows, closes, volumes)

        def _last_val(arr: np.ndarray) -> float | None:
            """Get last non-NaN value, or None."""
            val = arr[-1]
            if np.isnan(val):
                return None
            return float(val)

        # BB width
        bb_w = None
        bbu = _last_val(bb_upper)
        bbl = _last_val(bb_lower)
        bbm = _last_val(bb_middle)
        if bbu is not None and bbl is not None and bbm is not None and bbm != 0:
            bb_w = (bbu - bbl) / bbm

        return IndicatorValues(
            symbol=last.symbol,
            timeframe=last.timeframe,
            timestamp=last.time,
            ema_9=_last_val(ema_9),
            ema_21=_last_val(ema_21),
            ema_55=_last_val(ema_55),
            ema_200=_last_val(ema_200),
            macd=_last_val(macd_line),
            macd_signal=_last_val(macd_signal),
            macd_histogram=_last_val(macd_hist),
            adx=_last_val(adx),
            rsi_14=_last_val(rsi_14),
            stoch_k=_last_val(stoch_k),
            stoch_d=_last_val(stoch_d),
            atr_14=_last_val(atr_14),
            bb_upper=bbu,
            bb_middle=bbm,
            bb_lower=bbl,
            bb_width=bb_w,
            vwap=_last_val(vwap),
            obv=_last_val(obv),
            volume_sma_20=_last_val(vol_sma_20),
            mfi=_last_val(mfi),
        )
