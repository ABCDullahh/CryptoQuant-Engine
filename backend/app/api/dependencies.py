"""FastAPI dependency injection for CryptoQuant Engine."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import decode_access_token


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency. Overridden in tests."""
    from app.db.database import get_db_session

    async for session in get_db_session():
        yield session


async def get_redis_client() -> Redis:
    """Redis client dependency. Overridden in tests."""
    from app.db.redis_client import get_redis

    return await get_redis()


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> str:
    """Authenticate via JWT Bearer token. Returns username/subject."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Strip "Bearer " prefix
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = decode_access_token(token)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return subject


async def optional_auth(
    authorization: str | None = Header(default=None),
) -> str | None:
    """Optional auth - returns None if no token provided."""
    if authorization is None:
        return None
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None
