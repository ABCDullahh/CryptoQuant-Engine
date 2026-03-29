"""Unit tests for BaseExchangeProvider (abstract base class)."""

from __future__ import annotations

import pytest

from app.config.constants import Exchange
from app.data.providers.base import BaseExchangeProvider


class ConcreteProvider(BaseExchangeProvider):
    """Minimal concrete subclass used to test the abstract base."""

    async def connect(self) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False

    async def watch_ohlcv(self, symbol: str, timeframe: str) -> list[list]:
        return []

    async def watch_order_book(self, symbol: str, limit: int = 20) -> dict:
        return {}

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: int | None = None,
        limit: int = 500,
    ) -> list[list]:
        return []

    async def fetch_funding_rate(self, symbol: str) -> dict:
        return {}

    async def fetch_ticker(self, symbol: str) -> dict:
        return {}


class TestBaseExchangeProvider:
    """Tests for the abstract BaseExchangeProvider."""

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            BaseExchangeProvider(Exchange.BINANCE)

    def test_concrete_subclass_can_be_created(self):
        provider = ConcreteProvider(Exchange.BINANCE)
        assert provider.exchange == Exchange.BINANCE
        assert provider._connected is False
        assert provider.is_connected is False

    def test_is_connected_property(self):
        provider = ConcreteProvider(Exchange.BINANCE)
        assert provider.is_connected is False
        provider._connected = True
        assert provider.is_connected is True

    async def test_concrete_connect_sets_connected(self):
        provider = ConcreteProvider(Exchange.BINANCE)
        await provider.connect()
        assert provider.is_connected is True

    async def test_concrete_close_clears_connected(self):
        provider = ConcreteProvider(Exchange.BINANCE)
        await provider.connect()
        await provider.close()
        assert provider.is_connected is False
