"""Base strategy abstract class for all trading strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.config.constants import Direction
from app.core.models import Candle, IndicatorValues, MarketContext, RawSignal
from app.indicators.base import IndicatorPipeline

if TYPE_CHECKING:
    from app.data.collector import DataCollector


class BaseStrategy(ABC):
    """Abstract base class for trading strategies.

    Subclasses must implement `evaluate()` which is a synchronous method
    that takes precomputed candles, indicators, and optional market context
    and returns a RawSignal or None.

    The `analyze()` method is an async convenience that fetches data from
    the DataCollector, computes indicators, then calls evaluate().
    """

    name: str = "base"
    weight: float = 0.0
    min_candles: int = 20

    def __init__(self) -> None:
        self._pipeline = IndicatorPipeline()

    @abstractmethod
    def evaluate(
        self,
        candles: list[Candle],
        indicators: IndicatorValues,
        context: MarketContext | None = None,
    ) -> RawSignal | None:
        """Evaluate strategy on given data. Returns signal or None."""
        ...

    async def prepare(
        self,
        collector: DataCollector,
        symbol: str,
    ) -> None:
        """Pre-fetch any async data needed before evaluate().

        Called by the aggregator before evaluate(). Override in subclasses
        that need async data (e.g., funding rates). Default is a no-op.
        """

    async def analyze(
        self,
        collector: DataCollector,
        symbol: str,
        timeframe: str,
    ) -> RawSignal | None:
        """Fetch data, compute indicators, and evaluate strategy."""
        candles = await collector.get_candles(symbol, timeframe, limit=max(self.min_candles, 200))
        if len(candles) < self.min_candles:
            return None

        indicators = self._pipeline.compute(candles)
        return self.evaluate(candles, indicators)

    def _create_signal(
        self,
        direction: Direction,
        strength: float,
        entry_price: float,
        symbol: str,
        timeframe: str,
        conditions: list[str] | None = None,
        metadata: dict | None = None,
    ) -> RawSignal:
        """Helper to create a properly formatted RawSignal."""
        return RawSignal(
            strategy_name=self.name,
            symbol=symbol,
            direction=direction,
            strength=max(-1.0, min(1.0, strength)),
            entry_price=entry_price,
            timeframe=timeframe,
            conditions=conditions or [],
            metadata=metadata or {},
        )
