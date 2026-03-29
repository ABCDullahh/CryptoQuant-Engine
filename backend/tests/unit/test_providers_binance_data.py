"""Unit tests for BinanceProvider - data methods and error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    AuthenticationError,
    ExchangeConnectionError,
    RateLimitError,
)
from app.data.providers.binance import BinanceProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_exchange(for_ws: bool = False) -> AsyncMock:
    """Create a mock CCXT exchange instance.

    Args:
        for_ws: If True, includes WebSocket methods (watch_*).
                If False, includes REST methods (fetch_*).
    """
    mock_exchange = AsyncMock()
    mock_exchange.load_markets = AsyncMock()
    mock_exchange.close = AsyncMock()
    mock_exchange.markets = {"BTC/USDT": {}, "ETH/USDT": {}}
    mock_exchange.markets_by_id = {}
    mock_exchange.set_sandbox_mode = MagicMock()
    mock_exchange.enable_demo_trading = MagicMock()

    if for_ws:
        mock_exchange.watch_ohlcv = AsyncMock(return_value=[[1, 2, 3, 4, 5, 6]])
        mock_exchange.watch_order_book = AsyncMock(
            return_value={"bids": [[100, 1]], "asks": [[101, 1]]}
        )

    # REST methods on both (REST exchange uses them, WS may need stubs)
    mock_exchange.fetch_ohlcv = AsyncMock(return_value=[[1, 2, 3, 4, 5, 6]])
    mock_exchange.fetch_funding_rate = AsyncMock(return_value={"fundingRate": 0.0001})
    mock_exchange.fetch_ticker = AsyncMock(return_value={"last": 43000.0})
    return mock_exchange


def _make_mock_ccxt_errors() -> MagicMock:
    mock = MagicMock()

    class _CcxtAuthenticationError(Exception):
        pass

    class _CcxtRateLimitExceeded(Exception):
        pass

    class _CcxtDDoSProtection(Exception):
        pass

    class _CcxtNetworkError(Exception):
        pass

    mock.AuthenticationError = _CcxtAuthenticationError
    mock.RateLimitExceeded = _CcxtRateLimitExceeded
    mock.DDoSProtection = _CcxtDDoSProtection
    mock.NetworkError = _CcxtNetworkError
    return mock


def _patch_ccxt(
    mock_ws_exchange: AsyncMock,
    mock_rest_exchange: AsyncMock | None = None,
    mock_ccxt_errors: MagicMock | None = None,
):
    """Mock ccxt.pro (WS) and ccxt.async_support (REST)."""
    if mock_rest_exchange is None:
        mock_rest_exchange = _make_mock_exchange()

    mock_pro = MagicMock()
    mock_pro.binanceusdm = MagicMock(return_value=mock_ws_exchange)

    mock_rest = MagicMock()
    mock_rest.binanceusdm = MagicMock(return_value=mock_rest_exchange)

    if mock_ccxt_errors is None:
        mock_ccxt_errors = _make_mock_ccxt_errors()

    mock_ccxt_errors.pro = mock_pro
    mock_ccxt_errors.async_support = mock_rest

    modules = {
        "ccxt": mock_ccxt_errors,
        "ccxt.pro": mock_pro,
        "ccxt.async_support": mock_rest,
    }
    return patch.dict("sys.modules", modules), mock_pro, mock_rest, mock_ccxt_errors


# ---------------------------------------------------------------------------
# BinanceProvider data methods
# ---------------------------------------------------------------------------


class TestBinanceProviderDataMethods:
    @pytest.fixture
    async def connected_provider(self, monkeypatch):
        mock_ws = _make_mock_exchange(for_ws=True)
        mock_rest = _make_mock_exchange()
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()
            yield provider, mock_ws, mock_rest

    async def test_watch_ohlcv(self, connected_provider):
        provider, mock_ws, _ = connected_provider
        result = await provider.watch_ohlcv("BTC/USDT", "1h")
        mock_ws.watch_ohlcv.assert_awaited_once_with("BTC/USDT", "1h")
        assert result == [[1, 2, 3, 4, 5, 6]]

    async def test_watch_order_book(self, connected_provider):
        provider, mock_ws, _ = connected_provider
        result = await provider.watch_order_book("BTC/USDT", limit=10)
        mock_ws.watch_order_book.assert_awaited_once_with("BTC/USDT", 10)
        assert "bids" in result
        assert "asks" in result

    async def test_fetch_ohlcv_default_params(self, connected_provider):
        provider, _, mock_rest = connected_provider
        result = await provider.fetch_ohlcv("ETH/USDT", "15m")
        mock_rest.fetch_ohlcv.assert_awaited_once_with(
            "ETH/USDT", "15m", since=None, limit=500
        )
        assert result == [[1, 2, 3, 4, 5, 6]]

    async def test_fetch_ohlcv_with_since_and_limit(self, connected_provider):
        provider, _, mock_rest = connected_provider
        await provider.fetch_ohlcv("BTC/USDT", "1h", since=1000000, limit=100)
        mock_rest.fetch_ohlcv.assert_awaited_once_with(
            "BTC/USDT", "1h", since=1000000, limit=100
        )

    async def test_fetch_funding_rate(self, connected_provider):
        provider, _, mock_rest = connected_provider
        result = await provider.fetch_funding_rate("BTC/USDT")
        mock_rest.fetch_funding_rate.assert_awaited_once_with("BTC/USDT")
        assert result == {"fundingRate": 0.0001}

    async def test_fetch_ticker(self, connected_provider):
        provider, _, mock_rest = connected_provider
        result = await provider.fetch_ticker("BTC/USDT")
        mock_rest.fetch_ticker.assert_awaited_once_with("BTC/USDT")
        assert result == {"last": 43000.0}

    async def test_data_method_calls_ensure_connected(self, monkeypatch):
        mock_ws = _make_mock_exchange(for_ws=True)
        mock_rest = _make_mock_exchange()
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        assert provider._connected is False

        with ctx:
            result = await provider.fetch_ticker("BTC/USDT")

        assert provider._connected is True
        mock_rest.load_markets.assert_awaited_once()
        assert result == {"last": 43000.0}


# ---------------------------------------------------------------------------
# BinanceProvider._handle_exchange_error
# ---------------------------------------------------------------------------


class TestBinanceProviderHandleExchangeError:
    @pytest.fixture
    def mock_ccxt(self):
        return _make_mock_ccxt_errors()

    def test_auth_error_maps_to_authentication_error(self, mock_ccxt):
        provider = BinanceProvider()
        error = mock_ccxt.AuthenticationError("invalid key")

        with patch.dict("sys.modules", {"ccxt": mock_ccxt}):
            with pytest.raises(AuthenticationError, match="Binance auth failed"):
                provider._handle_exchange_error(error, "fetch_ticker", symbol="BTC/USDT")

    def test_rate_limit_maps_to_rate_limit_error(self, mock_ccxt):
        provider = BinanceProvider()
        error = mock_ccxt.RateLimitExceeded("too fast")

        with patch.dict("sys.modules", {"ccxt": mock_ccxt}):
            with pytest.raises(RateLimitError, match="Binance rate limit"):
                provider._handle_exchange_error(error, "fetch_ohlcv", symbol="BTC/USDT")

    def test_ddos_protection_maps_to_rate_limit_error(self, mock_ccxt):
        provider = BinanceProvider()
        error = mock_ccxt.DDoSProtection("banned")

        with patch.dict("sys.modules", {"ccxt": mock_ccxt}):
            with pytest.raises(RateLimitError, match="Binance rate limit"):
                provider._handle_exchange_error(error, "fetch_ohlcv", symbol="ETH/USDT")

    def test_network_error_maps_to_exchange_connection_error(self, mock_ccxt):
        provider = BinanceProvider()
        error = mock_ccxt.NetworkError("timeout")

        with patch.dict("sys.modules", {"ccxt": mock_ccxt}):
            with pytest.raises(ExchangeConnectionError, match="Binance network error"):
                provider._handle_exchange_error(error, "watch_ohlcv", symbol="BTC/USDT")

    def test_unknown_error_maps_to_exchange_connection_error(self, mock_ccxt):
        provider = BinanceProvider()
        error = RuntimeError("something unexpected")

        with patch.dict("sys.modules", {"ccxt": mock_ccxt}):
            with pytest.raises(ExchangeConnectionError, match="Binance error in fetch_ticker"):
                provider._handle_exchange_error(error, "fetch_ticker", symbol="BTC/USDT")

    def test_error_chaining(self, mock_ccxt):
        provider = BinanceProvider()
        original = mock_ccxt.AuthenticationError("bad key")

        with patch.dict("sys.modules", {"ccxt": mock_ccxt}):
            with pytest.raises(AuthenticationError) as exc_info:
                provider._handle_exchange_error(original, "fetch_ticker")

        assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# BinanceProvider data methods -- error propagation
# ---------------------------------------------------------------------------


class TestBinanceProviderDataMethodErrors:
    @pytest.fixture
    def mock_ccxt(self):
        return _make_mock_ccxt_errors()

    async def test_watch_ohlcv_auth_error(self, monkeypatch, mock_ccxt):
        mock_ws = _make_mock_exchange(for_ws=True)
        auth_err = mock_ccxt.AuthenticationError("invalid api key")
        mock_ws.watch_ohlcv = AsyncMock(side_effect=auth_err)
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_ccxt_errors=mock_ccxt)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()
            with pytest.raises(AuthenticationError):
                await provider.watch_ohlcv("BTC/USDT", "1h")

    async def test_fetch_ohlcv_rate_limit_error(self, monkeypatch, mock_ccxt):
        mock_ws = _make_mock_exchange(for_ws=True)
        mock_rest = _make_mock_exchange()
        mock_rest.fetch_ohlcv = AsyncMock(
            side_effect=mock_ccxt.RateLimitExceeded("slow down")
        )
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest, mock_ccxt)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()
            with pytest.raises(RateLimitError):
                await provider.fetch_ohlcv("BTC/USDT", "1h")

    async def test_fetch_ticker_network_error(self, monkeypatch, mock_ccxt):
        mock_ws = _make_mock_exchange(for_ws=True)
        mock_rest = _make_mock_exchange()
        mock_rest.fetch_ticker = AsyncMock(
            side_effect=mock_ccxt.NetworkError("connection reset")
        )
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest, mock_ccxt)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()
            with pytest.raises(ExchangeConnectionError):
                await provider.fetch_ticker("BTC/USDT")

    async def test_watch_order_book_unknown_error(self, monkeypatch, mock_ccxt):
        mock_ws = _make_mock_exchange(for_ws=True)
        mock_ws.watch_order_book = AsyncMock(
            side_effect=RuntimeError("unexpected")
        )
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_ccxt_errors=mock_ccxt)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()
            with pytest.raises(ExchangeConnectionError, match="Binance error in watch_order_book"):
                await provider.watch_order_book("BTC/USDT")

    async def test_fetch_funding_rate_ddos_protection(self, monkeypatch, mock_ccxt):
        mock_ws = _make_mock_exchange(for_ws=True)
        mock_rest = _make_mock_exchange()
        mock_rest.fetch_funding_rate = AsyncMock(
            side_effect=mock_ccxt.DDoSProtection("cloudflare block")
        )
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest, mock_ccxt)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()
            with pytest.raises(RateLimitError):
                await provider.fetch_funding_rate("BTC/USDT")
