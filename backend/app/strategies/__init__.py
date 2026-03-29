"""Trading strategies for signal generation."""

from app.strategies.base import BaseStrategy
from app.strategies.funding import FundingArbStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.momentum import MomentumStrategy
from app.strategies.smc import SmartMoneyStrategy
from app.strategies.order_block_zones import OrderBlockZonesStrategy
from app.strategies.volume import VolumeAnalysisStrategy

STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "smart_money": SmartMoneyStrategy,
    "volume_analysis": VolumeAnalysisStrategy,
    "funding_arb": FundingArbStrategy,
    "ob_zones": OrderBlockZonesStrategy,
    # Frontend aliases (bot page sends these keys)
    "smc": SmartMoneyStrategy,
    "volume_profile": VolumeAnalysisStrategy,
    "market_structure": MeanReversionStrategy,
    "funding": FundingArbStrategy,
}

__all__ = [
    "BaseStrategy",
    "FundingArbStrategy",
    "MeanReversionStrategy",
    "MomentumStrategy",
    "OrderBlockZonesStrategy",
    "SmartMoneyStrategy",
    "STRATEGY_REGISTRY",
    "VolumeAnalysisStrategy",
]
