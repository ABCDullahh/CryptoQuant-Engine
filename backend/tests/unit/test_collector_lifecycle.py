"""Unit tests for DataCollector - init, properties, start, stop."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.config.constants import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAMES


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDataCollectorInit:
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    def test_init_default_config(self, MockBP, MockNorm, MockWS, MockRC, MockHL):
        from app.data.collector import DataCollector

        collector = DataCollector()
        assert collector._symbols == DEFAULT_SYMBOLS
        assert collector._timeframes == [str(tf) for tf in DEFAULT_TIMEFRAMES]
        assert collector._running is False
        MockBP.assert_called_once()
        MockNorm.assert_called_once()

    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    def test_init_custom_config(self, MockBP, MockNorm, MockWS, MockRC, MockHL):
        from app.data.collector import DataCollector

        symbols = ["BTC/USDT", "ETH/USDT"]
        timeframes = ["1h", "4h"]
        collector = DataCollector(symbols=symbols, timeframes=timeframes)
        assert collector._symbols == symbols
        assert collector._timeframes == timeframes


class TestDataCollectorProperties:
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    def test_is_running_initially_false(self, MockBP, MockNorm, MockWS, MockRC, MockHL):
        from app.data.collector import DataCollector
        collector = DataCollector()
        assert collector.is_running is False

    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    def test_provider_property(self, MockBP, MockNorm, MockWS, MockRC, MockHL):
        from app.data.collector import DataCollector
        collector = DataCollector()
        assert collector.provider is MockBP.return_value

    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    def test_normalizer_property(self, MockBP, MockNorm, MockWS, MockRC, MockHL):
        from app.data.collector import DataCollector
        collector = DataCollector()
        assert collector.normalizer is MockNorm.return_value

    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    def test_historical_loader_property(self, MockBP, MockNorm, MockWS, MockRC, MockHL):
        from app.data.collector import DataCollector
        collector = DataCollector()
        assert collector.historical_loader is MockHL.return_value


class TestDataCollectorStart:
    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_start_calls_all_components(self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus):
        from app.data.collector import DataCollector

        mock_provider = MockBP.return_value
        mock_ws = MockWS.return_value
        mock_rc = MockRC.return_value

        mock_provider.connect = AsyncMock()
        mock_event_bus.connect = AsyncMock()
        mock_ws.start = AsyncMock()
        mock_ws.add_ohlcv_stream = AsyncMock(return_value="BTC/USDT:1h")
        mock_rc.start = AsyncMock()

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        await collector.start()

        mock_provider.connect.assert_called_once()
        mock_event_bus.connect.assert_called_once()
        mock_ws.start.assert_called_once()
        assert collector.is_running is True

    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_start_adds_streams_for_all_pairs(self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus):
        from app.data.collector import DataCollector

        mock_provider = MockBP.return_value
        mock_ws = MockWS.return_value
        mock_rc = MockRC.return_value

        mock_provider.connect = AsyncMock()
        mock_event_bus.connect = AsyncMock()
        mock_ws.start = AsyncMock()
        mock_ws.add_ohlcv_stream = AsyncMock(return_value="stream_id")
        mock_rc.start = AsyncMock()

        symbols = ["BTC/USDT", "ETH/USDT"]
        timeframes = ["1h", "4h"]
        collector = DataCollector(symbols=symbols, timeframes=timeframes)
        await collector.start()

        assert mock_ws.add_ohlcv_stream.call_count == len(symbols) * len(timeframes)

    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_start_already_running_skips(self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus):
        from app.data.collector import DataCollector

        mock_provider = MockBP.return_value
        mock_ws = MockWS.return_value
        mock_rc = MockRC.return_value

        mock_provider.connect = AsyncMock()
        mock_event_bus.connect = AsyncMock()
        mock_ws.start = AsyncMock()
        mock_ws.add_ohlcv_stream = AsyncMock()
        mock_rc.start = AsyncMock()

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        await collector.start()
        mock_provider.connect.reset_mock()
        await collector.start()
        mock_provider.connect.assert_not_called()


class TestDataCollectorStop:
    @patch("app.data.collector.event_bus")
    @patch("app.data.collector.HistoricalLoader")
    @patch("app.data.collector.RestClient")
    @patch("app.data.collector.WebSocketManager")
    @patch("app.data.collector.DataNormalizer")
    @patch("app.data.collector.BinanceProvider")
    async def test_stop_calls_all_components(self, MockBP, MockNorm, MockWS, MockRC, MockHL, mock_event_bus):
        from app.data.collector import DataCollector

        mock_provider = MockBP.return_value
        mock_ws = MockWS.return_value
        mock_rc = MockRC.return_value

        mock_provider.connect = AsyncMock()
        mock_provider.close = AsyncMock()
        mock_event_bus.connect = AsyncMock()
        mock_ws.start = AsyncMock()
        mock_ws.stop = AsyncMock()
        mock_ws.add_ohlcv_stream = AsyncMock()
        mock_rc.start = AsyncMock()
        mock_rc.stop = AsyncMock()

        collector = DataCollector(symbols=["BTC/USDT"], timeframes=["1h"])
        await collector.start()
        await collector.stop()

        mock_rc.stop.assert_called_once()
        mock_ws.stop.assert_called_once()
        mock_provider.close.assert_called_once()
        assert collector.is_running is False
