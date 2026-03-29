"""Async Redis client for caching and pub/sub."""

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config.settings import get_settings

settings = get_settings()

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """Get or create the Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            str(settings.redis_url),
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
