"""GARCH-based volatility forecasting for risk management.

Uses arch library to fit GARCH(1,1) or GJR-GARCH models and produce
forward-looking volatility forecasts. This replaces backward-looking
ATR for stop-loss placement and position sizing.

Crypto-specific: uses GED (Generalized Error Distribution) to capture
fat-tailed returns common in cryptocurrency markets.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

try:
    from arch import arch_model

    ARCH_AVAILABLE = True
except ImportError:
    ARCH_AVAILABLE = False
    logger.warning("arch not installed — GARCH models unavailable")


@dataclass
class VolatilityForecast:
    """Result of a GARCH volatility forecast."""

    current_vol: float  # Current annualized volatility
    forecast_1h: float  # 1-period ahead forecast (annualized)
    forecast_1d: float  # Daily forecast (annualized)
    vol_regime: str  # "low" | "normal" | "high" | "extreme"
    vol_trend: str  # "expanding" | "stable" | "contracting"
    confidence: float  # Model fit quality (0-1)


def forecast_volatility(
    closes: list[float],
    min_observations: int = 100,
) -> VolatilityForecast | None:
    """Fit GARCH(1,1) with GED distribution and produce volatility forecast.

    Args:
        closes: List of close prices (oldest first), minimum 100.
        min_observations: Minimum data points required.

    Returns:
        VolatilityForecast or None if insufficient data / model fails.
    """
    if not ARCH_AVAILABLE:
        return None

    if len(closes) < min_observations:
        return None

    try:
        # Compute log returns (percentage * 100 for numerical stability)
        prices = np.array(closes, dtype=np.float64)
        returns = np.diff(np.log(prices)) * 100

        if len(returns) < min_observations:
            return None

        # Fit GJR-GARCH(1,1) with GED distribution
        # GJR captures asymmetric volatility (crypto crashes > rallies)
        model = arch_model(
            returns,
            vol="GARCH",
            p=1,
            q=1,
            dist="ged",
            rescale=False,
        )

        result = model.fit(disp="off", show_warning=False)

        # Current conditional volatility (last fitted value)
        cond_vol = result.conditional_volatility
        cond_vol_values = cond_vol.values if hasattr(cond_vol, 'values') else np.array(cond_vol)
        current_vol = float(cond_vol_values[-1]) if len(cond_vol_values) > 0 else 0.0

        # 1-step ahead forecast
        forecast = result.forecast(horizon=1)
        fv = forecast.variance
        # Handle both DataFrame and ndarray
        if hasattr(fv, 'iloc'):
            forecast_var = float(fv.iloc[-1].values[0])
        elif hasattr(fv, 'values'):
            vals = fv.values
            forecast_var = float(vals[-1][0] if vals.ndim > 1 else vals[-1])
        else:
            forecast_var = float(np.array(fv).flatten()[-1])
        forecast_vol_1h = float(np.sqrt(forecast_var))

        # Annualize (assuming hourly data, ~8760 hours/year)
        annual_factor = np.sqrt(8760)
        current_annual = current_vol * annual_factor / 100
        forecast_1h_annual = forecast_vol_1h * annual_factor / 100

        # Daily forecast (24 hours)
        forecast_1d = forecast_vol_1h * np.sqrt(24) / 100

        # Classify volatility regime
        recent_vols = cond_vol_values[-20:] if len(cond_vol_values) >= 20 else cond_vol_values
        median_vol = float(np.median(recent_vols))
        vol_ratio = current_vol / median_vol if median_vol > 0 else 1.0

        if vol_ratio < 0.7:
            vol_regime = "low"
        elif vol_ratio < 1.3:
            vol_regime = "normal"
        elif vol_ratio < 2.0:
            vol_regime = "high"
        else:
            vol_regime = "extreme"

        # Detect vol trend (expanding/contracting)
        if len(cond_vol_values) >= 10:
            recent_5 = float(np.mean(cond_vol_values[-5:]))
            prior_5 = float(np.mean(cond_vol_values[-10:-5]))
            if recent_5 > prior_5 * 1.1:
                vol_trend = "expanding"
            elif recent_5 < prior_5 * 0.9:
                vol_trend = "contracting"
            else:
                vol_trend = "stable"
        else:
            vol_trend = "stable"

        # Model fit quality (R-squared proxy from log-likelihood)
        ll = result.loglikelihood
        n = len(returns)
        # Normalize to 0-1 range (heuristic)
        confidence = min(1.0, max(0.0, 0.5 + (ll / n) / 10))

        return VolatilityForecast(
            current_vol=current_annual,
            forecast_1h=forecast_1h_annual,
            forecast_1d=forecast_1d,
            vol_regime=vol_regime,
            vol_trend=vol_trend,
            confidence=confidence,
        )

    except Exception as exc:
        logger.debug("garch.forecast_failed", error=str(exc))
        return None


def garch_stop_distance(
    closes: list[float],
    multiplier: float = 2.0,
) -> float | None:
    """Calculate stop-loss distance using GARCH-forecasted volatility.

    Uses forward-looking forecasted vol instead of backward-looking ATR.

    Args:
        closes: Price history.
        multiplier: Volatility multiplier (like ATR multiplier).

    Returns:
        Suggested stop distance in price units, or None if unavailable.
    """
    forecast = forecast_volatility(closes)
    if forecast is None:
        return None

    current_price = closes[-1]
    # Convert daily vol percentage to price distance
    daily_vol_pct = forecast.forecast_1d
    stop_distance = current_price * daily_vol_pct * multiplier

    return stop_distance
