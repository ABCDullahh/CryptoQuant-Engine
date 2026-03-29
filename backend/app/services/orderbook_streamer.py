"""Real-time order book streamer via CCXT Pro WebSocket.

Streams live order book updates from Binance Futures for the active symbol
and publishes orderbook.update events through EventBus -> ws_bridge -> WebSocket.

Similar pattern to price_streamer but for a single active symbol at a time.
"""

from __future__ import annotations

import asyncio

import structlog

from app.core.events import event_bus

logger = structlog.get_logger(__name__)

_task: asyncio.Task | None = None
_running = False
_active_symbol: str = "BTC/USDT"
_OB_DEPTH = 20


def get_active_symbol() -> str:
    """Return the currently streamed symbol."""
    return _active_symbol


def set_active_symbol(symbol: str) -> None:
    """Change the active order book symbol.

    The streaming loop will pick up the change on its next iteration.
    """
    global _active_symbol
    _active_symbol = symbol
    logger.info("orderbook_streamer.symbol_changed", symbol=symbol)


async def _stream_loop() -> None:
    """Main streaming loop using CCXT Pro watch_order_book."""
    global _running

    import ccxt.pro as ccxt

    _running = True
    exchange = ccxt.binanceusdm({"enableRateLimit": True})

    try:
        await exchange.load_markets()
        logger.info("orderbook_streamer.started", symbol=_active_symbol)

        prev_symbol: str | None = None

        while _running:
            try:
                symbol = _active_symbol
                exchange_symbol = f"{symbol}:USDT" if ":USDT" not in symbol else symbol

                # If symbol changed, log it
                if symbol != prev_symbol:
                    logger.info(
                        "orderbook_streamer.watching",
                        symbol=symbol,
                        exchange_symbol=exchange_symbol,
                    )
                    prev_symbol = symbol

                ob = await exchange.watch_order_book(exchange_symbol, limit=_OB_DEPTH)

                bids = [[float(p), float(q)] for p, q in (ob.get("bids") or [])[:_OB_DEPTH]]
                asks = [[float(p), float(q)] for p, q in (ob.get("asks") or [])[:_OB_DEPTH]]

                await event_bus.publish_raw(
                    "orderbook.update",
                    {
                        "symbol": symbol,
                        "bids": bids,
                        "asks": asks,
                        "timestamp": ob.get("timestamp"),
                    },
                )

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("orderbook_streamer.error", error=str(exc))
                await asyncio.sleep(3)

    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.error("orderbook_streamer.fatal", error=str(exc))
    finally:
        _running = False
        try:
            await exchange.close()
        except Exception as exc:
            logger.debug("orderbook_streamer.close_failed", error=str(exc))
        logger.info("orderbook_streamer.stopped")


async def fetch_orderbook_snapshot(symbol: str = "BTC/USDT", limit: int = 20) -> dict:
    """Fetch a one-time order book snapshot via CCXT REST.

    Used for the initial load before WebSocket updates arrive.
    """
    from app.data.providers.exchange_factory import create_exchange

    exchange_symbol = f"{symbol}:USDT" if ":USDT" not in symbol else symbol
    exchange = await create_exchange()
    try:
        await exchange.load_markets()
        ob = await exchange.fetch_order_book(exchange_symbol, limit=limit)
        return {
            "symbol": symbol,
            "bids": [[float(p), float(q)] for p, q in (ob.get("bids") or [])[:limit]],
            "asks": [[float(p), float(q)] for p, q in (ob.get("asks") or [])[:limit]],
            "timestamp": ob.get("timestamp"),
        }
    finally:
        await exchange.close()


async def start_orderbook_streamer() -> None:
    """Start the background order book streaming task."""
    global _task
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_stream_loop())
    logger.info("orderbook_streamer.task_created")


async def stop_orderbook_streamer() -> None:
    """Stop the background order book streaming task."""
    global _running, _task
    _running = False
    if _task:
        _task.cancel()
        try:
            await _task
        except (asyncio.CancelledError, Exception):
            pass
        _task = None
    logger.info("orderbook_streamer.task_stopped")
