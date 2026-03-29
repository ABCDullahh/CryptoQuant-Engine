"""Unit tests for DataNormalizer - Redis cache methods."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio import Redis

from app.core.models import Candle, FundingRate, OrderBook
from app.data.normalization.normalizer import (
    CACHE_CANDLE,
    CACHE_FUNDING,
    CACHE_ORDERBOOK,
    CANDLE_TTL,
    FUNDING_TTL,
    ORDERBOOK_TTL,
    DataNormalizer,
)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis():
    redis = AsyncMock(spec=Redis)
    redis.set = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    return redis


def _make_candle(**overrides) -> Candle:
    defaults = dict(
        time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        symbol="BTC/USDT",
        timeframe="1h",
        open=42000.0,
        high=42500.0,
        low=41800.0,
        close=42300.0,
        volume=1500.0,
    )
    defaults.update(overrides)
    return Candle(**defaults)


def _make_order_book(**overrides) -> OrderBook:
    defaults = dict(
        symbol="BTC/USDT",
        timestamp=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        bids=[(42000.0, 1.5), (41999.0, 2.3)],
        asks=[(42001.0, 0.8), (42002.0, 1.1)],
    )
    defaults.update(overrides)
    return OrderBook(**defaults)


def _make_funding_rate(**overrides) -> FundingRate:
    defaults = dict(
        symbol="BTC/USDT",
        timestamp=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        rate=0.0001,
        next_funding_time=datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC),
    )
    defaults.update(overrides)
    return FundingRate(**defaults)


# ---------------------------------------------------------------------------
# Cache write tests
# ---------------------------------------------------------------------------


class TestCacheCandle:
    async def test_calls_redis_set_with_correct_key_and_ttl(self, mock_redis):
        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            candle = _make_candle(symbol="BTC/USDT", timeframe="1h")
            await normalizer.cache_candle(candle)

            expected_key = CACHE_CANDLE.format(symbol="BTC/USDT", timeframe="1h")
            assert expected_key == "candle:BTC/USDT:1h"
            mock_redis.set.assert_called_once_with(
                expected_key, candle.model_dump_json(), ex=CANDLE_TTL,
            )

    async def test_uses_correct_ttl_value(self, mock_redis):
        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            candle = _make_candle()
            await normalizer.cache_candle(candle)

            call_kwargs = mock_redis.set.call_args
            assert call_kwargs[1]["ex"] == 300 or call_kwargs[0][2] if len(call_kwargs[0]) > 2 else call_kwargs[1].get("ex") == 300

    async def test_different_symbols_produce_different_keys(self, mock_redis):
        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            await normalizer.cache_candle(_make_candle(symbol="BTC/USDT", timeframe="1h"))
            await normalizer.cache_candle(_make_candle(symbol="ETH/USDT", timeframe="4h"))

            calls = mock_redis.set.call_args_list
            assert calls[0][0][0] == "candle:BTC/USDT:1h"
            assert calls[1][0][0] == "candle:ETH/USDT:4h"


class TestCacheOrderBook:
    async def test_calls_redis_set_with_correct_key_and_ttl(self, mock_redis):
        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            ob = _make_order_book(symbol="BTC/USDT")
            await normalizer.cache_order_book(ob)

            expected_key = CACHE_ORDERBOOK.format(symbol="BTC/USDT")
            assert expected_key == "orderbook:BTC/USDT"
            mock_redis.set.assert_called_once_with(expected_key, ob.model_dump_json(), ex=ORDERBOOK_TTL)

    async def test_uses_correct_ttl_value(self, mock_redis):
        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            ob = _make_order_book()
            await normalizer.cache_order_book(ob)
            _, kwargs = mock_redis.set.call_args
            assert kwargs["ex"] == 10


class TestCacheFundingRate:
    async def test_calls_redis_set_with_correct_key_and_ttl(self, mock_redis):
        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            fr = _make_funding_rate(symbol="BTC/USDT")
            await normalizer.cache_funding_rate(fr)

            expected_key = CACHE_FUNDING.format(symbol="BTC/USDT")
            assert expected_key == "funding:BTC/USDT"
            mock_redis.set.assert_called_once_with(expected_key, fr.model_dump_json(), ex=FUNDING_TTL)

    async def test_uses_correct_ttl_value(self, mock_redis):
        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            fr = _make_funding_rate()
            await normalizer.cache_funding_rate(fr)
            _, kwargs = mock_redis.set.call_args
            assert kwargs["ex"] == 3600


# ---------------------------------------------------------------------------
# Cache read tests
# ---------------------------------------------------------------------------


class TestGetCachedCandle:
    async def test_returns_candle_when_data_exists(self, mock_redis):
        candle = _make_candle(symbol="BTC/USDT", timeframe="1h")
        mock_redis.get = AsyncMock(return_value=candle.model_dump_json())

        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            result = await normalizer.get_cached_candle("BTC/USDT", "1h")

            assert result is not None
            assert isinstance(result, Candle)
            assert result.symbol == "BTC/USDT"
            mock_redis.get.assert_called_once_with("candle:BTC/USDT:1h")

    async def test_returns_none_when_no_data(self, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            result = await normalizer.get_cached_candle("BTC/USDT", "1h")
            assert result is None

    async def test_returns_none_for_empty_string(self, mock_redis):
        mock_redis.get = AsyncMock(return_value="")
        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            result = await normalizer.get_cached_candle("BTC/USDT", "1h")
            assert result is None


class TestGetCachedOrderBook:
    async def test_returns_order_book_when_data_exists(self, mock_redis):
        ob = _make_order_book(symbol="ETH/USDT")
        mock_redis.get = AsyncMock(return_value=ob.model_dump_json())

        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            result = await normalizer.get_cached_order_book("ETH/USDT")

            assert result is not None
            assert isinstance(result, OrderBook)
            assert result.symbol == "ETH/USDT"

    async def test_returns_none_when_no_data(self, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            result = await normalizer.get_cached_order_book("ETH/USDT")
            assert result is None


class TestGetCachedFundingRate:
    async def test_returns_funding_rate_when_data_exists(self, mock_redis):
        fr = _make_funding_rate(symbol="BTC/USDT")
        mock_redis.get = AsyncMock(return_value=fr.model_dump_json())

        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            result = await normalizer.get_cached_funding_rate("BTC/USDT")

            assert result is not None
            assert isinstance(result, FundingRate)
            assert result.rate == 0.0001

    async def test_returns_none_when_no_data(self, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            result = await normalizer.get_cached_funding_rate("BTC/USDT")
            assert result is None

    async def test_roundtrip_funding_rate_without_next_time(self, mock_redis):
        fr = _make_funding_rate(next_funding_time=None)
        mock_redis.get = AsyncMock(return_value=fr.model_dump_json())

        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis):
            normalizer = DataNormalizer()
            result = await normalizer.get_cached_funding_rate("BTC/USDT")
            assert result is not None
            assert result.next_funding_time is None
