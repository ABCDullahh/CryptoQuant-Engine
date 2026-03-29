"""Markets endpoint — fetches available trading pairs from Binance Futures.

Uses CCXT to load Binance USDM Futures markets and returns
symbol list with metadata. Cached in-memory for 5 minutes.
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user
from app.data.providers.exchange_factory import create_exchange

logger = structlog.get_logger(__name__)

router = APIRouter()

# In-memory cache: (timestamp, data)
_cache: tuple[float, list[dict]] | None = None
_CACHE_TTL = 300  # 5 minutes


async def _fetch_markets_from_binance() -> list[dict]:
    """Fetch USDT-margined futures markets from Binance via CCXT."""
    exchange = await create_exchange()
    try:
        await exchange.load_markets()
        markets = []
        for symbol, market in exchange.markets.items():
            # Only include active USDT-margined perpetual futures
            if not market.get("active", False):
                continue
            if market.get("quote") != "USDT":
                continue
            if not market.get("swap", False):
                continue

            markets.append({
                "symbol": f"{market['base']}/USDT",
                "base": market["base"],
                "quote": "USDT",
                "exchange_symbol": symbol,
                "active": True,
                "price_precision": market.get("precision", {}).get("price"),
                "amount_precision": market.get("precision", {}).get("amount"),
                "min_notional": market.get("limits", {}).get("cost", {}).get("min"),
                "contract_size": market.get("contractSize", 1),
            })

        # Sort by base currency (BTC first, then ETH, then alphabetical)
        priority = {"BTC": 0, "ETH": 1, "BNB": 2, "SOL": 3, "XRP": 4}
        markets.sort(key=lambda m: (priority.get(m["base"], 999), m["base"]))

        return markets
    finally:
        await exchange.close()


@router.get("/orderbook")
async def get_orderbook(
    symbol: str = "BTC/USDT",
    limit: int = 20,
):
    """Fetch order book snapshot from Binance Futures.

    Returns top N bids and asks for the given symbol.
    No authentication required — public market data.
    """
    # Binance only accepts specific depth limits
    valid_limits = [5, 10, 20, 50, 100, 500, 1000]
    snapped = min((v for v in valid_limits if v >= limit), default=20)
    try:
        from app.services.orderbook_streamer import fetch_orderbook_snapshot
        data = await fetch_orderbook_snapshot(symbol, snapped)
        return data
    except Exception as exc:
        logger.warning("orderbook.fetch_failed", symbol=symbol, error=str(exc))
        return {"symbol": symbol, "bids": [], "asks": [], "timestamp": None, "error": "Order book fetch failed"}


@router.get("")
async def get_markets():
    """Fetch available USDT-margined futures markets from Binance.

    Cached for 5 minutes to avoid hitting Binance rate limits.
    No authentication required — public market data.
    """
    global _cache

    now = time.time()
    if _cache and (now - _cache[0]) < _CACHE_TTL:
        return {"markets": _cache[1], "cached": True, "count": len(_cache[1])}

    try:
        markets = await _fetch_markets_from_binance()
        _cache = (now, markets)
        logger.info("markets.fetched", count=len(markets))
        return {"markets": markets, "cached": False, "count": len(markets)}
    except Exception as exc:
        logger.warning("markets.fetch_failed", error=str(exc))
        # Return cached data if available, even if stale
        if _cache:
            return {"markets": _cache[1], "cached": True, "stale": True, "count": len(_cache[1])}
        # Fallback to hardcoded top symbols
        fallback = [
            {"symbol": s, "base": s.split("/")[0], "quote": "USDT", "active": True}
            for s in ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
                       "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT"]
        ]
        return {"markets": fallback, "cached": False, "fallback": True, "count": len(fallback)}


@router.get("/balance")
async def get_balance():
    """Fetch full account balance from Binance Futures (USDM + Coin-M).

    Returns all non-zero asset balances, not just USDT.
    """
    try:
        exchange = await create_exchange(auth=True)
        try:
            balance = await exchange.fetch_balance()

            # Collect ALL non-zero assets
            assets = []
            total_usd_value = 0.0
            for currency, data in balance.items():
                if not isinstance(data, dict):
                    continue
                total_val = float(data.get("total", 0) or 0)
                if total_val == 0:
                    continue
                asset = {
                    "currency": currency,
                    "total": total_val,
                    "free": float(data.get("free", 0) or 0),
                    "used": float(data.get("used", 0) or 0),
                }
                assets.append(asset)
                # Approximate USD value for summary
                if currency in ("USDT", "USDC", "BUSD", "FDUSD"):
                    total_usd_value += total_val

            # Sort: stablecoins first, then by total descending
            stables = {"USDT", "USDC", "BUSD", "FDUSD"}
            assets.sort(key=lambda a: (a["currency"] not in stables, -a["total"]))

            # Primary balance (USDT) for backward compat
            usdt = balance.get("USDT", {})

            return {
                "total": float(usdt.get("total", 0) or 0),
                "free": float(usdt.get("free", 0) or 0),
                "used": float(usdt.get("used", 0) or 0),
                "currency": "USDT",
                "assets": assets,
                "total_usd_value": total_usd_value,
                "source": "binance",
            }
        finally:
            await exchange.close()
    except Exception as exc:
        logger.warning("balance.failed", error=str(exc))
        return {
            "total": 0, "free": 0, "used": 0, "currency": "USDT",
            "assets": [], "total_usd_value": 0,
            "source": "error", "error": "Balance fetch failed",
        }


@router.get("/leverage-tiers")
async def get_leverage_tiers(
    symbol: str = Query(default="BTC/USDT"),
    user: str = Depends(get_current_user),
):
    """Fetch leverage tier brackets for a symbol from Binance."""
    exchange = await create_exchange(auth=True)
    try:
        await exchange.load_markets()
        exchange_symbol = f"{symbol}:USDT" if ":USDT" not in symbol else symbol
        tiers = await exchange.fetch_leverage_tiers([exchange_symbol])
        tier_list = tiers.get(exchange_symbol, [])

        max_leverage = max((t.get("maxLeverage", 1) for t in tier_list), default=1)

        return {
            "symbol": symbol,
            "max_leverage": int(max_leverage),
            "tiers": [
                {
                    "min_notional": t.get("minNotional", 0),
                    "max_notional": t.get("maxNotional", 0),
                    "max_leverage": int(t.get("maxLeverage", 1)),
                }
                for t in tier_list
            ],
        }
    except Exception as exc:
        logger.warning("leverage_tiers.failed", symbol=symbol, error=str(exc))
        return {"symbol": symbol, "max_leverage": 20, "tiers": []}
    finally:
        await exchange.close()
