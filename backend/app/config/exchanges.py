"""Exchange-specific configuration."""

from dataclasses import dataclass, field

from app.config.constants import Exchange, Timeframe


@dataclass(frozen=True)
class ExchangeConfig:
    """Configuration for a specific exchange."""

    name: Exchange
    base_url: str
    ws_url: str
    testnet_base_url: str
    testnet_ws_url: str
    maker_fee: float
    taker_fee: float
    max_leverage: int
    supported_timeframes: tuple[Timeframe, ...] = field(
        default=(
            Timeframe.M1,
            Timeframe.M5,
            Timeframe.M15,
            Timeframe.H1,
            Timeframe.H4,
            Timeframe.D1,
        )
    )
    rate_limit_per_minute: int = 1200
    ws_rate_limit_per_second: int = 5


BINANCE_CONFIG = ExchangeConfig(
    name=Exchange.BINANCE,
    base_url="https://fapi.binance.com",
    ws_url="wss://fstream.binance.com",
    testnet_base_url="https://testnet.binancefuture.com",
    testnet_ws_url="wss://fstream.binancefuture.com",
    maker_fee=0.0002,  # 0.02%
    taker_fee=0.0004,  # 0.04%
    max_leverage=125,
    rate_limit_per_minute=2400,
    ws_rate_limit_per_second=10,
)

EXCHANGE_CONFIGS: dict[Exchange, ExchangeConfig] = {
    Exchange.BINANCE: BINANCE_CONFIG,
}


def get_exchange_config(exchange: Exchange) -> ExchangeConfig:
    """Get configuration for a specific exchange."""
    if exchange not in EXCHANGE_CONFIGS:
        raise ValueError(f"Unsupported exchange: {exchange}")
    return EXCHANGE_CONFIGS[exchange]
