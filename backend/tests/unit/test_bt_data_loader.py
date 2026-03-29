"""Tests for backtesting data loader -- synthetic candle generation and symbol normalization."""

import pytest
from datetime import datetime, timezone

from app.backtesting.data_loader import (
    normalize_symbol,
    denormalize_symbol,
    generate_synthetic_candles,
)


class TestNormalizeSymbol:
    def test_already_normalized(self):
        assert normalize_symbol("BTC/USDT") == "BTC/USDT"

    def test_btcusdt(self):
        assert normalize_symbol("BTCUSDT") == "BTC/USDT"

    def test_ethusdt(self):
        assert normalize_symbol("ETHUSDT") == "ETH/USDT"

    def test_bnbusdt(self):
        assert normalize_symbol("BNBUSDT") == "BNB/USDT"

    def test_solusdt(self):
        assert normalize_symbol("SOLUSDT") == "SOL/USDT"

    def test_lowercase_input(self):
        # normalize_symbol uppercases before regex, so lowercase works
        result = normalize_symbol("btcusdt")
        assert result == "BTC/USDT"

    def test_unknown_format(self):
        result = normalize_symbol("UNKNOWN")
        assert result == "UNKNOWN"  # Pass-through

    def test_busd_quote(self):
        assert normalize_symbol("ETHBUSD") == "ETH/BUSD"

    def test_btc_quote(self):
        assert normalize_symbol("ETHBTC") == "ETH/BTC"


class TestDenormalizeSymbol:
    def test_removes_slash(self):
        assert denormalize_symbol("BTC/USDT") == "BTCUSDT"

    def test_already_denormalized(self):
        assert denormalize_symbol("BTCUSDT") == "BTCUSDT"

    def test_eth_usdt(self):
        assert denormalize_symbol("ETH/USDT") == "ETHUSDT"


class TestGenerateSyntheticCandles:
    @pytest.fixture
    def candles(self):
        return generate_synthetic_candles(
            symbol="BTC/USDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 8, tzinfo=timezone.utc),  # 7 days = 168 hours
        )

    def test_returns_list(self, candles):
        assert isinstance(candles, list)
        assert len(candles) > 0

    def test_candle_count_hourly(self, candles):
        # 7 days * 24 hours = 168 candles
        assert len(candles) == 168

    def test_candle_fields(self, candles):
        c = candles[0]
        assert c.symbol == "BTC/USDT"
        assert c.timeframe == "1h"
        assert c.open > 0
        assert c.high > 0
        assert c.low > 0
        assert c.close > 0
        assert c.volume > 0

    def test_ohlc_relationship(self, candles):
        for c in candles:
            assert c.high >= c.open, f"high ({c.high}) < open ({c.open})"
            assert c.high >= c.close, f"high ({c.high}) < close ({c.close})"
            assert c.low <= c.open, f"low ({c.low}) > open ({c.open})"
            assert c.low <= c.close, f"low ({c.low}) > close ({c.close})"

    def test_time_ascending(self, candles):
        for i in range(1, len(candles)):
            assert candles[i].time > candles[i - 1].time

    def test_btc_default_price(self, candles):
        # BTC should start around 43000
        assert 30000 < candles[0].open < 60000

    def test_different_symbol_price(self):
        candles = generate_synthetic_candles(
            symbol="ETH/USDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
        # ETH should start around 2500
        assert 1000 < candles[0].open < 5000

    def test_5m_timeframe(self):
        candles = generate_synthetic_candles(
            symbol="BTC/USDT",
            timeframe="5m",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),  # 1 hour
        )
        assert len(candles) == 12  # 60min / 5min = 12

    def test_symbol_normalization(self):
        candles = generate_synthetic_candles(
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        )
        assert candles[0].symbol == "BTC/USDT"

    def test_custom_initial_price(self):
        candles = generate_synthetic_candles(
            symbol="BTC/USDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
            initial_price=50000.0,
        )
        assert 45000 < candles[0].open < 55000

    def test_reproducible_with_seed(self):
        """Same inputs should produce same outputs (seed=42)."""
        args = dict(
            symbol="BTC/USDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
        c1 = generate_synthetic_candles(**args)
        c2 = generate_synthetic_candles(**args)
        assert c1[0].close == c2[0].close
        assert c1[-1].close == c2[-1].close

    def test_naive_datetime_gets_utc(self):
        """Naive datetimes should be treated as UTC."""
        candles = generate_synthetic_candles(
            symbol="BTC/USDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 1, 3, 0),
        )
        assert len(candles) == 3
        assert candles[0].time.tzinfo is not None
