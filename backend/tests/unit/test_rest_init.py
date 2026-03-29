"""Unit tests for RestClient - init, start, stop lifecycle.

asyncio.sleep patched with CancelledError so funding loop exits immediately.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config.constants import DEFAULT_SYMBOLS
from app.core.models import FundingRate
from app.data.feed.rest_client import RestClient

_PATCH_SLEEP = "app.data.feed.rest_client.asyncio.sleep"


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.fetch_funding_rate = AsyncMock(return_value={
        "fundingRate": 0.0001,
        "fundingTimestamp": 1705276800000,
        "nextFundingTimestamp": 1705305600000,
    })
    return provider


@pytest.fixture
def mock_funding():
    return FundingRate(
        symbol="BTC/USDT",
        timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
        rate=0.0001,
        next_funding_time=datetime(2024, 1, 15, 8, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_normalizer(mock_funding):
    normalizer = MagicMock()
    normalizer.normalize_funding_rate = MagicMock(return_value=mock_funding)
    normalizer.cache_funding_rate = AsyncMock()
    return normalizer


@pytest.fixture
def client(mock_provider, mock_normalizer):
    return RestClient(mock_provider, mock_normalizer, symbols=["BTC/USDT"])


def test_init_default_symbols(mock_provider, mock_normalizer):
    c = RestClient(mock_provider, mock_normalizer)
    assert c._symbols == DEFAULT_SYMBOLS
    assert c._running is False
    assert c._tasks == []


def test_init_default_symbols_none(mock_provider, mock_normalizer):
    c = RestClient(mock_provider, mock_normalizer, symbols=None)
    assert c._symbols == DEFAULT_SYMBOLS


def test_init_custom_symbols(mock_provider, mock_normalizer):
    custom = ["SOL/USDT", "DOGE/USDT"]
    c = RestClient(mock_provider, mock_normalizer, symbols=custom)
    assert c._symbols == custom


def test_init_single_symbol(mock_provider, mock_normalizer):
    c = RestClient(mock_provider, mock_normalizer, symbols=["BTC/USDT"])
    assert len(c._symbols) == 1


async def test_start(client):
    with patch(_PATCH_SLEEP, side_effect=asyncio.CancelledError):
        await client.start()
        assert client._running is True
        assert len(client._tasks) == 1
        assert isinstance(client._tasks[0], asyncio.Task)
        await client.stop()


async def test_start_already_running(client):
    with patch(_PATCH_SLEEP, side_effect=asyncio.CancelledError):
        await client.start()
        first_tasks = list(client._tasks)
        await client.start()
        assert len(client._tasks) == 1
        assert client._tasks[0] is first_tasks[0]
        await client.stop()


async def test_stop(client):
    with patch(_PATCH_SLEEP, side_effect=asyncio.CancelledError):
        await client.start()
        task = client._tasks[0]
        await client.stop()
        assert client._running is False
        assert client._tasks == []
        assert task.cancelled() or task.done()


async def test_stop_without_start(client):
    await client.stop()
    assert client._running is False
    assert client._tasks == []


async def test_stop_multiple_times(client):
    with patch(_PATCH_SLEEP, side_effect=asyncio.CancelledError):
        await client.start()
        await client.stop()
        await client.stop()
        assert client._running is False


async def test_start_then_stop_lifecycle(client):
    assert client._running is False
    with patch(_PATCH_SLEEP, side_effect=asyncio.CancelledError):
        await client.start()
        assert client._running is True
        await client.stop()
        assert client._running is False
        assert client._tasks == []


def test_default_symbols_value():
    assert "BTC/USDT" in DEFAULT_SYMBOLS
    assert "ETH/USDT" in DEFAULT_SYMBOLS
    assert len(DEFAULT_SYMBOLS) == 5
