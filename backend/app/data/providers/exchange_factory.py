"""Centralized CCXT exchange instance factory.

Provides a single helper to create properly configured Binance USDM Futures
exchange instances, eliminating duplicate initialization code across routes
and services.

Usage:
    exchange = await create_exchange()          # Public data (no auth)
    exchange = await create_exchange(auth=True)  # With API keys

IMPORTANT: Caller MUST call `await exchange.close()` when done (use try/finally).
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


async def create_exchange(*, auth: bool = False):
    """Create a configured CCXT binanceusdm instance.

    Args:
        auth: If True, attach API key/secret from settings for
              authenticated endpoints (balance, positions, orders).

    Returns:
        Configured ccxt.async_support.binanceusdm instance.
        Caller MUST call ``await exchange.close()`` when done.
    """
    import ccxt.async_support as ccxt

    from app.config.settings import get_settings

    settings = get_settings()

    config: dict = {
        "enableRateLimit": True,
        "options": {"defaultType": "future", "recvWindow": 60000},
    }

    if auth:
        if settings.exchange_api_key and settings.exchange_api_secret:
            config["apiKey"] = settings.exchange_api_key
            config["secret"] = settings.exchange_api_secret

    exchange = ccxt.binanceusdm(config)

    if settings.binance_testnet:
        exchange.enable_demo_trading(True)

    return exchange
