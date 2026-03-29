"""Unit tests for BinanceProvider - init, connect, close, ensure_connected."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config.constants import Exchange
from app.core.exceptions import ExchangeConnectionError
from app.data.providers.binance import BinanceProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_exchange() -> AsyncMock:
    mock_exchange = AsyncMock()
    mock_exchange.load_markets = AsyncMock()
    mock_exchange.close = AsyncMock()
    mock_exchange.markets = {"BTC/USDT": {}, "ETH/USDT": {}}
    mock_exchange.markets_by_id = {}
    mock_exchange.set_sandbox_mode = MagicMock()
    mock_exchange.enable_demo_trading = MagicMock()
    return mock_exchange


def _patch_ccxt(mock_ws_exchange: AsyncMock, mock_rest_exchange: AsyncMock | None = None):
    """Mock both ccxt.pro (WebSocket) and ccxt.async_support (REST).

    If mock_rest_exchange is not provided, creates a separate one.
    Returns (context_manager, mock_pro_module, mock_rest_module, rest_exchange).
    """
    if mock_rest_exchange is None:
        mock_rest_exchange = _make_mock_exchange()

    mock_pro = MagicMock()
    mock_pro.binanceusdm = MagicMock(return_value=mock_ws_exchange)

    mock_rest = MagicMock()
    mock_rest.binanceusdm = MagicMock(return_value=mock_rest_exchange)

    mock_ccxt = MagicMock()
    mock_ccxt.pro = mock_pro
    mock_ccxt.async_support = mock_rest

    modules = {
        "ccxt": mock_ccxt,
        "ccxt.pro": mock_pro,
        "ccxt.async_support": mock_rest,
    }
    return patch.dict("sys.modules", modules), mock_pro, mock_rest, mock_rest_exchange


# ---------------------------------------------------------------------------
# BinanceProvider.__init__
# ---------------------------------------------------------------------------


class TestBinanceProviderInit:
    def test_init_sets_exchange(self):
        provider = BinanceProvider()
        assert provider.exchange == Exchange.BINANCE

    def test_init_not_connected(self):
        provider = BinanceProvider()
        assert provider._connected is False
        assert provider.is_connected is False

    def test_init_exchange_is_none(self):
        provider = BinanceProvider()
        assert provider._exchange is None


# ---------------------------------------------------------------------------
# BinanceProvider.connect
# ---------------------------------------------------------------------------


class TestBinanceProviderConnect:
    async def test_connect_creates_exchange_and_loads_markets(self, monkeypatch):
        mock_ws = _make_mock_exchange()
        mock_rest = _make_mock_exchange()
        ctx, mock_pro, mock_rest_mod, _ = _patch_ccxt(mock_ws, mock_rest)

        monkeypatch.setenv("BINANCE_API_KEY", "test-key")
        monkeypatch.setenv("BINANCE_SECRET", "test-secret")
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()

        # Both modules should create an exchange instance
        mock_pro.binanceusdm.assert_called_once()
        mock_rest_mod.binanceusdm.assert_called_once()

        config_arg = mock_rest_mod.binanceusdm.call_args[0][0]
        assert config_arg["apiKey"] == "test-key"
        assert config_arg["secret"] == "test-secret"
        assert config_arg["enableRateLimit"] is True

        # load_markets is called on the REST instance only
        mock_rest.load_markets.assert_awaited_once()
        assert provider._connected is True
        assert provider.is_connected is True
        assert provider._exchange is mock_ws
        assert provider._rest_exchange is mock_rest

    async def test_connect_testnet_enables_demo_trading(self, monkeypatch):
        mock_ws = _make_mock_exchange()
        mock_rest = _make_mock_exchange()
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest)

        monkeypatch.setenv("BINANCE_API_KEY", "")
        monkeypatch.setenv("BINANCE_SECRET", "")
        monkeypatch.setenv("BINANCE_TESTNET", "true")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()

        # Both instances should have demo trading enabled
        mock_ws.enable_demo_trading.assert_called_once_with(True)
        mock_rest.enable_demo_trading.assert_called_once_with(True)

    async def test_connect_no_testnet_does_not_enable_demo(self, monkeypatch):
        mock_ws = _make_mock_exchange()
        mock_rest = _make_mock_exchange()
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()

        mock_ws.enable_demo_trading.assert_not_called()
        mock_rest.enable_demo_trading.assert_not_called()

    async def test_connect_without_api_keys(self, monkeypatch):
        mock_ws = _make_mock_exchange()
        mock_rest = _make_mock_exchange()
        ctx, _, mock_rest_mod, _ = _patch_ccxt(mock_ws, mock_rest)

        monkeypatch.setenv("BINANCE_API_KEY", "")
        monkeypatch.setenv("BINANCE_SECRET", "")
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()

        config_arg = mock_rest_mod.binanceusdm.call_args[0][0]
        assert "apiKey" not in config_arg
        assert "secret" not in config_arg
        assert provider._connected is True

    async def test_connect_failure_raises_exchange_connection_error(self, monkeypatch):
        mock_ws = _make_mock_exchange()
        mock_rest = _make_mock_exchange()
        mock_rest.load_markets = AsyncMock(side_effect=Exception("network down"))
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            with pytest.raises(ExchangeConnectionError, match="Failed to connect to Binance"):
                await provider.connect()

        assert provider._connected is False
        assert provider._exchange is None
        assert provider._rest_exchange is None

    async def test_connect_skips_if_already_connected(self, monkeypatch):
        mock_ws = _make_mock_exchange()
        mock_rest = _make_mock_exchange()
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()
            await provider.connect()

        mock_rest.load_markets.assert_awaited_once()


# ---------------------------------------------------------------------------
# BinanceProvider.close / _safe_close
# ---------------------------------------------------------------------------


class TestBinanceProviderClose:
    async def test_close_calls_safe_close_and_disconnects(self, monkeypatch):
        mock_ws = _make_mock_exchange()
        mock_rest = _make_mock_exchange()
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()
            await provider.close()

        mock_ws.close.assert_awaited_once()
        mock_rest.close.assert_awaited_once()
        assert provider._connected is False
        assert provider._exchange is None
        assert provider._rest_exchange is None

    async def test_safe_close_ignores_errors(self, monkeypatch):
        mock_ws = _make_mock_exchange()
        mock_rest = _make_mock_exchange()
        mock_ws.close = AsyncMock(side_effect=RuntimeError("oops"))
        mock_rest.close = AsyncMock(side_effect=RuntimeError("oops"))
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()
            await provider._safe_close()

        assert provider._exchange is None
        assert provider._rest_exchange is None

    async def test_safe_close_noop_when_exchange_is_none(self):
        provider = BinanceProvider()
        await provider._safe_close()
        assert provider._exchange is None
        assert provider._rest_exchange is None

    async def test_close_when_not_connected(self):
        provider = BinanceProvider()
        await provider.close()
        assert provider._connected is False


# ---------------------------------------------------------------------------
# BinanceProvider._ensure_connected
# ---------------------------------------------------------------------------


class TestBinanceProviderEnsureConnected:
    async def test_ensure_connected_calls_connect_when_disconnected(self, monkeypatch):
        mock_ws = _make_mock_exchange()
        mock_rest = _make_mock_exchange()
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider._ensure_connected()

        assert provider._connected is True
        mock_rest.load_markets.assert_awaited_once()

    async def test_ensure_connected_skips_when_connected(self, monkeypatch):
        mock_ws = _make_mock_exchange()
        mock_rest = _make_mock_exchange()
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()
            mock_rest.load_markets.reset_mock()
            await provider._ensure_connected()

        mock_rest.load_markets.assert_not_awaited()

    async def test_ensure_connected_reconnects_when_rest_exchange_none(self, monkeypatch):
        mock_ws = _make_mock_exchange()
        mock_rest = _make_mock_exchange()
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()
            provider._rest_exchange = None
            mock_rest.load_markets.reset_mock()
            await provider._ensure_connected()

        # Should reconnect since _rest_exchange is None
        mock_rest.load_markets.assert_awaited_once()

    async def test_ensure_connected_full_reconnect_after_close(self, monkeypatch):
        mock_ws = _make_mock_exchange()
        mock_rest = _make_mock_exchange()
        ctx, _, _, _ = _patch_ccxt(mock_ws, mock_rest)
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        provider = BinanceProvider()
        with ctx:
            await provider.connect()
            await provider.close()
            assert provider._connected is False
            assert provider._exchange is None
            assert provider._rest_exchange is None

            mock_rest.load_markets.reset_mock()
            await provider._ensure_connected()

        assert provider._connected is True
        mock_rest.load_markets.assert_awaited_once()
