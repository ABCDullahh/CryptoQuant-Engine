"""Async database engine and session management for TimescaleDB."""

from collections.abc import AsyncGenerator

import structlog

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import get_settings

logger = structlog.get_logger(__name__)

settings = get_settings()

engine = create_async_engine(
    str(settings.database_url),
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
    echo=False,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database: create tables if they don't exist."""
    from app.db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Add new columns to existing tables (safe migration)
    await _ensure_new_columns()


async def _ensure_new_columns() -> None:
    """Add columns introduced after initial schema creation.

    Each ALTER TABLE uses IF NOT EXISTS (PG 9.6+) so this is idempotent.
    """
    from sqlalchemy import text

    migrations = [
        "ALTER TABLE positions ADD COLUMN IF NOT EXISTS trading_mode VARCHAR(10) DEFAULT 'paper'",
        "ALTER TABLE positions ADD COLUMN IF NOT EXISTS exchange_order_id VARCHAR(100)",
        "ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS paper_balance NUMERIC(20,8)",
        "ALTER TABLE bot_state ADD COLUMN IF NOT EXISTS paper_initial_balance NUMERIC(20,8)",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS signal_policy JSONB DEFAULT '{}'::jsonb",
        "ALTER TABLE positions ADD COLUMN IF NOT EXISTS strategy_name VARCHAR(50)",
        "ALTER TABLE positions ADD COLUMN IF NOT EXISTS dca_data_json JSONB",
        "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS annual_return NUMERIC(10,4)",
        "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS expectancy NUMERIC(10,4)",
        "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS avg_win NUMERIC(20,8)",
        "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS avg_loss NUMERIC(20,8)",
        "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS calmar_ratio NUMERIC(10,4)",
        "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS avg_holding_period NUMERIC(10,2)",
    ]

    async with engine.begin() as conn:
        for sql in migrations:
            try:
                await conn.execute(text(sql))
            except Exception as exc:
                logger.debug("db.migration_step_skipped", error=str(exc))


async def init_timescale_hypertables() -> None:
    """Create TimescaleDB hypertables (idempotent). Requires TimescaleDB extension."""
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        await conn.execute(text(
            "SELECT create_hypertable('candles', 'time', "
            "if_not_exists => TRUE, "
            "chunk_time_interval => INTERVAL '7 days')"
        ))


async def close_db() -> None:
    """Dispose of the database engine."""
    await engine.dispose()
