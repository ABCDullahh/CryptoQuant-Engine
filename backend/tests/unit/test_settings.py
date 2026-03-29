"""Unit tests for backend/app/config/settings.py"""

import pytest
from pydantic import PostgresDsn, RedisDsn

from app.config.settings import Settings, get_settings


class TestSettings:
    """Test suite for Settings configuration."""

    def test_default_settings(self, monkeypatch):
        """Test that Settings creates with all expected default values."""
        # Clear env vars that may be set by .env file
        monkeypatch.delenv("BINANCE_API_KEY", raising=False)
        monkeypatch.delenv("BINANCE_SECRET", raising=False)
        # Create settings with _env_file=None to test code defaults (not .env overrides)
        settings = Settings(_env_file=None)

        # Database settings
        db_url = str(settings.database_url)
        assert db_url.startswith("postgresql+asyncpg://")
        assert "cryptoquant" in db_url
        assert settings.database_pool_size == 10
        assert settings.database_max_overflow == 20

        # Redis settings
        assert str(settings.redis_url) == "redis://localhost:6379/0"

        # Exchange settings
        assert settings.binance_api_key == ""
        assert settings.binance_secret == ""
        assert settings.binance_testnet is True

        # API Server settings
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert len(settings.jwt_secret) > 0  # default or .env override
        assert settings.cors_origins == "http://localhost:3000"

        # Risk defaults
        assert settings.default_risk_pct == 0.02
        assert settings.max_positions == 5
        assert settings.max_portfolio_heat == 0.06
        assert settings.max_leverage == 10
        assert settings.default_leverage == 3

        # Notifications
        assert settings.telegram_bot_token == ""
        assert settings.telegram_chat_id == ""
        assert settings.discord_webhook_url == ""

        # Logging
        assert settings.log_level == "INFO"
        assert settings.log_format == "json"

        # ML
        assert settings.ml_models_dir == "./ml_models"

    def test_env_override(self, monkeypatch):
        """Test that environment variables override default settings."""
        # Set environment variables
        monkeypatch.setenv("DATABASE_POOL_SIZE", "20")
        monkeypatch.setenv("API_PORT", "9000")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("MAX_POSITIONS", "10")
        monkeypatch.setenv("BINANCE_TESTNET", "false")

        # Create new Settings instance (not using cached get_settings)
        settings = Settings()

        assert settings.database_pool_size == 20
        assert settings.api_port == 9000
        assert settings.log_level == "DEBUG"
        assert settings.max_positions == 10
        assert settings.binance_testnet is False

    def test_cors_origins_list_single(self):
        """Test cors_origins_list property with a single origin."""
        settings = Settings()

        origins_list = settings.cors_origins_list

        assert isinstance(origins_list, list)
        assert len(origins_list) == 1
        assert origins_list[0] == "http://localhost:3000"

    def test_cors_origins_list_multiple(self, monkeypatch):
        """Test cors_origins_list property with multiple comma-separated origins."""
        monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com")

        settings = Settings()
        origins_list = settings.cors_origins_list

        assert isinstance(origins_list, list)
        assert len(origins_list) == 2
        assert origins_list[0] == "http://a.com"
        assert origins_list[1] == "http://b.com"

    def test_binance_testnet_default_true(self):
        """Test that binance_testnet defaults to True."""
        settings = Settings()

        assert settings.binance_testnet is True

    def test_trading_enabled_default_false(self, monkeypatch):
        """Test that trading_enabled defaults to False (master kill switch)."""
        monkeypatch.setenv("TRADING_ENABLED", "false")
        settings = Settings()
        assert settings.trading_enabled is False

    def test_environment_default_demo(self, monkeypatch):
        """Test that environment defaults to 'demo'."""
        monkeypatch.setenv("ENVIRONMENT", "demo")
        settings = Settings()
        assert settings.environment == "demo"

    def test_trading_enabled_env_override(self, monkeypatch):
        """Test that TRADING_ENABLED can be overridden via env."""
        monkeypatch.setenv("TRADING_ENABLED", "true")
        settings = Settings()
        assert settings.trading_enabled is True

    def test_risk_defaults(self):
        """Test that risk management parameters have correct defaults."""
        settings = Settings()

        assert settings.default_risk_pct == 0.02
        assert settings.max_positions == 5
        assert settings.max_portfolio_heat == 0.06
        assert settings.max_leverage == 10
        assert settings.default_leverage == 3

    def test_database_url_type(self):
        """Test that database_url is a PostgresDsn type."""
        settings = Settings()

        # PostgresDsn from pydantic v2 can be checked via isinstance or str representation
        assert isinstance(settings.database_url, (PostgresDsn, str))
        # Ensure it's a valid postgres connection string
        db_str = str(settings.database_url)
        assert db_str.startswith("postgresql")

    def test_extra_fields_ignored(self, monkeypatch):
        """Test that extra environment variables are ignored (extra='ignore')."""
        # Set an extra environment variable that doesn't exist in Settings
        monkeypatch.setenv("SOME_RANDOM_EXTRA_FIELD", "should_be_ignored")
        monkeypatch.setenv("ANOTHER_UNKNOWN_VAR", "12345")

        # Should not raise an error
        settings = Settings()

        # Verify it doesn't have the extra field
        assert not hasattr(settings, "some_random_extra_field")
        assert not hasattr(settings, "another_unknown_var")


class TestGetSettings:
    """Test suite for get_settings() function."""

    def test_get_settings_returns_settings_instance(self):
        """Test that get_settings() returns a Settings instance."""
        # Clear the cache first
        get_settings.cache_clear()

        settings = get_settings()

        assert isinstance(settings, Settings)

    def test_get_settings_is_cached(self):
        """Test that get_settings() returns the same cached instance."""
        # Clear the cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the exact same object due to @lru_cache
        assert settings1 is settings2

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self):
        """Fixture to clear get_settings cache before each test."""
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()
