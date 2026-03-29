"""Unit tests for HistoricalLoader - init, timeframe deltas, constants."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.data.feed.historical_loader import (
    TIMEFRAME_DELTA,
    MAX_CANDLES_PER_REQUEST,
    REQUEST_DELAY,
    HistoricalLoader,
)


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


class TestHistoricalLoaderInit:
    def test_init_sets_provider_and_normalizer(self, mock_provider, mock_normalizer):
        loader = HistoricalLoader(provider=mock_provider, normalizer=mock_normalizer)
        assert loader._provider is mock_provider
        assert loader._normalizer is mock_normalizer


class TestTimeframeDeltaMapping:
    def test_timeframe_delta_mapping_contains_expected_keys(self):
        expected = {"1m", "5m", "15m", "1h", "4h", "1d"}
        assert set(TIMEFRAME_DELTA.keys()) == expected

    def test_timeframe_delta_values_are_timedeltas(self):
        for key, val in TIMEFRAME_DELTA.items():
            assert isinstance(val, timedelta)

    def test_timeframe_delta_1m(self):
        assert TIMEFRAME_DELTA["1m"] == timedelta(minutes=1)

    def test_timeframe_delta_5m(self):
        assert TIMEFRAME_DELTA["5m"] == timedelta(minutes=5)

    def test_timeframe_delta_15m(self):
        assert TIMEFRAME_DELTA["15m"] == timedelta(minutes=15)

    def test_timeframe_delta_1h(self):
        assert TIMEFRAME_DELTA["1h"] == timedelta(hours=1)

    def test_timeframe_delta_4h(self):
        assert TIMEFRAME_DELTA["4h"] == timedelta(hours=4)

    def test_timeframe_delta_1d(self):
        assert TIMEFRAME_DELTA["1d"] == timedelta(days=1)


class TestConstants:
    def test_max_candles_per_request(self):
        assert MAX_CANDLES_PER_REQUEST == 1000

    def test_request_delay(self):
        assert REQUEST_DELAY == 0.2
