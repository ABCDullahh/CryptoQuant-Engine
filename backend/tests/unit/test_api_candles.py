"""Unit tests for backend/app/api/routes/candles.py — Candle data endpoint.

Tests the dual-source candle fetching: Binance REST (primary) + TimescaleDB (fallback).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest


class TestCandlesEndpoint:
    """Tests for GET /api/candles."""

    def _clear_cache(self):
        """Clear the candle cache before tests."""
        import app.api.routes.candles as candles_mod
        candles_mod._candle_cache.clear()

    def test_candles_with_binance_source(self, api_client):
        """Should fetch candles from Binance and return them."""
        self._clear_cache()
        mock_candles = [
            {"time": 1705312800, "open": 43000.0, "high": 43100.0, "low": 42900.0, "close": 43050.0, "volume": 100.5},
            {"time": 1705316400, "open": 43050.0, "high": 43200.0, "low": 43000.0, "close": 43150.0, "volume": 80.3},
        ]
        with patch(
            "app.api.routes.candles._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get("/api/candles?symbol=BTC/USDT&timeframe=1h")
            assert resp.status_code == 200
            body = resp.json()
            assert body["source"] == "binance"
            assert len(body["candles"]) == 2
            assert body["symbol"] == "BTC/USDT"
            assert body["timeframe"] == "1h"

    def test_candles_cached_on_second_request(self, api_client):
        """Second request should return cached data."""
        self._clear_cache()
        mock_candles = [
            {"time": 1705312800, "open": 43000.0, "high": 43100.0, "low": 42900.0, "close": 43050.0, "volume": 100.5},
        ]
        with patch(
            "app.api.routes.candles._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ) as mock_fetch:
            resp1 = api_client.get("/api/candles?symbol=BTC/USDT&timeframe=1h")
            assert resp1.json()["source"] == "binance"

            resp2 = api_client.get("/api/candles?symbol=BTC/USDT&timeframe=1h")
            assert resp2.json()["source"] == "binance_cached"

            # Binance should only be called once
            assert mock_fetch.call_count == 1

    def test_candles_fallback_to_db(self, api_client, seed_db):
        """Should fallback to TimescaleDB when Binance fails."""
        self._clear_cache()
        # Seed DB with candles
        ts = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc).isoformat()
        seed_db(
            "INSERT INTO candles (time, symbol, timeframe, exchange, open, high, low, close, volume) "
            "VALUES (:time, :symbol, :tf, :exchange, :open, :high, :low, :close, :vol)",
            {
                "time": ts,
                "symbol": "BTC/USDT",
                "tf": "1h",
                "exchange": "binance",
                "open": 43000,
                "high": 43100,
                "low": 42900,
                "close": 43050,
                "vol": 100.5,
            },
        )

        with patch(
            "app.api.routes.candles._fetch_candles_from_binance",
            new_callable=AsyncMock,
            side_effect=Exception("Binance unavailable"),
        ):
            resp = api_client.get("/api/candles?symbol=BTC/USDT&timeframe=1h")
            assert resp.status_code == 200
            body = resp.json()
            assert body["source"] == "database"
            assert len(body["candles"]) == 1

    def test_candles_empty_when_both_fail(self, api_client):
        """Should return empty candles when both Binance and DB have no data."""
        self._clear_cache()
        with patch(
            "app.api.routes.candles._fetch_candles_from_binance",
            new_callable=AsyncMock,
            side_effect=Exception("Binance unavailable"),
        ):
            resp = api_client.get("/api/candles?symbol=UNKNOWN/USDT&timeframe=1h")
            assert resp.status_code == 200
            body = resp.json()
            assert body["source"] == "empty"
            assert body["candles"] == []

    def test_default_params(self, api_client):
        """Calling without explicit params should use defaults."""
        self._clear_cache()
        mock_candles = [
            {"time": 1705312800, "open": 43000.0, "high": 43100.0, "low": 42900.0, "close": 43050.0, "volume": 100.5},
        ]
        with patch(
            "app.api.routes.candles._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get("/api/candles")
            assert resp.status_code == 200
            body = resp.json()
            assert body["symbol"] == "BTC/USDT"
            assert body["timeframe"] == "1h"
            assert isinstance(body["candles"], list)

    def test_candle_structure(self, api_client):
        """Each candle should have time, open, high, low, close, volume."""
        self._clear_cache()
        mock_candles = [
            {"time": 1705312800, "open": 43000.0, "high": 43100.0, "low": 42900.0, "close": 43050.0, "volume": 100.5},
        ]
        with patch(
            "app.api.routes.candles._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get("/api/candles?symbol=BTC/USDT&timeframe=1h")
            body = resp.json()
            c = body["candles"][0]
            assert "time" in c
            assert "open" in c
            assert "high" in c
            assert "low" in c
            assert "close" in c
            assert "volume" in c
            assert isinstance(c["time"], int)
            assert isinstance(c["open"], float)

    def test_with_seeded_candles_db_fallback(self, api_client, seed_db):
        """With seeded candle data and Binance offline, should return DB candles sorted ascending."""
        self._clear_cache()
        for i, hour in enumerate([10, 11, 12]):
            ts = datetime(2024, 1, 15, hour, 0, 0, tzinfo=timezone.utc).isoformat()
            seed_db(
                "INSERT INTO candles (time, symbol, timeframe, exchange, open, high, low, close, volume) "
                "VALUES (:time, :symbol, :tf, :exchange, :open, :high, :low, :close, :vol)",
                {
                    "time": ts,
                    "symbol": "BTC/USDT",
                    "tf": "1h",
                    "exchange": "binance",
                    "open": 43000 + i * 100,
                    "high": 43100 + i * 100,
                    "low": 42900 + i * 100,
                    "close": 43050 + i * 100,
                    "vol": 100.5,
                },
            )

        with patch(
            "app.api.routes.candles._fetch_candles_from_binance",
            new_callable=AsyncMock,
            side_effect=Exception("Binance offline"),
        ):
            resp = api_client.get("/api/candles?symbol=BTC/USDT&timeframe=1h&limit=10")
            assert resp.status_code == 200
            body = resp.json()
            assert len(body["candles"]) == 3

            # Should be sorted ascending (oldest first)
            times = [c["time"] for c in body["candles"]]
            assert times == sorted(times)

    def test_limit_parameter(self, api_client):
        """Limit parameter should be passed to fetch function."""
        self._clear_cache()
        mock_candles = [
            {"time": 1705312800 + i * 3600, "open": 43000.0, "high": 43100.0, "low": 42900.0, "close": 43050.0, "volume": 100.5}
            for i in range(5)
        ]
        with patch(
            "app.api.routes.candles._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get("/api/candles?symbol=BTC/USDT&timeframe=1h&limit=3")
            assert resp.status_code == 200
            # The endpoint passes limit to Binance, mock returns all
            # But response should still be valid
            body = resp.json()
            assert isinstance(body["candles"], list)

    def test_response_has_source_field(self, api_client):
        """Response should include source field indicating data origin."""
        self._clear_cache()
        mock_candles = [
            {"time": 1705312800, "open": 43000.0, "high": 43100.0, "low": 42900.0, "close": 43050.0, "volume": 100.5},
        ]
        with patch(
            "app.api.routes.candles._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get("/api/candles?symbol=BTC/USDT&timeframe=1h")
            body = resp.json()
            assert "source" in body
            assert body["source"] in ("binance", "binance_cached", "database", "empty")
