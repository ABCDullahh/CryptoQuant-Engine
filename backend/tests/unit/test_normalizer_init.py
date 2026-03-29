"""Unit tests for DataNormalizer - init, constants, and Redis caching."""

from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio import Redis

from app.data.normalization.normalizer import (
    CACHE_CANDLE,
    CACHE_FUNDING,
    CACHE_ORDERBOOK,
    CANDLE_TTL,
    FUNDING_TTL,
    ORDERBOOK_TTL,
    DataNormalizer,
)


@pytest.fixture
def mock_redis():
    redis = AsyncMock(spec=Redis)
    redis.set = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    return redis


class TestDataNormalizerInit:
    def test_init_redis_is_none(self):
        normalizer = DataNormalizer()
        assert normalizer._redis is None

    async def test_get_redis_caches_connection(self, mock_redis):
        with patch("app.data.normalization.normalizer.get_redis", return_value=mock_redis) as mock_get:
            normalizer = DataNormalizer()
            redis1 = await normalizer._get_redis()
            redis2 = await normalizer._get_redis()
            assert redis1 is redis2
            mock_get.assert_called_once()


class TestConstants:
    def test_cache_key_patterns(self):
        assert "{symbol}" in CACHE_CANDLE
        assert "{timeframe}" in CACHE_CANDLE
        assert "{symbol}" in CACHE_ORDERBOOK
        assert "{symbol}" in CACHE_FUNDING

    def test_ttl_values(self):
        assert CANDLE_TTL == 300
        assert ORDERBOOK_TTL == 10
        assert FUNDING_TTL == 3600

    def test_key_formatting(self):
        assert CACHE_CANDLE.format(symbol="BTC/USDT", timeframe="1h") == "candle:BTC/USDT:1h"
        assert CACHE_ORDERBOOK.format(symbol="ETH/USDT") == "orderbook:ETH/USDT"
        assert CACHE_FUNDING.format(symbol="SOL/USDT") == "funding:SOL/USDT"
