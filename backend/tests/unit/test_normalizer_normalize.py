"""Unit tests for DataNormalizer - normalization methods (candle, order book, funding)."""

from datetime import UTC, datetime, timezone

import pytest

from app.core.models import Candle, FundingRate, OrderBook
from app.data.normalization.normalizer import DataNormalizer


@pytest.fixture
def normalizer():
    return DataNormalizer()


@pytest.fixture
def sample_raw_candle():
    return [1704067200000, 42000.5, 42500.75, 41800.25, 42300.0, 1500.123]


@pytest.fixture
def sample_raw_order_book():
    return {
        "bids": [["42000.5", "1.5"], ["41999.0", "2.3"]],
        "asks": [["42001.0", "0.8"], ["42002.5", "1.1"]],
        "timestamp": 1704067200000,
    }


@pytest.fixture
def sample_raw_funding():
    return {
        "fundingRate": 0.0001,
        "fundingTimestamp": 1704067200000,
        "nextFundingTimestamp": 1704096000000,
    }


class TestNormalizeCandle:
    def test_valid_raw_data_returns_correct_candle(self, normalizer, sample_raw_candle):
        candle = normalizer.normalize_candle(sample_raw_candle, "BTC/USDT", "1h")

        assert isinstance(candle, Candle)
        assert candle.symbol == "BTC/USDT"
        assert candle.timeframe == "1h"
        assert candle.open == 42000.5
        assert candle.high == 42500.75
        assert candle.low == 41800.25
        assert candle.close == 42300.0
        assert candle.volume == 1500.123

    def test_timestamp_ms_converted_to_utc_datetime(self, normalizer):
        raw = [1704067200000, 100, 110, 90, 105, 50]
        candle = normalizer.normalize_candle(raw, "ETH/USDT", "4h")

        expected_dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert candle.time == expected_dt
        assert candle.time.tzinfo is not None

    def test_float_conversion_from_string_values(self, normalizer):
        raw = [1704067200000, "42000.5", "42500.75", "41800.25", "42300.0", "1500.123"]
        candle = normalizer.normalize_candle(raw, "BTC/USDT", "1h")

        assert candle.open == 42000.5
        assert candle.volume == 1500.123
        assert all(
            isinstance(v, float)
            for v in [candle.open, candle.high, candle.low, candle.close, candle.volume]
        )

    def test_float_conversion_from_int_values(self, normalizer):
        raw = [1704067200000, 42000, 42500, 41800, 42300, 1500]
        candle = normalizer.normalize_candle(raw, "BTC/USDT", "15m")

        assert isinstance(candle.open, float)
        assert isinstance(candle.volume, float)

    def test_optional_fields_default_to_none(self, normalizer, sample_raw_candle):
        candle = normalizer.normalize_candle(sample_raw_candle, "BTC/USDT", "1h")
        assert candle.quote_volume is None
        assert candle.trades_count is None


class TestNormalizeCandles:
    def test_converts_multiple_raw_candles(self, normalizer):
        raw_list = [
            [1704067200000, 42000, 42500, 41800, 42300, 1500],
            [1704070800000, 42300, 42800, 42100, 42600, 1200],
            [1704074400000, 42600, 43000, 42400, 42900, 1800],
        ]
        candles = normalizer.normalize_candles(raw_list, "BTC/USDT", "1h")

        assert len(candles) == 3
        assert all(isinstance(c, Candle) for c in candles)
        assert candles[0].open == 42000.0

    def test_empty_list_returns_empty_list(self, normalizer):
        candles = normalizer.normalize_candles([], "BTC/USDT", "1h")
        assert candles == []


class TestNormalizeOrderBook:
    def test_int_timestamp(self, normalizer):
        raw = {"bids": [["42000.5", "1.5"]], "asks": [["42001.0", "0.8"]], "timestamp": 1704067200000}
        ob = normalizer.normalize_order_book(raw, "BTC/USDT")

        assert isinstance(ob, OrderBook)
        assert ob.symbol == "BTC/USDT"
        expected_dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert ob.timestamp == expected_dt

    def test_float_timestamp(self, normalizer):
        raw = {"bids": [["42000.5", "1.5"]], "asks": [["42001.0", "0.8"]], "timestamp": 1704067200000.0}
        ob = normalizer.normalize_order_book(raw, "BTC/USDT")
        expected_dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert ob.timestamp == expected_dt

    def test_str_timestamp_iso_format(self, normalizer):
        raw = {"bids": [["42000.5", "1.5"]], "asks": [["42001.0", "0.8"]], "timestamp": "2024-01-01T00:00:00Z"}
        ob = normalizer.normalize_order_book(raw, "BTC/USDT")
        expected_dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert ob.timestamp == expected_dt

    def test_str_timestamp_iso_format_with_offset(self, normalizer):
        raw = {"bids": [], "asks": [], "timestamp": "2024-01-01T00:00:00+00:00"}
        ob = normalizer.normalize_order_book(raw, "BTC/USDT")
        expected_dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert ob.timestamp == expected_dt

    def test_none_timestamp_uses_now(self, normalizer):
        raw = {"bids": [["42000.5", "1.5"]], "asks": [["42001.0", "0.8"]], "timestamp": None}
        before = datetime.now(tz=UTC)
        ob = normalizer.normalize_order_book(raw, "BTC/USDT")
        after = datetime.now(tz=UTC)
        assert before <= ob.timestamp <= after

    def test_missing_timestamp_key_uses_now(self, normalizer):
        raw = {"bids": [["42000.5", "1.5"]], "asks": [["42001.0", "0.8"]]}
        before = datetime.now(tz=UTC)
        ob = normalizer.normalize_order_book(raw, "BTC/USDT")
        after = datetime.now(tz=UTC)
        assert before <= ob.timestamp <= after

    def test_bids_asks_conversion_to_float_tuples(self, normalizer, sample_raw_order_book):
        ob = normalizer.normalize_order_book(sample_raw_order_book, "BTC/USDT")

        assert len(ob.bids) == 2
        assert len(ob.asks) == 2
        assert ob.bids[0] == (42000.5, 1.5)
        assert ob.asks[0] == (42001.0, 0.8)
        for price, qty in ob.bids + ob.asks:
            assert isinstance(price, float)
            assert isinstance(qty, float)

    def test_empty_bids_asks(self, normalizer):
        raw = {"bids": [], "asks": [], "timestamp": 1704067200000}
        ob = normalizer.normalize_order_book(raw, "BTC/USDT")
        assert ob.bids == []
        assert ob.asks == []

    def test_missing_bids_asks_keys(self, normalizer):
        raw = {"timestamp": 1704067200000}
        ob = normalizer.normalize_order_book(raw, "BTC/USDT")
        assert ob.bids == []
        assert ob.asks == []

    def test_datetime_field_uses_raw(self, normalizer):
        raw = {"bids": [], "asks": [], "datetime": "2024-06-15T12:00:00Z"}
        ob = normalizer.normalize_order_book(raw, "ETH/USDT")
        expected_dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert ob.timestamp == expected_dt


class TestNormalizeFundingRate:
    def test_complete_data(self, normalizer, sample_raw_funding):
        fr = normalizer.normalize_funding_rate(sample_raw_funding, "BTC/USDT")

        assert isinstance(fr, FundingRate)
        assert fr.symbol == "BTC/USDT"
        assert fr.rate == 0.0001
        expected_ts = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert fr.timestamp == expected_ts
        expected_next = datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC)
        assert fr.next_funding_time == expected_next

    def test_missing_next_funding_timestamp(self, normalizer):
        raw = {"fundingRate": 0.0002, "fundingTimestamp": 1704067200000}
        fr = normalizer.normalize_funding_rate(raw, "ETH/USDT")
        assert fr.next_funding_time is None

    def test_next_funding_timestamp_none(self, normalizer):
        raw = {"fundingRate": 0.0003, "fundingTimestamp": 1704067200000, "nextFundingTimestamp": None}
        fr = normalizer.normalize_funding_rate(raw, "BTC/USDT")
        assert fr.next_funding_time is None

    def test_rate_zero(self, normalizer):
        raw = {"fundingRate": 0, "fundingTimestamp": 1704067200000}
        fr = normalizer.normalize_funding_rate(raw, "BTC/USDT")
        assert fr.rate == 0.0
        assert isinstance(fr.rate, float)

    def test_negative_rate(self, normalizer):
        raw = {"fundingRate": -0.0005, "fundingTimestamp": 1704067200000}
        fr = normalizer.normalize_funding_rate(raw, "BTC/USDT")
        assert fr.rate == -0.0005

    def test_fallback_to_timestamp_key(self, normalizer):
        raw = {"fundingRate": 0.0001, "timestamp": 1704067200000}
        fr = normalizer.normalize_funding_rate(raw, "BTC/USDT")
        expected_ts = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert fr.timestamp == expected_ts

    def test_missing_timestamp_uses_now(self, normalizer):
        raw = {"fundingRate": 0.0001}
        before = datetime.now(tz=UTC)
        fr = normalizer.normalize_funding_rate(raw, "BTC/USDT")
        after = datetime.now(tz=UTC)
        assert before <= fr.timestamp <= after

    def test_missing_funding_rate_defaults_to_zero(self, normalizer):
        raw = {"fundingTimestamp": 1704067200000}
        fr = normalizer.normalize_funding_rate(raw, "BTC/USDT")
        assert fr.rate == 0.0
