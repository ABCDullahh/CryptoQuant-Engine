"""Data loader for backtesting — loads candles from DB or generates synthetic data."""

from __future__ import annotations

import re
import warnings
from datetime import datetime, timedelta, timezone

import numpy as np
import structlog

from app.core.models import Candle

logger = structlog.get_logger(__name__)


def normalize_symbol(symbol: str) -> str:
    """Normalize symbol to exchange format: BTCUSDT -> BTC/USDT."""
    if "/" in symbol:
        return symbol
    # Match base + quote currency (USDT, BUSD, USD, BTC, ETH)
    match = re.match(r"^([A-Z]+?)(USDT|BUSD|USD|BTC|ETH)$", symbol.upper())
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return symbol


def denormalize_symbol(symbol: str) -> str:
    """Denormalize symbol: BTC/USDT -> BTCUSDT."""
    return symbol.replace("/", "")


_TIMEFRAME_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480, "12h": 720,
    "1d": 1440, "1D": 1440, "1w": 10080, "1W": 10080,
}


def generate_synthetic_candles(
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    initial_price: float | None = None,
) -> list[Candle]:
    """Generate synthetic OHLCV candles using a random walk with drift.

    Produces realistic-looking candle data for dev/testing when no DB is available.
    """
    norm_symbol = normalize_symbol(symbol)
    minutes = _TIMEFRAME_MINUTES.get(timeframe, 60)
    delta = timedelta(minutes=minutes)

    # Ensure timezone-aware
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    # Calculate number of candles
    total_minutes = (end_date - start_date).total_seconds() / 60
    n_candles = max(int(total_minutes / minutes), 1)

    # Seed for reproducibility within the same request
    rng = np.random.default_rng(seed=42)

    # Default starting price based on symbol
    if initial_price is None:
        if "BTC" in norm_symbol:
            initial_price = 43000.0
        elif "ETH" in norm_symbol:
            initial_price = 2500.0
        elif "BNB" in norm_symbol:
            initial_price = 300.0
        elif "SOL" in norm_symbol:
            initial_price = 100.0
        else:
            initial_price = 1.0

    candles: list[Candle] = []
    price = initial_price
    volatility = initial_price * 0.002  # 0.2% per candle

    for i in range(n_candles):
        time = start_date + delta * i
        if time >= end_date:
            break

        # Random walk with slight upward drift
        change = rng.normal(0.0001, 1.0) * volatility
        open_price = price
        close_price = open_price + change
        high_price = max(open_price, close_price) + abs(rng.normal(0, 0.3)) * volatility
        low_price = min(open_price, close_price) - abs(rng.normal(0, 0.3)) * volatility

        # Ensure valid OHLC relationship
        low_price = max(low_price, close_price * 0.95)  # Don't let it go too low
        high_price = max(high_price, max(open_price, close_price))
        low_price = min(low_price, min(open_price, close_price))

        volume = abs(rng.normal(500, 200)) + 10

        candles.append(Candle(
            time=time,
            symbol=norm_symbol,
            timeframe=timeframe,
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=round(volume, 2),
        ))
        price = close_price

    return candles


async def fetch_candles_from_exchange(
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
) -> list[Candle]:
    """Fetch candles from Binance REST via CCXT fetch_ohlcv.

    Loops with `since` parameter to handle > 1500 candle requests.
    """
    norm_symbol = normalize_symbol(symbol)

    from app.data.providers.exchange_factory import create_exchange

    exchange_symbol = f"{norm_symbol}:USDT" if ":USDT" not in norm_symbol else norm_symbol
    exchange = await create_exchange()

    try:
        await exchange.load_markets()
        minutes = _TIMEFRAME_MINUTES.get(timeframe, 60)

        all_candles: list[Candle] = []
        since_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)
        batch_limit = 1500

        while since_ms < end_ms:
            ohlcv = await exchange.fetch_ohlcv(
                exchange_symbol, timeframe, since=since_ms, limit=batch_limit
            )
            if not ohlcv:
                break

            for row in ohlcv:
                ts_ms = int(row[0])
                if ts_ms > end_ms:
                    break
                dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                all_candles.append(Candle(
                    time=dt,
                    symbol=norm_symbol,
                    timeframe=timeframe,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                ))

            # Advance since to after the last candle
            last_ts = int(ohlcv[-1][0])
            if last_ts <= since_ms:
                break  # No progress — avoid infinite loop
            since_ms = last_ts + (minutes * 60 * 1000)

            if len(ohlcv) < batch_limit:
                break  # No more data to fetch

        logger.info(
            "backtest.exchange_fetch_ok",
            symbol=norm_symbol,
            timeframe=timeframe,
            candles=len(all_candles),
        )
        return all_candles

    except Exception as exc:
        logger.warning(
            "backtest.exchange_fetch_failed",
            symbol=norm_symbol,
            error=str(exc),
        )
        return []
    finally:
        await exchange.close()


async def load_candles(
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    db_session=None,
) -> list[Candle]:
    """Load candles from Binance REST (primary), DB (fallback), or synthetic data.

    Priority: Binance REST -> TimescaleDB -> synthetic data.
    """
    norm_symbol = normalize_symbol(symbol)

    # Try Binance REST first (real exchange data)
    try:
        exchange_candles = await fetch_candles_from_exchange(
            norm_symbol, timeframe, start_date, end_date
        )
        if exchange_candles:
            return exchange_candles
    except Exception as exc:
        logger.warning(
            "backtest.exchange_load_failed",
            symbol=norm_symbol,
            error=str(exc),
        )

    # Fallback: Try DB if session available
    if db_session is not None:
        try:
            from sqlalchemy import select
            from app.db.models import CandleModel

            query = (
                select(CandleModel)
                .where(CandleModel.symbol == norm_symbol)
                .where(CandleModel.timeframe == timeframe)
                .where(CandleModel.time >= start_date)
                .where(CandleModel.time <= end_date)
                .order_by(CandleModel.time.asc())
            )
            result = await db_session.execute(query)
            rows = result.scalars().all()

            if rows:
                return [
                    Candle(
                        time=row.time,
                        symbol=row.symbol,
                        timeframe=row.timeframe,
                        open=float(row.open),
                        high=float(row.high),
                        low=float(row.low),
                        close=float(row.close),
                        volume=float(row.volume),
                        quote_volume=float(row.quote_volume) if row.quote_volume else None,
                        trades_count=row.trades_count,
                    )
                    for row in rows
                ]
        except Exception as exc:
            logger.warning(
                "backtest.db_load_failed",
                symbol=norm_symbol,
                error=str(exc),
            )

    # Fallback: generate synthetic data
    warnings.warn(
        f"Using SYNTHETIC data for {norm_symbol} {timeframe} "
        f"({start_date.date()} to {end_date.date()}). "
        "Backtest results will NOT reflect real market conditions.",
        UserWarning,
        stacklevel=2,
    )
    logger.warning(
        "backtest.using_synthetic_data",
        symbol=norm_symbol,
        timeframe=timeframe,
        start=str(start_date.date()),
        end=str(end_date.date()),
    )
    return generate_synthetic_candles(norm_symbol, timeframe, start_date, end_date)
