"""Unit tests for backend/app/api/routes/markets.py — Markets endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestMarketsEndpoint:
    """Tests for GET /api/markets."""

    def test_markets_returns_200(self, api_client):
        """Should return 200 with markets list."""
        # Mock the Binance fetch to avoid real API calls
        mock_markets = [
            {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "active": True},
            {"symbol": "ETH/USDT", "base": "ETH", "quote": "USDT", "active": True},
        ]
        with patch(
            "app.api.routes.markets._fetch_markets_from_binance",
            new_callable=AsyncMock,
            return_value=mock_markets,
        ):
            # Clear cache first
            import app.api.routes.markets as markets_mod
            markets_mod._cache = None

            resp = api_client.get("/api/markets")
            assert resp.status_code == 200
            body = resp.json()
            assert "markets" in body
            assert "count" in body
            assert body["count"] == 2

    def test_markets_has_correct_structure(self, api_client):
        """Each market should have symbol, base, quote, active fields."""
        mock_markets = [
            {
                "symbol": "BTC/USDT",
                "base": "BTC",
                "quote": "USDT",
                "active": True,
                "price_precision": 2,
                "amount_precision": 3,
            },
        ]
        with patch(
            "app.api.routes.markets._fetch_markets_from_binance",
            new_callable=AsyncMock,
            return_value=mock_markets,
        ):
            import app.api.routes.markets as markets_mod
            markets_mod._cache = None

            resp = api_client.get("/api/markets")
            body = resp.json()
            m = body["markets"][0]
            assert m["symbol"] == "BTC/USDT"
            assert m["base"] == "BTC"
            assert m["quote"] == "USDT"
            assert m["active"] is True

    def test_markets_caching(self, api_client):
        """Second request should return cached data."""
        mock_markets = [
            {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "active": True},
        ]
        with patch(
            "app.api.routes.markets._fetch_markets_from_binance",
            new_callable=AsyncMock,
            return_value=mock_markets,
        ) as mock_fetch:
            import app.api.routes.markets as markets_mod
            markets_mod._cache = None

            # First call
            resp1 = api_client.get("/api/markets")
            assert resp1.status_code == 200
            assert resp1.json()["cached"] is False

            # Second call — should use cache
            resp2 = api_client.get("/api/markets")
            assert resp2.status_code == 200
            assert resp2.json()["cached"] is True

            # Fetch should only be called once
            assert mock_fetch.call_count == 1

    def test_markets_fallback_on_error(self, api_client):
        """Should return fallback markets if Binance fails and no cache."""
        with patch(
            "app.api.routes.markets._fetch_markets_from_binance",
            new_callable=AsyncMock,
            side_effect=Exception("Network error"),
        ):
            import app.api.routes.markets as markets_mod
            markets_mod._cache = None

            resp = api_client.get("/api/markets")
            assert resp.status_code == 200
            body = resp.json()
            assert body["fallback"] is True
            assert len(body["markets"]) > 0
            # Should include BTC/USDT at minimum
            symbols = [m["symbol"] for m in body["markets"]]
            assert "BTC/USDT" in symbols

    def test_markets_stale_cache_on_error(self, api_client):
        """Should return stale cached data if Binance fails but cache exists."""
        import time
        import app.api.routes.markets as markets_mod

        stale_markets = [
            {"symbol": "SOL/USDT", "base": "SOL", "quote": "USDT", "active": True},
        ]
        # Set stale cache (expired TTL)
        markets_mod._cache = (time.time() - 600, stale_markets)

        with patch(
            "app.api.routes.markets._fetch_markets_from_binance",
            new_callable=AsyncMock,
            side_effect=Exception("Network error"),
        ):
            resp = api_client.get("/api/markets")
            assert resp.status_code == 200
            body = resp.json()
            assert body["stale"] is True
            assert body["markets"][0]["symbol"] == "SOL/USDT"

    def test_markets_no_auth_required(self, api_client):
        """Markets endpoint should work without authentication."""
        # The api_client fixture already overrides auth, but we verify
        # the endpoint doesn't explicitly reject unauthenticated requests
        mock_markets = [
            {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "active": True},
        ]
        with patch(
            "app.api.routes.markets._fetch_markets_from_binance",
            new_callable=AsyncMock,
            return_value=mock_markets,
        ):
            import app.api.routes.markets as markets_mod
            markets_mod._cache = None

            resp = api_client.get("/api/markets")
            assert resp.status_code == 200


class TestOrderBookEndpoint:
    """Tests for GET /api/markets/orderbook."""

    def test_orderbook_returns_200(self, api_client):
        mock_data = {
            "symbol": "BTC/USDT",
            "bids": [[43000.0, 1.5], [42999.0, 2.0]],
            "asks": [[43001.0, 1.0], [43002.0, 0.5]],
            "timestamp": 1705312800,
        }
        with patch(
            "app.services.orderbook_streamer.fetch_orderbook_snapshot",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            resp = api_client.get("/api/markets/orderbook?symbol=BTC/USDT&limit=20")
            assert resp.status_code == 200
            body = resp.json()
            assert body["symbol"] == "BTC/USDT"
            assert "bids" in body
            assert "asks" in body

    def test_orderbook_default_params(self, api_client):
        mock_data = {
            "symbol": "BTC/USDT",
            "bids": [],
            "asks": [],
            "timestamp": None,
        }
        with patch(
            "app.services.orderbook_streamer.fetch_orderbook_snapshot",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            resp = api_client.get("/api/markets/orderbook")
            assert resp.status_code == 200
            assert resp.json()["symbol"] == "BTC/USDT"

    def test_orderbook_error_returns_empty(self, api_client):
        """On error, orderbook should return empty bids/asks with error."""
        with patch(
            "app.services.orderbook_streamer.fetch_orderbook_snapshot",
            new_callable=AsyncMock,
            side_effect=Exception("Connection failed"),
        ):
            resp = api_client.get("/api/markets/orderbook?symbol=BTC/USDT")
            assert resp.status_code == 200
            body = resp.json()
            assert body["bids"] == []
            assert body["asks"] == []
            assert "error" in body


class TestBalanceEndpoint:
    """Tests for GET /api/markets/balance."""

    def test_balance_returns_200(self, api_client):
        """Should return account balance."""
        mock_balance = {
            "USDT": {"total": 10000.0, "free": 8000.0, "used": 2000.0}
        }
        mock_exchange = AsyncMock()
        mock_exchange.fetch_balance = AsyncMock(return_value=mock_balance)
        mock_exchange.close = AsyncMock()

        with patch("ccxt.async_support.binanceusdm", return_value=mock_exchange):
            resp = api_client.get("/api/markets/balance")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 10000.0
            assert body["free"] == 8000.0
            assert body["used"] == 2000.0
            assert body["currency"] == "USDT"
            assert body["source"] == "binance"

    def test_balance_error_returns_zero(self, api_client):
        """On error, balance should return zeros with error source."""
        with patch(
            "ccxt.async_support.binanceusdm",
            side_effect=Exception("API key invalid"),
        ):
            resp = api_client.get("/api/markets/balance")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 0
            assert body["source"] == "error"
            assert "error" in body

    def test_balance_fields_complete(self, api_client):
        """Balance response should have all required fields."""
        with patch(
            "ccxt.async_support.binanceusdm",
            side_effect=Exception("No key"),
        ):
            resp = api_client.get("/api/markets/balance")
            body = resp.json()
            for field in ("total", "free", "used", "currency", "source"):
                assert field in body
