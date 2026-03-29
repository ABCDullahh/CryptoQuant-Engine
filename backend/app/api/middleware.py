"""Custom rate limiting middleware for CryptoQuant Engine API.

Uses an in-memory sliding-window counter per client IP. No external
dependencies required — suitable for single-instance deployments.
"""

from __future__ import annotations

import time
from collections import defaultdict

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)

# Rate limit configuration (requests per window)
GENERAL_LIMIT = 300  # requests per minute for general endpoints
AUTH_LIMIT = 10  # requests per minute for auth endpoints
WINDOW_SECONDS = 60  # sliding window size in seconds

# Paths that use the stricter auth rate limit
AUTH_PATHS = {"/api/auth/login", "/api/auth/register"}

# Paths exempt from rate limiting (health checks, high-frequency polling)
EXEMPT_PATHS = {"/health", "/api/system/ping", "/ws", "/api/health/detailed"}


class _TokenBucket:
    """Per-key sliding window rate limiter backed by a simple list of timestamps."""

    def __init__(self) -> None:
        # key -> list of request timestamps (only within the current window)
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup: float = time.monotonic()

    def is_allowed(self, key: str, limit: int, window: float) -> tuple[bool, int]:
        """Check whether *key* may proceed.

        Returns (allowed, remaining) where *remaining* is how many requests
        are still available in the current window.
        """
        now = time.monotonic()

        # Periodic cleanup: every 5 minutes, purge stale keys to prevent memory leak
        if now - self._last_cleanup > 300:
            self._cleanup(now, window)

        # Trim expired entries for this key
        cutoff = now - window
        hits = self._hits[key]
        # Remove timestamps older than the window
        while hits and hits[0] < cutoff:
            hits.pop(0)

        if len(hits) >= limit:
            remaining = 0
            return False, remaining

        hits.append(now)
        remaining = limit - len(hits)
        return True, remaining

    def _cleanup(self, now: float, window: float) -> None:
        """Remove keys that have had no activity within *window* seconds."""
        cutoff = now - window
        stale_keys = [k for k, v in self._hits.items() if not v or v[-1] < cutoff]
        for k in stale_keys:
            del self._hits[k]
        self._last_cleanup = now


_bucket = _TokenBucket()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces per-IP rate limits.

    - 60 req/min for general endpoints
    - 5 req/min for auth endpoints (login/register)
    - Returns 429 Too Many Requests with Retry-After header when exceeded
    """

    async def dispatch(self, request: Request, call_next):
        # Determine client IP (respect X-Forwarded-For behind a reverse proxy)
        client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"

        path = request.url.path

        # Skip rate limiting for exempt paths (health checks, WS, ping)
        if path in EXEMPT_PATHS:
            return await call_next(request)

        # Choose limit based on path
        if path in AUTH_PATHS:
            limit = AUTH_LIMIT
            bucket_key = f"auth:{client_ip}"
        else:
            limit = GENERAL_LIMIT
            bucket_key = f"general:{client_ip}"

        allowed, remaining = _bucket.is_allowed(bucket_key, limit, WINDOW_SECONDS)

        if not allowed:
            logger.warning(
                "rate_limit.exceeded",
                client_ip=client_ip,
                path=path,
                limit=limit,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please try again later.",
                    }
                },
                headers={
                    "Retry-After": str(WINDOW_SECONDS),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)

        # Attach rate-limit headers to successful responses
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
