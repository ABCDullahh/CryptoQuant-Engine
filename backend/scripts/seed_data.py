"""Seed REAL data for CryptoQuant Engine from Binance Futures API.

Fetches live market data from Binance to populate the database with
real candles, user settings, and bot state. Signals and positions are
fetched live from the exchange (not seeded).

Usage:
    cd backend && python -m scripts.seed_data
    cd backend && python scripts/seed_data.py
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Allow running as `python scripts/seed_data.py` from backend/
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from sqlalchemy import delete, select

from app.db.database import async_session_factory, engine, init_db
from app.db.models import (
    BacktestRunModel,
    Base,
    BotStateModel,
    CandleModel,
    PositionModel,
    SignalModel,
    UserSettingsModel,
)

BINANCE_FUTURES_URL = "https://fapi.binance.com"


# ---------------------------------------------------------------------------
# Binance API helpers
# ---------------------------------------------------------------------------

async def fetch_klines(
    client: httpx.AsyncClient,
    symbol: str,
    interval: str = "1h",
    limit: int = 200,
) -> list[dict]:
    """Fetch real OHLCV klines from Binance Futures."""
    url = f"{BINANCE_FUTURES_URL}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    raw = resp.json()

    candles = []
    for k in raw:
        candles.append({
            "time": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "quote_volume": float(k[7]),
            "trades_count": int(k[8]),
        })
    return candles


async def fetch_price(client: httpx.AsyncClient, symbol: str) -> float:
    """Fetch current price from Binance Futures."""
    url = f"{BINANCE_FUTURES_URL}/fapi/v1/ticker/price"
    resp = await client.get(url, params={"symbol": symbol})
    resp.raise_for_status()
    return float(resp.json()["price"])


# ---------------------------------------------------------------------------
# Main seed routine
# ---------------------------------------------------------------------------

async def seed() -> None:
    """Fetch real Binance data and seed into database."""

    print("[seed] Initializing database tables...")
    await init_db()

    async with httpx.AsyncClient(timeout=30) as client:
        # Fetch real prices
        print("[seed] Fetching real prices from Binance Futures...")
        btc_price = await fetch_price(client, "BTCUSDT")
        eth_price = await fetch_price(client, "ETHUSDT")
        print(f"[seed] BTC/USDT = ${btc_price:,.2f}")
        print(f"[seed] ETH/USDT = ${eth_price:,.2f}")

        # Fetch real candles
        print("[seed] Fetching real BTC/USDT 1h candles (200 bars)...")
        btc_candles = await fetch_klines(client, "BTCUSDT", "1h", 200)
        print(f"[seed] Got {len(btc_candles)} real candles from Binance")

        print("[seed] Fetching real ETH/USDT 1h candles (200 bars)...")
        eth_candles = await fetch_klines(client, "ETHUSDT", "1h", 200)
        print(f"[seed] Got {len(eth_candles)} real candles from Binance")

    async with async_session_factory() as session:
        # ------------------------------------------------------------------
        # 0. Clean old seed data (delete all old data to replace with real)
        # ------------------------------------------------------------------
        print("[seed] Cleaning old data...")
        await session.execute(delete(CandleModel))
        await session.execute(delete(SignalModel))
        await session.execute(delete(PositionModel))
        await session.execute(delete(BacktestRunModel))
        await session.execute(delete(BotStateModel))
        # Keep UserSettingsModel (user preferences) and users
        await session.flush()
        print("[seed] Old data cleaned.")

        # ------------------------------------------------------------------
        # 1. Real Candles from Binance
        # ------------------------------------------------------------------
        btc_objs = [
            CandleModel(
                time=c["time"],
                symbol="BTC/USDT",
                timeframe="1h",
                exchange="binance",
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c["volume"],
                quote_volume=c["quote_volume"],
                trades_count=c["trades_count"],
            )
            for c in btc_candles
        ]
        eth_objs = [
            CandleModel(
                time=c["time"],
                symbol="ETH/USDT",
                timeframe="1h",
                exchange="binance",
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c["volume"],
                quote_volume=c["quote_volume"],
                trades_count=c["trades_count"],
            )
            for c in eth_candles
        ]
        session.add_all(btc_objs + eth_objs)
        await session.flush()
        print(f"[seed] Inserted {len(btc_objs)} BTC + {len(eth_objs)} ETH real candles.")

        # ------------------------------------------------------------------
        # 2. User settings (keep defaults if not exist)
        # ------------------------------------------------------------------
        existing_settings = await session.execute(
            select(UserSettingsModel.id).limit(1)
        )
        if existing_settings.scalar() is None:
            user_settings = UserSettingsModel(
                risk_params={
                    "default_risk_pct": 0.02,
                    "max_positions": 5,
                    "max_portfolio_heat": 0.06,
                    "max_leverage": 10,
                    "default_leverage": 3,
                },
                strategy_config={
                    "enabled_strategies": [
                        "momentum",
                        "mean_reversion",
                        "smart_money",
                    ],
                    "signal_expiry_seconds": 900,
                    "min_strategy_agreement": 3,
                },
                notification_config={
                    "telegram_enabled": False,
                    "telegram_chat_id": "",
                    "discord_enabled": False,
                    "discord_webhook": "",
                },
            )
            session.add(user_settings)
            await session.flush()
            print("[seed] Inserted default user settings.")
        else:
            print("[seed] User settings already exist, keeping.")

        # ------------------------------------------------------------------
        # 3. Bot state (clean/reset)
        # ------------------------------------------------------------------
        now = datetime.now(timezone.utc)
        bot_state = BotStateModel(
            is_running=False,
            is_paper_mode=True,
            active_strategies=["momentum", "mean_reversion"],
            started_at=None,
            stopped_at=now,
            total_pnl=0.0,
            metadata_json={},
        )
        session.add(bot_state)
        await session.flush()
        print("[seed] Inserted clean bot state (stopped, paper mode, pnl=0).")

        # ------------------------------------------------------------------
        # Commit all
        # ------------------------------------------------------------------
        await session.commit()
        print("[seed] All REAL data committed successfully!")
        print()
        print(f"[verify] BTC/USDT real price from Binance: ${btc_price:,.2f}")
        print(f"[verify] ETH/USDT real price from Binance: ${eth_price:,.2f}")
        print(f"[verify] Candles: {len(btc_objs)} BTC + {len(eth_objs)} ETH (real Binance data)")
        print("[verify] Signals & positions: skipped (fetched live from exchange)")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
