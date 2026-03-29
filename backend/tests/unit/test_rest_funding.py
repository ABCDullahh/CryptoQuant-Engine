"""Unit tests for RestClient - funding rate fetch, publish, loop."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config.constants import DEFAULT_SYMBOLS, EventChannel
from app.core.models import EventMessage, FundingRate
from app.data.feed.rest_client import RestClient


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


async def test_fetch_and_publish_funding(client, mock_provider, mock_normalizer, mock_funding):
    with patch("app.data.feed.rest_client.event_bus") as mock_event_bus:
        mock_event_bus.publish = AsyncMock()
        await client._fetch_and_publish_funding("BTC/USDT")

        mock_provider.fetch_funding_rate.assert_called_once_with("BTC/USDT")
        raw_data = mock_provider.fetch_funding_rate.return_value
        mock_normalizer.normalize_funding_rate.assert_called_once_with(raw_data, "BTC/USDT")
        mock_normalizer.cache_funding_rate.assert_called_once_with(mock_funding)

        mock_event_bus.publish.assert_called_once()
        call_args = mock_event_bus.publish.call_args
        channel = call_args[0][0]
        event_msg = call_args[0][1]
        assert channel == EventChannel.MARKET_FUNDING
        assert isinstance(event_msg, EventMessage)
        assert event_msg.event_type == "funding_rate"


async def test_fetch_and_publish_funding_data_content(client, mock_provider, mock_normalizer, mock_funding):
    with patch("app.data.feed.rest_client.event_bus") as mock_event_bus:
        mock_event_bus.publish = AsyncMock()
        await client._fetch_and_publish_funding("BTC/USDT")

        event_msg = mock_event_bus.publish.call_args[0][1]
        data = event_msg.data
        assert data["symbol"] == "BTC/USDT"
        assert data["rate"] == 0.0001


async def test_fetch_and_publish_funding_multiple_symbols(mock_provider, mock_normalizer, mock_funding):
    c = RestClient(mock_provider, mock_normalizer, symbols=["BTC/USDT", "ETH/USDT"])

    with patch("app.data.feed.rest_client.event_bus") as mock_event_bus:
        mock_event_bus.publish = AsyncMock()
        await c._fetch_and_publish_funding("BTC/USDT")
        await c._fetch_and_publish_funding("ETH/USDT")

        assert mock_provider.fetch_funding_rate.call_count == 2


async def test_fetch_funding_rate_oneshot(client, mock_provider, mock_normalizer, mock_funding):
    result = await client.fetch_funding_rate("BTC/USDT")
    assert result is mock_funding
    assert isinstance(result, FundingRate)
    mock_provider.fetch_funding_rate.assert_called_once_with("BTC/USDT")


async def test_fetch_funding_rate_oneshot_does_not_publish(client, mock_provider, mock_normalizer):
    with patch("app.data.feed.rest_client.event_bus") as mock_event_bus:
        mock_event_bus.publish = AsyncMock()
        await client.fetch_funding_rate("BTC/USDT")
        mock_event_bus.publish.assert_not_called()


async def test_fetch_funding_rate_returns_correct_type(client, mock_normalizer, mock_funding):
    result = await client.fetch_funding_rate("BTC/USDT")
    assert isinstance(result, FundingRate)
    assert result.timestamp == datetime(2024, 1, 15, tzinfo=timezone.utc)


async def test_funding_rate_loop_iterates_symbols(mock_provider, mock_normalizer, mock_funding):
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    c = RestClient(mock_provider, mock_normalizer, symbols=symbols)
    c._running = True

    async def stop_after_one_cycle(delay):
        c._running = False

    with patch("app.data.feed.rest_client.event_bus") as mock_event_bus:
        mock_event_bus.publish = AsyncMock()
        with patch("app.data.feed.rest_client.asyncio.sleep", side_effect=stop_after_one_cycle):
            await c._funding_rate_loop()

    assert mock_provider.fetch_funding_rate.call_count == 3


async def test_funding_rate_loop_handles_fetch_error(client, mock_provider, mock_normalizer):
    mock_provider.fetch_funding_rate = AsyncMock(side_effect=ConnectionError("network error"))
    client._running = True

    async def stop_after_one_cycle(delay):
        client._running = False

    with patch("app.data.feed.rest_client.asyncio.sleep", side_effect=stop_after_one_cycle):
        await client._funding_rate_loop()

    mock_provider.fetch_funding_rate.assert_called()


async def test_funding_rate_loop_sleeps_60_seconds(client, mock_provider, mock_normalizer, mock_funding):
    client._running = True
    sleep_values = []

    async def capture_sleep(delay):
        sleep_values.append(delay)
        client._running = False

    with patch("app.data.feed.rest_client.event_bus") as mock_event_bus:
        mock_event_bus.publish = AsyncMock()
        with patch("app.data.feed.rest_client.asyncio.sleep", side_effect=capture_sleep):
            await client._funding_rate_loop()

    assert sleep_values == [60]
