"""Lightweight real-time price streamer.

Streams live ticker data from Binance Futures via CCXT Pro WebSocket and
publishes price_update events through Redis EventBus -> ws_bridge -> WebSocket.

Runs independently of the Bot — chart always gets real-time data.
Uses watch_tickers() which streams all symbols in a single WS connection.
"""

from __future__ import annotations

import asyncio
import time

import structlog

from app.core.events import event_bus

logger = structlog.get_logger(__name__)

# Symbols to stream — futures use :USDT suffix
# Map from display symbol -> exchange symbol
_DISPLAY_SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]
STREAM_SYMBOLS = [f"{s}:USDT" for s in _DISPLAY_SYMBOLS]
# Reverse map: exchange symbol -> display symbol
_SYMBOL_MAP = {f"{s}:USDT": s for s in _DISPLAY_SYMBOLS}

_task: asyncio.Task | None = None
_running = False

# Track current candle per symbol for building OHLCV from ticks
_candle_state: dict[str, dict] = {}
_CANDLE_INTERVAL = 60  # 1 minute candles

# Track last 24h base volume per symbol for delta calculation.
# ticker.baseVolume is cumulative 24h — we need per-candle deltas.
_last_base_volume: dict[str, float] = {}


def _get_candle_start(ts: float) -> int:
    """Round timestamp down to candle interval boundary."""
    return int(ts // _CANDLE_INTERVAL) * _CANDLE_INTERVAL


async def _stream_loop() -> None:
    """Main streaming loop using CCXT Pro watch_tickers."""
    global _running

    import ccxt.pro as ccxt

    _running = True
    exchange = ccxt.binanceusdm({"enableRateLimit": True})

    try:
        await exchange.load_markets()
        logger.info("price_streamer.started", symbols=STREAM_SYMBOLS)

        while _running:
            try:
                tickers = await exchange.watch_tickers(STREAM_SYMBOLS)

                for exchange_symbol, ticker in tickers.items():
                    display_symbol = _SYMBOL_MAP.get(exchange_symbol)
                    if not display_symbol:
                        continue

                    price = ticker.get("last")
                    if not price:
                        continue

                    now = time.time()
                    candle_start = _get_candle_start(now)

                    # Compute per-candle volume delta from cumulative 24h baseVolume
                    raw_vol = ticker.get("baseVolume", 0) or 0
                    prev_vol = _last_base_volume.get(display_symbol)
                    _last_base_volume[display_symbol] = raw_vol

                    # Initialize or roll candle
                    state = _candle_state.get(display_symbol)
                    if not state or state["time"] != candle_start:
                        # New candle boundary — reset volume accumulator
                        _candle_state[display_symbol] = {
                            "time": candle_start,
                            "open": price,
                            "high": price,
                            "low": price,
                            "close": price,
                            "volume": 0.0,
                        }
                    else:
                        state["high"] = max(state["high"], price)
                        state["low"] = min(state["low"], price)
                        state["close"] = price

                    # Accumulate volume delta (positive diff only; reset/wrap → ignore)
                    if prev_vol is not None and raw_vol >= prev_vol:
                        _candle_state[display_symbol]["volume"] += raw_vol - prev_vol

                    cs = _candle_state[display_symbol]

                    await event_bus.publish_raw(
                        "price.update",
                        {
                            "symbol": display_symbol,
                            "price": price,
                            "timeframe": "1m",
                            "time": cs["time"],
                            "open": cs["open"],
                            "high": cs["high"],
                            "low": cs["low"],
                            "close": cs["close"],
                            "volume": cs["volume"],
                            "change_24h": ticker.get("change"),
                            "change_24h_percent": ticker.get("percentage"),
                            "high_24h": ticker.get("high"),
                            "low_24h": ticker.get("low"),
                            "volume_24h": ticker.get("quoteVolume"),
                        },
                    )

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("price_streamer.error", error=str(exc))
                await asyncio.sleep(3)

    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.error("price_streamer.fatal", error=str(exc))
    finally:
        _running = False
        try:
            await exchange.close()
        except Exception as exc:
            logger.debug("price_streamer.close_failed", error=str(exc))
        logger.info("price_streamer.stopped")


async def start_price_streamer() -> None:
    """Start the background price streaming task."""
    global _task
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_stream_loop())
    logger.info("price_streamer.task_created")


async def stop_price_streamer() -> None:
    """Stop the background price streaming task."""
    global _running, _task
    _running = False
    if _task:
        _task.cancel()
        try:
            await _task
        except (asyncio.CancelledError, Exception):
            pass
        _task = None
    logger.info("price_streamer.task_stopped")
