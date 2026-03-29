"""Abstract base class for exchange data providers."""

from __future__ import annotations

import abc

from app.config.constants import Exchange


class BaseExchangeProvider(abc.ABC):
    """Abstract interface for exchange data providers."""

    def __init__(self, exchange: Exchange) -> None:
        self.exchange = exchange
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abc.abstractmethod
    async def connect(self) -> None:
        """Connect to the exchange (load markets etc.)."""
        ...

    @abc.abstractmethod
    async def close(self) -> None:
        """Close all connections."""
        ...

    @abc.abstractmethod
    async def watch_ohlcv(self, symbol: str, timeframe: str) -> list[list]:
        """Stream OHLCV candles via WebSocket. Returns raw CCXT format: [[ts, o, h, l, c, v], ...]"""
        ...

    @abc.abstractmethod
    async def watch_order_book(self, symbol: str, limit: int = 20) -> dict:
        """Stream order book via WebSocket. Returns raw CCXT format."""
        ...

    @abc.abstractmethod
    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, since: int | None = None, limit: int = 500
    ) -> list[list]:
        """Fetch historical OHLCV via REST. Returns raw CCXT format."""
        ...

    @abc.abstractmethod
    async def fetch_funding_rate(self, symbol: str) -> dict:
        """Fetch current funding rate. Returns raw CCXT format."""
        ...

    @abc.abstractmethod
    async def fetch_ticker(self, symbol: str) -> dict:
        """Fetch current ticker. Returns raw CCXT format."""
        ...

    # ── Order execution methods ──────────────────────────────────

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None = None,
        params: dict | None = None,
    ) -> dict:
        """Place an order. Returns raw CCXT order structure."""
        raise NotImplementedError("create_order not supported by this provider")

    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        """Cancel an order by ID."""
        raise NotImplementedError("cancel_order not supported by this provider")

    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        """Set leverage for a symbol."""
        raise NotImplementedError("set_leverage not supported by this provider")

    async def fetch_balance(self) -> dict:
        """Fetch account balance."""
        raise NotImplementedError("fetch_balance not supported by this provider")

    async def fetch_order(self, order_id: str, symbol: str) -> dict:
        """Fetch order details by ID."""
        raise NotImplementedError("fetch_order not supported by this provider")
