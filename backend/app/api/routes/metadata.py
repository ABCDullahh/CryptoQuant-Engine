"""Platform metadata — single source of truth for strategies, timeframes, config."""

from __future__ import annotations

from fastapi import APIRouter

from app.config.constants import (
    AVAILABLE_STRATEGIES,
    APP_VERSION,
    DEFAULT_LEVERAGE,
    ENTRY_ZONE_PCT,
    MAX_DAILY_LOSS,
    MAX_DRAWDOWN,
    MAX_LEVERAGE,
    MAX_OPEN_POSITIONS,
    MAX_PORTFOLIO_HEAT,
    MAX_RISK_PER_TRADE,
    TP1_CLOSE_PCT,
    TP1_RR_RATIO,
    TP2_CLOSE_PCT,
    TP2_RR_RATIO,
    TP3_CLOSE_PCT,
    TP3_RR_RATIO,
    Timeframe,
)
from app.config.settings import get_settings

router = APIRouter()


@router.get("")
async def get_metadata():
    """Return platform metadata for frontend consumption.

    This is the single source of truth for strategies, timeframes,
    risk defaults, TP defaults, and app version. Frontend should
    fetch this once and use it for all dropdowns/config.
    """
    settings = get_settings()

    return {
        "strategies": AVAILABLE_STRATEGIES,
        "timeframes": [
            {"value": tf.value, "label": tf.value}
            for tf in Timeframe
        ],
        "risk_defaults": {
            "default_risk_pct": MAX_RISK_PER_TRADE,
            "max_leverage": MAX_LEVERAGE,
            "default_leverage": DEFAULT_LEVERAGE,
            "max_positions": MAX_OPEN_POSITIONS,
            "max_portfolio_heat": MAX_PORTFOLIO_HEAT,
            "max_daily_loss": MAX_DAILY_LOSS,
            "max_drawdown": MAX_DRAWDOWN,
        },
        "tp_defaults": {
            "tp1": {"rr_ratio": TP1_RR_RATIO, "close_pct": TP1_CLOSE_PCT},
            "tp2": {"rr_ratio": TP2_RR_RATIO, "close_pct": TP2_CLOSE_PCT},
            "tp3": {"rr_ratio": TP3_RR_RATIO, "close_pct": TP3_CLOSE_PCT},
        },
        "entry_zone_pct": ENTRY_ZONE_PCT,
        "version": APP_VERSION,
        "environment": settings.environment,
        "trading_enabled": settings.trading_enabled,
    }
