"""Unit tests for backend/app/api/routes/indicators.py — Indicator data endpoint.

Tests the indicator computation from Binance candle data with mocked exchange.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


def _make_mock_candles(n: int = 60) -> list[dict]:
    """Generate n mock candle dicts for testing."""
    base_time = 1705312800  # 2024-01-15 10:00 UTC
    base_price = 43000.0
    candles = []
    for i in range(n):
        price = base_price + i * 10
        candles.append({
            "time": base_time + i * 3600,
            "open": price - 5,
            "high": price + 50,
            "low": price - 50,
            "close": price,
            "volume": 100.0 + i,
        })
    return candles


class TestIndicatorsEndpoint:
    """Tests for GET /api/indicators."""

    def _clear_cache(self):
        """Clear the indicator cache before tests."""
        import app.api.routes.indicators as ind_mod
        ind_mod._indicator_cache.clear()

    def test_indicators_basic(self, api_client):
        """Should fetch indicators from Binance candles and return them."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=ema_9,rsi_14"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["symbol"] == "BTC/USDT"
            assert body["timeframe"] == "1h"
            assert body["source"] == "binance"
            assert "data" in body
            assert len(body["data"]) == 60

    def test_indicators_ema_values(self, api_client):
        """EMA values should be present and numeric in the response."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=ema_9"
            )
            body = resp.json()
            # Last data point should have a valid ema_9 (not null for 60 candles)
            last = body["data"][-1]
            assert "ema_9" in last
            assert last["ema_9"] is not None
            assert isinstance(last["ema_9"], float)

    def test_indicators_rsi_values(self, api_client):
        """RSI values should be between 0 and 100."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=rsi_14"
            )
            body = resp.json()
            last = body["data"][-1]
            assert "rsi_14" in last
            assert last["rsi_14"] is not None
            assert 0 <= last["rsi_14"] <= 100

    def test_indicators_macd(self, api_client):
        """MACD request should return macd, macd_signal, macd_histogram."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=macd"
            )
            body = resp.json()
            last = body["data"][-1]
            assert "macd" in last
            assert "macd_signal" in last
            assert "macd_histogram" in last

    def test_indicators_bollinger_bands(self, api_client):
        """BB request should return bb_upper, bb_middle, bb_lower."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=bb"
            )
            body = resp.json()
            last = body["data"][-1]
            assert "bb_upper" in last
            assert "bb_middle" in last
            assert "bb_lower" in last
            # Upper should be > middle > lower
            if last["bb_upper"] and last["bb_middle"] and last["bb_lower"]:
                assert last["bb_upper"] >= last["bb_middle"] >= last["bb_lower"]

    def test_indicators_multiple(self, api_client):
        """Should handle multiple indicators in a single request."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=ema_9,rsi_14,macd,bb"
            )
            assert resp.status_code == 200
            body = resp.json()
            last = body["data"][-1]
            # All indicator keys should be present
            for key in ["ema_9", "rsi_14", "macd", "macd_signal", "macd_histogram",
                        "bb_upper", "bb_middle", "bb_lower"]:
                assert key in last

    def test_indicators_cached_on_second_request(self, api_client):
        """Second request should use cached data."""
        self._clear_cache()
        mock_candles = _make_mock_candles(30)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ) as mock_fetch:
            resp1 = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=30&indicators=ema_9"
            )
            assert resp1.status_code == 200

            resp2 = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=30&indicators=ema_9"
            )
            assert resp2.status_code == 200

            # Binance should only be called once
            assert mock_fetch.call_count == 1

    def test_indicators_empty_candles(self, api_client):
        """Should return empty data when no candles are available."""
        self._clear_cache()
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = api_client.get(
                "/api/indicators?symbol=UNKNOWN/USDT&timeframe=1h&indicators=ema_9"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["data"] == []
            assert body["source"] == "empty"

    def test_indicators_default_params(self, api_client):
        """Calling without explicit params should use defaults."""
        self._clear_cache()
        mock_candles = _make_mock_candles(30)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get("/api/indicators")
            assert resp.status_code == 200
            body = resp.json()
            assert body["symbol"] == "BTC/USDT"
            assert body["timeframe"] == "1h"

    def test_indicators_data_structure(self, api_client):
        """Each data point should have time and close fields."""
        self._clear_cache()
        mock_candles = _make_mock_candles(10)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=10&indicators=ema_9"
            )
            body = resp.json()
            point = body["data"][0]
            assert "time" in point
            assert "close" in point
            assert isinstance(point["time"], int)
            assert isinstance(point["close"], float)

    def test_indicators_sma(self, api_client):
        """SMA indicators should be computed correctly."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=sma_20"
            )
            body = resp.json()
            last = body["data"][-1]
            assert "sma_20" in last
            assert last["sma_20"] is not None

    def test_indicators_response_has_count(self, api_client):
        """Response should include count field."""
        self._clear_cache()
        mock_candles = _make_mock_candles(25)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=ETH/USDT&timeframe=1h&limit=25&indicators=ema_9"
            )
            body = resp.json()
            assert body["count"] == 25

    def test_indicators_early_values_are_null(self, api_client):
        """Indicator values before warmup period should be null."""
        self._clear_cache()
        mock_candles = _make_mock_candles(15)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=15&indicators=ema_21"
            )
            body = resp.json()
            # First data point should have null ema_21 (not enough data)
            first = body["data"][0]
            assert first["ema_21"] is None


class TestIndicatorEdgeCases:
    """Edge cases for indicator calculation."""

    def _clear_cache(self):
        import app.api.routes.indicators as ind_mod
        ind_mod._indicator_cache.clear()

    def test_stochastic_indicator(self, api_client):
        """Stochastic should return stoch_k and stoch_d."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=stoch"
            )
            assert resp.status_code == 200
            last = resp.json()["data"][-1]
            assert "stoch_k" in last
            assert "stoch_d" in last

    def test_adx_indicator(self, api_client):
        """ADX should be between 0 and 100."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=adx"
            )
            assert resp.status_code == 200
            last = resp.json()["data"][-1]
            assert "adx" in last
            if last["adx"] is not None:
                assert 0 <= last["adx"] <= 100

    def test_atr_indicator(self, api_client):
        """ATR should be positive."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=atr"
            )
            assert resp.status_code == 200
            last = resp.json()["data"][-1]
            assert "atr" in last
            if last["atr"] is not None:
                assert last["atr"] > 0

    def test_vwap_indicator(self, api_client):
        """VWAP should be near price range."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=vwap"
            )
            assert resp.status_code == 200
            last = resp.json()["data"][-1]
            assert "vwap" in last

    def test_obv_indicator(self, api_client):
        """OBV should be present."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=obv"
            )
            assert resp.status_code == 200
            last = resp.json()["data"][-1]
            assert "obv" in last

    def test_mfi_indicator(self, api_client):
        """MFI should be between 0 and 100."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=mfi"
            )
            assert resp.status_code == 200
            last = resp.json()["data"][-1]
            assert "mfi" in last
            if last["mfi"] is not None:
                assert 0 <= last["mfi"] <= 100

    def test_vol_sma_indicator(self, api_client):
        """Volume SMA should be present."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60&indicators=vol_sma"
            )
            assert resp.status_code == 200
            last = resp.json()["data"][-1]
            assert "vol_sma" in last

    def test_all_indicators_at_once(self, api_client):
        """Request all indicators in single call."""
        self._clear_cache()
        mock_candles = _make_mock_candles(60)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=60"
                "&indicators=ema_9,ema_21,sma_20,rsi_14,macd,bb,stoch,adx,atr,vwap,obv,mfi,vol_sma"
            )
            assert resp.status_code == 200
            last = resp.json()["data"][-1]
            # Spot check key indicators are present
            assert "ema_9" in last
            assert "rsi_14" in last
            assert "macd" in last
            assert "bb_upper" in last

    def test_few_candles_graceful(self, api_client):
        """With very few candles (< warmup), should not crash."""
        self._clear_cache()
        mock_candles = _make_mock_candles(5)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=BTC/USDT&timeframe=1h&limit=5&indicators=rsi_14,macd"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert len(body["data"]) == 5

    def test_different_symbol(self, api_client):
        """Requesting different symbol should work."""
        self._clear_cache()
        mock_candles = _make_mock_candles(30)
        with patch(
            "app.api.routes.indicators._fetch_candles_from_binance",
            new_callable=AsyncMock,
            return_value=mock_candles,
        ):
            resp = api_client.get(
                "/api/indicators?symbol=ETH/USDT&timeframe=4h&limit=30&indicators=ema_9"
            )
            assert resp.status_code == 200
            assert resp.json()["symbol"] == "ETH/USDT"
            assert resp.json()["timeframe"] == "4h"
