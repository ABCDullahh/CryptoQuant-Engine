"""REST client for periodic data fetching (funding rates, sentiment, etc.)."""

from __future__ import annotations

import asyncio

import structlog

from app.config.constants import DEFAULT_SYMBOLS, EventChannel
from app.core.events import event_bus
from app.core.models import EventMessage
from app.data.normalization.normalizer import DataNormalizer
from app.data.providers.base import BaseExchangeProvider

logger = structlog.get_logger(__name__)


class RestClient:
    """Periodically fetches data via REST APIs and publishes events.

    Handles:
    - Funding rates (every 60 seconds)
    - Can be extended for open interest, sentiment, etc.
    """

    def __init__(
        self,
        provider: BaseExchangeProvider,
        normalizer: DataNormalizer,
        symbols: list[str] | None = None,
    ) -> None:
        self._provider = provider
        self._normalizer = normalizer
        self._symbols = symbols or DEFAULT_SYMBOLS
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start all periodic fetching tasks."""
        if self._running:
            return
        self._running = True

        self._tasks.append(asyncio.create_task(self._funding_rate_loop()))
        logger.info("rest_client.started", symbols=self._symbols)

    async def stop(self) -> None:
        """Stop all periodic tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        logger.info("rest_client.stopped")

    async def _funding_rate_loop(self) -> None:
        """Fetch funding rates periodically for all symbols."""
        while self._running:
            for symbol in self._symbols:
                if not self._running:
                    break
                try:
                    await self._fetch_and_publish_funding(symbol)
                except Exception:
                    logger.exception("rest_client.funding_error", symbol=symbol)
            await asyncio.sleep(60)

    async def _fetch_and_publish_funding(self, symbol: str) -> None:
        """Fetch funding rate for a symbol and publish event."""
        raw = await self._provider.fetch_funding_rate(symbol)
        funding = self._normalizer.normalize_funding_rate(raw, symbol)
        await self._normalizer.cache_funding_rate(funding)

        await event_bus.publish(
            EventChannel.MARKET_FUNDING,
            EventMessage(
                event_type="funding_rate",
                data=funding.model_dump(mode="json"),
            ),
        )
        logger.debug("rest_client.funding_published", symbol=symbol, rate=funding.rate)

    async def fetch_funding_rate(self, symbol: str):
        """One-shot fetch funding rate (for external callers)."""
        raw = await self._provider.fetch_funding_rate(symbol)
        funding = self._normalizer.normalize_funding_rate(raw, symbol)
        await self._normalizer.cache_funding_rate(funding)
        return funding
