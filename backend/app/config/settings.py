"""Application settings loaded from environment variables."""

import secrets
import warnings
from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SECRET = "change-this-to-a-random-string"


class Settings(BaseSettings):
    """Main application settings. Loaded from .env file and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://cryptoquant:cryptoquant_dev@localhost:5432/cryptoquant"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # --- Redis ---
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")

    # --- Trading Safety ---
    trading_enabled: bool = False  # Master kill switch: must be explicitly enabled
    environment: str = "demo"  # "demo" or "live" — guards against accidental production use

    # --- Exchange ---
    binance_api_key: str = ""
    binance_secret: str = ""
    binance_testnet: bool = True

    # Aliases for generic exchange access (used by CCXT endpoints)
    @property
    def exchange_api_key(self) -> str:
        return self.binance_api_key

    @property
    def exchange_api_secret(self) -> str:
        return self.binance_secret

    @property
    def exchange_testnet(self) -> bool:
        return self.binance_testnet

    # --- API Server ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    jwt_secret: str = _INSECURE_DEFAULT_SECRET
    cors_origins: str = "http://localhost:9977,http://localhost:3000"

    # --- Risk Defaults ---
    default_risk_pct: float = 0.02
    max_positions: int = 5
    max_portfolio_heat: float = 0.06
    max_leverage: int = 10
    default_leverage: int = 3

    # --- Notifications ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""

    # --- Logging ---
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "console"

    # --- ML ---
    ml_models_dir: str = "./ml_models"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings singleton.

    If JWT_SECRET is not set (still the default), auto-generate a random secret
    for this session and warn the user.
    """
    settings = Settings()
    if settings.jwt_secret == _INSECURE_DEFAULT_SECRET:
        settings.jwt_secret = secrets.token_urlsafe(48)
        warnings.warn(
            "JWT_SECRET is not set! A random secret has been generated for this "
            "session. Set JWT_SECRET in your .env file for persistent tokens.",
            UserWarning,
            stacklevel=2,
        )
    return settings
