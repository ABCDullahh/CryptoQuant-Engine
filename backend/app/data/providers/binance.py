"""Binance USDM Futures data provider using CCXT 4.x async."""

from __future__ import annotations

import structlog

from app.config.constants import Exchange
from app.config.settings import get_settings
from app.core.exceptions import (
    AuthenticationError,
    ExchangeConnectionError,
    RateLimitError,
)
from app.data.providers.base import BaseExchangeProvider

logger = structlog.get_logger(__name__)


class BinanceProvider(BaseExchangeProvider):
    """Binance USDM Futures provider via CCXT 4.x.

    Uses two exchange instances:
    - _exchange (ccxt.pro): WebSocket streaming (watch_ohlcv, watch_order_book)
    - _rest_exchange (ccxt.async_support): REST operations (create_order, fetch_*, etc.)

    ccxt.pro can return None from REST methods in certain conditions,
    so all trading/REST calls go through the dedicated _rest_exchange.
    """

    def __init__(self) -> None:
        super().__init__(Exchange.BINANCE)
        self._exchange = None
        self._rest_exchange = None

    async def connect(self) -> None:
        """Initialize CCXT binanceusdm with API keys and load markets."""
        if self._connected:
            return

        import ccxt.async_support as ccxt_rest

        try:
            import ccxt.pro as ccxtpro
        except ImportError:
            ccxtpro = ccxt_rest

        settings = get_settings()

        config = {
            "enableRateLimit": True,
            "options": {"defaultType": "future", "recvWindow": 60000},
        }

        if settings.binance_api_key:
            config["apiKey"] = settings.binance_api_key
            config["secret"] = settings.binance_secret

        # WebSocket instance (ccxt.pro) for streaming
        self._exchange = ccxtpro.binanceusdm(config)
        # REST instance (ccxt.async_support) for trading/queries
        self._rest_exchange = ccxt_rest.binanceusdm(config)

        if settings.binance_testnet:
            self._exchange.enable_demo_trading(True)
            self._rest_exchange.enable_demo_trading(True)
            logger.info("binance.demo_trading_enabled")

        try:
            await self._rest_exchange.load_markets()
            # Share loaded markets with the WS instance to avoid double load
            self._exchange.markets = self._rest_exchange.markets
            self._exchange.markets_by_id = self._rest_exchange.markets_by_id
            self._connected = True
            logger.info(
                "binance.connected",
                testnet=settings.binance_testnet,
                markets_count=len(self._rest_exchange.markets),
            )
        except Exception as e:
            await self._safe_close()
            raise ExchangeConnectionError(f"Failed to connect to Binance: {e}") from e

    async def close(self) -> None:
        """Close both CCXT exchange connections."""
        await self._safe_close()
        self._connected = False
        logger.info("binance.disconnected")

    async def _safe_close(self) -> None:
        """Safely close both exchange instances, ignoring errors."""
        for inst_name in ("_exchange", "_rest_exchange"):
            inst = getattr(self, inst_name, None)
            if inst is not None:
                try:
                    await inst.close()
                except Exception as exc:
                    logger.debug("binance.close_failed", instance=inst_name, error=str(exc))
                setattr(self, inst_name, None)

    async def _ensure_connected(self) -> None:
        """Ensure we're connected before making calls."""
        if not self._connected or self._rest_exchange is None:
            self._connected = False  # Reset so connect() doesn't skip
            await self.connect()

    async def watch_ohlcv(self, symbol: str, timeframe: str) -> list[list]:
        """Watch OHLCV candles via WebSocket.

        Returns raw CCXT format: [[timestamp_ms, open, high, low, close, volume], ...]
        """
        await self._ensure_connected()
        try:
            return await self._exchange.watch_ohlcv(symbol, timeframe)
        except Exception as e:
            self._handle_exchange_error(e, "watch_ohlcv", symbol=symbol, timeframe=timeframe)

    async def watch_order_book(self, symbol: str, limit: int = 20) -> dict:
        """Watch order book via WebSocket.

        Returns raw CCXT format: {bids: [[price, amount], ...], asks: [[price, amount], ...], ...}
        """
        await self._ensure_connected()
        try:
            return await self._exchange.watch_order_book(symbol, limit)
        except Exception as e:
            self._handle_exchange_error(e, "watch_order_book", symbol=symbol)

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, since: int | None = None, limit: int = 500
    ) -> list[list]:
        """Fetch historical OHLCV via REST.

        Returns raw CCXT format: [[timestamp_ms, open, high, low, close, volume], ...]
        """
        await self._ensure_connected()
        try:
            return await self._rest_exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        except Exception as e:
            self._handle_exchange_error(e, "fetch_ohlcv", symbol=symbol, timeframe=timeframe)

    async def fetch_funding_rate(self, symbol: str) -> dict:
        """Fetch current funding rate via REST."""
        await self._ensure_connected()
        try:
            return await self._rest_exchange.fetch_funding_rate(symbol)
        except Exception as e:
            self._handle_exchange_error(e, "fetch_funding_rate", symbol=symbol)

    async def fetch_ticker(self, symbol: str) -> dict:
        """Fetch current ticker via REST."""
        await self._ensure_connected()
        try:
            return await self._rest_exchange.fetch_ticker(symbol)
        except Exception as e:
            self._handle_exchange_error(e, "fetch_ticker", symbol=symbol)

    # ── Order execution methods (all use _rest_exchange) ─────────

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None = None,
        params: dict | None = None,
    ) -> dict:
        """Place an order on Binance USDM Futures."""
        await self._ensure_connected()
        try:
            return await self._rest_exchange.create_order(
                symbol, order_type, side, amount, price, params or {}
            )
        except Exception as e:
            self._handle_exchange_error(e, "create_order", symbol=symbol, side=side)

    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        """Cancel an order on Binance."""
        await self._ensure_connected()
        try:
            return await self._rest_exchange.cancel_order(order_id, symbol)
        except Exception as e:
            self._handle_exchange_error(e, "cancel_order", symbol=symbol, order_id=order_id)

    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        """Set leverage for a Binance USDM Futures symbol."""
        await self._ensure_connected()
        try:
            return await self._rest_exchange.set_leverage(leverage, symbol)
        except Exception as e:
            self._handle_exchange_error(e, "set_leverage", symbol=symbol, leverage=leverage)

    async def fetch_balance(self) -> dict:
        """Fetch Binance USDM Futures account balance."""
        await self._ensure_connected()
        try:
            return await self._rest_exchange.fetch_balance()
        except Exception as e:
            self._handle_exchange_error(e, "fetch_balance")

    async def fetch_order(self, order_id: str, symbol: str) -> dict:
        """Fetch order details from Binance."""
        await self._ensure_connected()
        try:
            return await self._rest_exchange.fetch_order(order_id, symbol)
        except Exception as e:
            self._handle_exchange_error(e, "fetch_order", symbol=symbol, order_id=order_id)

    async def fetch_positions(self) -> list[dict]:
        """Fetch open positions from Binance."""
        await self._ensure_connected()
        try:
            return await self._rest_exchange.fetch_positions()
        except Exception as e:
            self._handle_exchange_error(e, "fetch_positions")

    def _normalize_symbol(self, symbol: str) -> str:
        """Ensure symbol has :USDT suffix for CCXT precision methods."""
        if ":USDT" not in symbol and "/USDT" in symbol:
            return f"{symbol}:USDT"
        return symbol

    def amount_to_precision(self, symbol: str, amount: float) -> float:
        """Round amount to exchange precision for a symbol."""
        ex = self._rest_exchange or self._exchange
        if ex is None:
            return amount
        try:
            return float(ex.amount_to_precision(
                self._normalize_symbol(symbol), amount,
            ))
        except Exception:
            return amount

    def price_to_precision(self, symbol: str, price: float) -> float:
        """Round price to exchange precision for a symbol."""
        ex = self._rest_exchange or self._exchange
        if ex is None:
            return price
        try:
            return float(ex.price_to_precision(
                self._normalize_symbol(symbol), price,
            ))
        except Exception:
            return price

    def _handle_exchange_error(self, error: Exception, method: str, **context) -> None:
        """Map CCXT exceptions to our custom exceptions."""
        import ccxt as ccxt_errors

        log_ctx = {"method": method, **context, "error": str(error)}

        if isinstance(error, ccxt_errors.AuthenticationError):
            logger.error("binance.auth_error", **log_ctx)
            raise AuthenticationError(f"Binance auth failed: {error}") from error
        elif isinstance(error, (ccxt_errors.RateLimitExceeded, ccxt_errors.DDoSProtection)):
            logger.warning("binance.rate_limit", **log_ctx)
            raise RateLimitError(f"Binance rate limit: {error}") from error
        elif isinstance(error, ccxt_errors.NetworkError):
            logger.error("binance.network_error", **log_ctx)
            raise ExchangeConnectionError(f"Binance network error: {error}") from error
        else:
            logger.error("binance.exchange_error", **log_ctx)
            raise ExchangeConnectionError(f"Binance error in {method}: {error}") from error
