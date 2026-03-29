"""Session factory for background tasks that need their own DB sessions."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings

_engine = None
_session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create an async session factory for background tasks.

    Returns a callable that creates async context-managed sessions,
    suitable for use with `async with db_factory() as session:`.
    """
    global _engine, _session_factory
    if _session_factory is None:
        settings = get_settings()
        _engine = create_async_engine(
            str(settings.database_url),
            echo=False,
        )
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory
