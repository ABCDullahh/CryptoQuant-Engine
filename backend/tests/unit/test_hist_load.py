"""Unit tests for HistoricalLoader - load_history, load_all_defaults, fill_gaps, store."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.models import Candle
from app.config.constants import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAMES
from app.data.feed.historical_loader import (
    MAX_CANDLES_PER_REQUEST,
    HistoricalLoader,
)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.fetch_ohlcv = AsyncMock(return_value=[])
    return provider


@pytest.fixture
def mock_normalizer():
    normalizer = MagicMock()
    normalizer.normalize_candles = MagicMock(return_value=[])
    return normalizer


@pytest.fixture
def loader(mock_provider, mock_normalizer):
    return HistoricalLoader(provider=mock_provider, normalizer=mock_normalizer)


def _make_raw_candle(ts_ms: int) -> list:
    return [ts_ms, 43000.0, 43500.0, 42900.0, 43200.0, 100.0]


def _make_candle(ts_ms: int, symbol: str = "BTC/USDT", timeframe: str = "1h") -> Candle:
    return Candle(
        time=datetime.fromtimestamp(ts_ms / 1000, tz=UTC),
        symbol=symbol, timeframe=timeframe,
        open=43000.0, high=43500.0, low=42900.0, close=43200.0, volume=100.0,
    )


def _patch_session():
    mock_result = MagicMock()
    mock_result.rowcount = 2

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)
    return patch("app.data.feed.historical_loader.async_session_factory", mock_factory), mock_session, mock_result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadHistory:
    async def test_load_history_single_page(self, loader, mock_provider, mock_normalizer):
        ts1, ts2 = 1700000000000, 1700003600000
        raw = [_make_raw_candle(ts1), _make_raw_candle(ts2)]
        candles = [_make_candle(ts1), _make_candle(ts2)]

        mock_provider.fetch_ohlcv = AsyncMock(return_value=raw)
        mock_normalizer.normalize_candles = MagicMock(return_value=candles)

        session_patch, mock_session, mock_result = _patch_session()
        mock_result.rowcount = 2
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 2, tzinfo=UTC)

        with session_patch:
            total = await loader.load_history("BTC/USDT", "1h", start, end)

        assert total == 2
        mock_provider.fetch_ohlcv.assert_called_once()

    async def test_load_history_multiple_pages(self, loader, mock_provider, mock_normalizer):
        base_ts = 1700000000000
        step = 3600000

        raw_page1 = [_make_raw_candle(base_ts + i * step) for i in range(1000)]
        candles_page1 = [_make_candle(base_ts + i * step) for i in range(1000)]

        page2_start = base_ts + 1000 * step
        raw_page2 = [_make_raw_candle(page2_start + i * step) for i in range(500)]
        candles_page2 = [_make_candle(page2_start + i * step) for i in range(500)]

        mock_provider.fetch_ohlcv = AsyncMock(side_effect=[raw_page1, raw_page2])
        mock_normalizer.normalize_candles = MagicMock(side_effect=[candles_page1, candles_page2])

        session_patch, mock_session, mock_result = _patch_session()
        mock_result.rowcount = 1000

        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2025, 1, 1, tzinfo=UTC)

        with session_patch:
            total = await loader.load_history("BTC/USDT", "1h", start, end)

        assert total == 2000
        assert mock_provider.fetch_ohlcv.call_count == 2

    async def test_load_history_empty_response(self, loader, mock_provider):
        mock_provider.fetch_ohlcv = AsyncMock(return_value=[])
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 2, tzinfo=UTC)
        total = await loader.load_history("BTC/USDT", "1h", start, end)
        assert total == 0

    async def test_load_history_default_end_is_now(self, loader, mock_provider):
        mock_provider.fetch_ohlcv = AsyncMock(return_value=[])
        start = datetime(2024, 1, 1, tzinfo=UTC)
        total = await loader.load_history("BTC/USDT", "1h", start)
        assert total == 0
        mock_provider.fetch_ohlcv.assert_called_once()

    async def test_load_history_exception_breaks_loop(self, loader, mock_provider, mock_normalizer):
        mock_provider.fetch_ohlcv = AsyncMock(side_effect=RuntimeError("exchange down"))
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 2, tzinfo=UTC)
        total = await loader.load_history("BTC/USDT", "1h", start, end)
        assert total == 0


class TestLoadAllDefaults:
    async def test_load_all_defaults_calls_load_history_for_each_pair(self, loader):
        loader.load_history = AsyncMock(return_value=42)
        results = await loader.load_all_defaults(days_back=30)

        expected_count = len(DEFAULT_SYMBOLS) * len(DEFAULT_TIMEFRAMES)
        assert loader.load_history.call_count == expected_count

        for symbol in DEFAULT_SYMBOLS:
            for tf in DEFAULT_TIMEFRAMES:
                key = f"{symbol}:{tf}"
                assert key in results
                assert results[key] == 42

    async def test_load_all_defaults_handles_exception_per_pair(self, loader):
        call_count = 0

        async def _side_effect(symbol, timeframe, start):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")
            return 10

        loader.load_history = AsyncMock(side_effect=_side_effect)
        results = await loader.load_all_defaults(days_back=7)
        values = list(results.values())
        assert values[0] == 0
        assert all(v == 10 for v in values[1:])


class TestFillGaps:
    async def test_fill_gaps_no_data_returns_zero(self, loader):
        loader.get_latest_candle_time = AsyncMock(return_value=None)
        result = await loader.fill_gaps("BTC/USDT", "1h")
        assert result == 0

    async def test_fill_gaps_unknown_timeframe_returns_zero(self, loader):
        latest = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        loader.get_latest_candle_time = AsyncMock(return_value=latest)
        result = await loader.fill_gaps("BTC/USDT", "3h")
        assert result == 0

    async def test_fill_gaps_calls_load_history(self, loader):
        latest = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        loader.get_latest_candle_time = AsyncMock(return_value=latest)
        loader.load_history = AsyncMock(return_value=50)
        result = await loader.fill_gaps("BTC/USDT", "1h")
        assert result == 50
        loader.load_history.assert_called_once()


class TestGetLatestCandleTime:
    async def test_get_latest_candle_time_returns_datetime(self, loader):
        expected_time = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=expected_time)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.data.feed.historical_loader.async_session_factory", MagicMock(return_value=mock_session)):
            result = await loader.get_latest_candle_time("BTC/USDT", "1h")
        assert result == expected_time

    async def test_get_latest_candle_time_returns_none_when_empty(self, loader):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.data.feed.historical_loader.async_session_factory", MagicMock(return_value=mock_session)):
            result = await loader.get_latest_candle_time("BTC/USDT", "1h")
        assert result is None


class TestStoreCandles:
    async def test_store_candles_empty_list_returns_zero(self, loader):
        result = await loader._store_candles([])
        assert result == 0

    async def test_store_candles_inserts_and_returns_rowcount(self, loader):
        candles = [_make_candle(1700000000000), _make_candle(1700003600000)]
        session_patch, mock_session, mock_result = _patch_session()
        mock_result.rowcount = 2
        with session_patch:
            result = await loader._store_candles(candles)
        assert result == 2
        mock_session.execute.assert_called_once()

    async def test_store_candles_fallback_to_len_rows(self, loader):
        candles = [_make_candle(1700000000000)]
        session_patch, mock_session, mock_result = _patch_session()
        mock_result.rowcount = 0
        with session_patch:
            result = await loader._store_candles(candles)
        assert result == 1
