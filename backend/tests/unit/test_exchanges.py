"""Unit tests for backend/app/config/exchanges.py"""

import pytest
from dataclasses import FrozenInstanceError

from app.config.constants import Exchange, Timeframe
from app.config.exchanges import (
    ExchangeConfig,
    BINANCE_CONFIG,
    EXCHANGE_CONFIGS,
    get_exchange_config,
)


class TestBinanceConfig:
    """Test suite for BINANCE_CONFIG."""

    def test_binance_config_values(self):
        """Test that BINANCE_CONFIG has all expected field values."""
        assert BINANCE_CONFIG.name == Exchange.BINANCE
        assert BINANCE_CONFIG.base_url == "https://fapi.binance.com"
        assert BINANCE_CONFIG.ws_url == "wss://fstream.binance.com"
        assert BINANCE_CONFIG.testnet_base_url == "https://testnet.binancefuture.com"
        assert BINANCE_CONFIG.testnet_ws_url == "wss://fstream.binancefuture.com"
        assert BINANCE_CONFIG.maker_fee == 0.0002
        assert BINANCE_CONFIG.taker_fee == 0.0004
        assert BINANCE_CONFIG.max_leverage == 125
        assert BINANCE_CONFIG.rate_limit_per_minute == 2400
        assert BINANCE_CONFIG.ws_rate_limit_per_second == 10

    def test_binance_supported_timeframes(self):
        """Test that BINANCE_CONFIG supports all 6 timeframes."""
        timeframes = BINANCE_CONFIG.supported_timeframes

        assert len(timeframes) == 6
        assert Timeframe.M1 in timeframes
        assert Timeframe.M5 in timeframes
        assert Timeframe.M15 in timeframes
        assert Timeframe.H1 in timeframes
        assert Timeframe.H4 in timeframes
        assert Timeframe.D1 in timeframes

    def test_binance_fees(self):
        """Test that Binance fees are valid and maker < taker."""
        assert BINANCE_CONFIG.maker_fee > 0
        assert BINANCE_CONFIG.taker_fee > 0
        assert BINANCE_CONFIG.maker_fee < BINANCE_CONFIG.taker_fee

    def test_binance_urls_https(self):
        """Test that Binance URLs use correct protocols (https/wss)."""
        assert BINANCE_CONFIG.base_url.startswith("https://")
        assert BINANCE_CONFIG.ws_url.startswith("wss://")
        assert BINANCE_CONFIG.testnet_base_url.startswith("https://")
        assert BINANCE_CONFIG.testnet_ws_url.startswith("wss://")


class TestExchangeConfig:
    """Test suite for ExchangeConfig dataclass."""

    def test_exchange_config_frozen(self):
        """Test that ExchangeConfig is frozen and cannot be modified."""
        with pytest.raises(FrozenInstanceError):
            BINANCE_CONFIG.maker_fee = 0.001

    def test_exchange_config_creation(self):
        """Test that ExchangeConfig can be created with custom values."""
        custom_config = ExchangeConfig(
            name=Exchange.BYBIT,
            base_url="https://api.bybit.com",
            ws_url="wss://stream.bybit.com",
            testnet_base_url="https://api-testnet.bybit.com",
            testnet_ws_url="wss://stream-testnet.bybit.com",
            maker_fee=0.0001,
            taker_fee=0.0006,
            max_leverage=100,
        )

        assert custom_config.name == Exchange.BYBIT
        assert custom_config.maker_fee == 0.0001
        assert custom_config.taker_fee == 0.0006
        assert custom_config.max_leverage == 100
        # Check default values
        assert custom_config.rate_limit_per_minute == 1200
        assert custom_config.ws_rate_limit_per_second == 5
        assert len(custom_config.supported_timeframes) == 6


class TestGetExchangeConfig:
    """Test suite for get_exchange_config function."""

    def test_get_exchange_config_binance(self):
        """Test that get_exchange_config returns BINANCE_CONFIG for Exchange.BINANCE."""
        config = get_exchange_config(Exchange.BINANCE)

        assert config is BINANCE_CONFIG
        assert config.name == Exchange.BINANCE

    def test_get_exchange_config_unsupported(self):
        """Test that get_exchange_config raises ValueError for unsupported exchange."""
        with pytest.raises(ValueError) as exc_info:
            get_exchange_config(Exchange.BYBIT)

        assert "Unsupported exchange" in str(exc_info.value)
        assert "bybit" in str(exc_info.value)


class TestExchangeConfigs:
    """Test suite for EXCHANGE_CONFIGS dictionary."""

    def test_exchange_configs_contains_binance(self):
        """Test that EXCHANGE_CONFIGS contains Binance."""
        assert Exchange.BINANCE in EXCHANGE_CONFIGS
        assert EXCHANGE_CONFIGS[Exchange.BINANCE] is BINANCE_CONFIG

    def test_exchange_configs_type(self):
        """Test that EXCHANGE_CONFIGS is a dictionary with correct types."""
        assert isinstance(EXCHANGE_CONFIGS, dict)

        for exchange, config in EXCHANGE_CONFIGS.items():
            assert isinstance(exchange, Exchange)
            assert isinstance(config, ExchangeConfig)
            assert config.name == exchange
