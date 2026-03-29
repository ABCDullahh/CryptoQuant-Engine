"""Unit tests for DataCollector - on_ohlcv_update, get_funding, get_candles, load_historical, store."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config.constants import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAMES, EventChannel
from app.core.models import Candle, EventMessage, FundingRate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_candle(symbol: str = "BTC/USDT", timeframe: str = "1h") -> Candle:
    return Candle(
        time=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        symbol=symbol, timeframe=timeframe,
        open=43000.0, high=43500.0, low=42900.0, close=43200.0,
        volume=100.0, quote_volume=4320000.0, trades_count=500,
    )


def _make_funding_rate(symbol: str = "BTC/USDT") -> FundingRate:
    return FundingRate(
        symbol=symbol,
        timestamp=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        rate=0.0001,
        next_funding_time=datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOnOhlcvUpdate:
    @patch("app.data.collector.async_session_factory")
    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_on_ohlcv_update_normalizes_stores_caches_publishes(
        self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus, mock_session_factory
    ):
        from app.data.collector import DataCollector

        mock_normalizer = MockNorm.return_value
        candle = _make_candle()
        mock_normalizer.normalize_candle = MagicMock(return_value=candle)
        mock_normalizer.cache_candle = AsyncMock()

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        mock_event_bus.publish = AsyncMock()

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        raw_candles = [[1700000000000, 43000.0, 43500.0, 42900.0, 43200.0, 100.0]]
        await collector._on_ohlcv_update(raw_candles, "BTC/USDT", "1h")

        mock_normalizer.normalize_candle.assert_called_once()
        mock_session.execute.assert_called_once()
        mock_normalizer.cache_candle.assert_called_once_with(candle)
        mock_event_bus.publish.assert_called_once()

        channel = mock_event_bus.publish.call_args[0][0]
        assert channel == EventChannel.MARKET_CANDLE.format(timeframe="1h")

    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_on_ohlcv_update_empty_candles_returns_early(
        self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus
    ):
        from app.data.collector import DataCollector

        mock_normalizer = MockNorm.return_value
        mock_normalizer.normalize_candle = MagicMock()

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        await collector._on_ohlcv_update([], "BTC/USDT", "1h")

        mock_normalizer.normalize_candle.assert_not_called()


class TestGetFundingRate:
    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_get_funding_rate_cached(self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus):
        from app.data.collector import DataCollector

        mock_normalizer = MockNorm.return_value
        cached_fr = _make_funding_rate()
        mock_normalizer.get_cached_funding_rate = AsyncMock(return_value=cached_fr)
        MockRC.return_value.fetch_funding_rate = AsyncMock()

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        result = await collector.get_funding_rate("BTC/USDT")

        assert result is cached_fr
        MockRC.return_value.fetch_funding_rate.assert_not_called()

    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_get_funding_rate_not_cached_fetches_from_rest(self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus):
        from app.data.collector import DataCollector

        mock_normalizer = MockNorm.return_value
        mock_normalizer.get_cached_funding_rate = AsyncMock(return_value=None)

        fresh_fr = _make_funding_rate()
        MockRC.return_value.fetch_funding_rate = AsyncMock(return_value=fresh_fr)

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        result = await collector.get_funding_rate("BTC/USDT")
        assert result is fresh_fr


class TestGetCandles:
    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_get_candles_fetches_from_exchange(self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus):
        from app.data.collector import DataCollector

        mock_provider = MockBP.return_value
        mock_normalizer = MockNorm.return_value
        mock_provider.is_connected = True

        raw = [[1700000000000, 43000.0, 43500.0, 42900.0, 43200.0, 100.0]]
        candles = [_make_candle()]
        mock_provider.fetch_ohlcv = AsyncMock(return_value=raw)
        mock_normalizer.normalize_candles = MagicMock(return_value=candles)
        mock_normalizer.get_cached_candle = AsyncMock(return_value=None)

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        # Mock _load_candles_from_db to return empty so it falls through to exchange
        collector._load_candles_from_db = AsyncMock(return_value=[])
        result = await collector.get_candles("BTC/USDT", "1h", limit=50)

        assert result == candles
        mock_provider.fetch_ohlcv.assert_called_once_with("BTC/USDT", "1h", limit=50)

    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_get_candles_connects_if_not_connected(self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus):
        from app.data.collector import DataCollector

        mock_provider = MockBP.return_value
        mock_provider.is_connected = False
        mock_provider.connect = AsyncMock()
        mock_provider.fetch_ohlcv = AsyncMock(return_value=[])
        MockNorm.return_value.normalize_candles = MagicMock(return_value=[])
        MockNorm.return_value.get_cached_candle = AsyncMock(return_value=None)

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        # Mock _load_candles_from_db to return empty so it falls through to exchange
        collector._load_candles_from_db = AsyncMock(return_value=[])
        await collector.get_candles("BTC/USDT", "1h")
        mock_provider.connect.assert_called_once()


class TestLoadHistorical:
    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_load_historical_connects_if_needed(self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus):
        from app.data.collector import DataCollector

        mock_provider = MockBP.return_value
        mock_provider.is_connected = False
        mock_provider.connect = AsyncMock()
        MockHL.return_value.load_history = AsyncMock(return_value=100)

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        result = await collector.load_historical(days_back=30)

        mock_provider.connect.assert_called_once()
        # Result includes configured timeframe + DEFAULT_TIMEFRAMES
        assert "BTC/USDT:1h" in result
        assert result["BTC/USDT:1h"] == 100

    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_load_historical_skips_connect_if_connected(self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus):
        from app.data.collector import DataCollector

        mock_provider = MockBP.return_value
        mock_provider.is_connected = True
        mock_provider.connect = AsyncMock()
        MockHL.return_value.load_history = AsyncMock(return_value=0)

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        await collector.load_historical()
        mock_provider.connect.assert_not_called()


class TestStoreCandle:
    @patch("app.data.collector.async_session_factory")
    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_store_candle_inserts_to_db(self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus, mock_session_factory):
        from app.data.collector import DataCollector

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        await collector._store_candle(_make_candle())

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("app.data.collector.async_session_factory")
    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_store_candle_handles_db_error_gracefully(self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus, mock_session_factory):
        from app.data.collector import DataCollector

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("db down"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        await collector._store_candle(_make_candle())
