"""Shared pytest fixtures for CryptoQuant Engine tests."""

import gc
import pytest
import numpy as np
from datetime import datetime, timezone
from uuid import uuid4

# --- SQLite compatibility for PostgreSQL types (JSONB, UUID) ---
# This allows using in-memory SQLite for API route tests
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"


# Override UUID bind/result processors for SQLite.
# PostgreSQL UUID(as_uuid=False) strips dashes in bind_processor on non-native
# dialects, causing WHERE comparisons to fail against stored UUID strings.
_orig_uuid_bind = PG_UUID.bind_processor
_orig_uuid_result = PG_UUID.result_processor


def _uuid_bind_sqlite(self, dialect):
    if dialect.name == "sqlite":
        return None  # Keep UUID strings as-is (with dashes)
    return _orig_uuid_bind(self, dialect)


def _uuid_result_sqlite(self, dialect, coltype):
    if dialect.name == "sqlite":
        return None  # Return raw string from DB
    return _orig_uuid_result(self, dialect, coltype)


PG_UUID.bind_processor = _uuid_bind_sqlite
PG_UUID.result_processor = _uuid_result_sqlite


from app.config.constants import (
    Direction,
    SignalGrade,
    StopLossType,
    MarketRegime,
    SignalStatus,
)
from app.core.models import (
    Candle,
    IndicatorValues,
    RawSignal,
    CompositeSignal,
    TakeProfit,
    RiskReward,
    PositionSize,
    MarketContext,
    Position,
    PortfolioState,
)


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch):
    """Clear Settings lru_cache before/after each test.

    Also ensures TRADING_ENABLED=true so executor tests can run.
    """
    from app.config.settings import get_settings

    monkeypatch.setenv("TRADING_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _gc_collect_after_test():
    """Force garbage collection after each test to reduce memory usage."""
    yield
    gc.collect()


@pytest.fixture
def sample_candle():
    """Returns a realistic BTC/USDT Candle model instance."""
    return Candle(
        time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        symbol="BTC/USDT",
        timeframe="1h",
        open=43250.50,
        high=43580.75,
        low=43100.25,
        close=43450.00,
        volume=1250.5,
        quote_volume=54312500.00,
        trades_count=15420,
    )


@pytest.fixture
def sample_raw_signal():
    """Returns a RawSignal model instance."""
    return RawSignal(
        strategy_name="smc_strategy",
        symbol="BTC/USDT",
        direction=Direction.LONG,
        strength=0.78,
        entry_price=43450.00,
        timeframe="1h",
        conditions=["order_block_detected", "bullish_fvg", "structure_break"],
        metadata={"order_block_level": 43200.0, "structure_break": True},
    )


@pytest.fixture
def sample_composite_signal():
    """Returns a CompositeSignal model instance with full data."""
    return CompositeSignal(
        symbol="BTC/USDT",
        direction=Direction.LONG,
        grade=SignalGrade.A,
        strength=0.85,
        entry_price=43450.00,
        entry_zone=(43200.00, 43500.00),
        stop_loss=42950.00,
        sl_type=StopLossType.STRUCTURE_BASED,
        take_profits=[
            TakeProfit(level="TP1", price=44200.00, close_pct=50, rr_ratio=1.5),
            TakeProfit(level="TP2", price=45400.00, close_pct=30, rr_ratio=3.0),
            TakeProfit(level="TP3", price=46950.00, close_pct=20, rr_ratio=5.0),
        ],
        risk_reward=RiskReward(rr_tp1=1.5, rr_tp2=3.0, rr_tp3=5.0, weighted_rr=2.75),
        position_size=PositionSize(
            quantity=0.345,
            notional=15000.00,
            margin=5000.00,
            risk_amount=172.50,
            risk_pct=0.02,
            leverage=3,
        ),
        strategy_scores={
            "smc_strategy": 0.85,
            "volume_profile": 0.75,
            "market_structure": 0.80,
            "momentum": 0.72,
        },
        market_context=MarketContext(regime=MarketRegime.TRENDING_UP),
    )


# --- Phase 3 Fixtures ---


@pytest.fixture
def sample_candle_array():
    """Returns 60 realistic candles for indicator/strategy testing."""
    np.random.seed(42)
    candles = []
    price = 43000.0
    for i in range(60):
        price += np.random.randn() * 50
        candles.append(Candle(
            time=datetime(2024, 1, 1, i % 24, 0, tzinfo=timezone.utc),
            symbol="BTC/USDT",
            timeframe="1h",
            open=price - 20,
            high=price + abs(np.random.randn() * 30),
            low=price - abs(np.random.randn() * 30),
            close=price,
            volume=abs(np.random.randn() * 100) + 50,
        ))
    return candles


@pytest.fixture
def sample_indicator_values():
    """Returns a fully-populated IndicatorValues model."""
    return IndicatorValues(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        ema_9=43200.0, ema_21=43100.0, ema_55=43000.0, ema_200=42800.0,
        macd=50.0, macd_signal=30.0, macd_histogram=20.0, adx=28.0,
        rsi_14=55.0, stoch_k=60.0, stoch_d=58.0,
        atr_14=200.0, bb_upper=43800.0, bb_middle=43200.0,
        bb_lower=42600.0, bb_width=0.028,
        vwap=43150.0, obv=50000.0, volume_sma_20=120.0,
    )


@pytest.fixture
def sample_market_context():
    """Returns a MarketContext for trending up regime."""
    return MarketContext(
        regime=MarketRegime.TRENDING_UP,
        trend_1h="STRONG_UP",
        volatility="MEDIUM",
        volume_profile="AVERAGE",
    )


# --- Phase 4 Fixtures ---


@pytest.fixture
def sample_position():
    """Returns a Position model instance."""
    return Position(
        signal_id=uuid4(),
        symbol="BTC/USDT",
        direction=Direction.LONG,
        entry_price=43200.0,
        current_price=43500.0,
        quantity=0.5,
        remaining_qty=0.5,
        leverage=3,
        stop_loss=42900.0,
        take_profits=[
            TakeProfit(level="TP1", price=43650.0, close_pct=50, rr_ratio=1.5),
            TakeProfit(level="TP2", price=44100.0, close_pct=30, rr_ratio=3.0),
            TakeProfit(level="TP3", price=44700.0, close_pct=20, rr_ratio=5.0),
        ],
        unrealized_pnl=150.0,
    )


@pytest.fixture
def sample_portfolio_state():
    """Returns a PortfolioState model instance."""
    return PortfolioState(
        balance=10000.0,
        equity=10150.0,
        unrealized_pnl=150.0,
        margin_used=7200.0,
        margin_available=2800.0,
        portfolio_heat=0.015,
        open_positions=1,
        daily_pnl=150.0,
        weekly_pnl=300.0,
        max_drawdown=0.02,
        consecutive_losses=0,
    )


# --- Phase 5 Fixtures ---


# --- Phase 8 Fixtures (API testing with async SQLite) ---


@pytest.fixture
def async_db_engine():
    """Create an async SQLite engine with all tables for API testing."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool
    from app.db.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    loop = asyncio.new_event_loop()

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop.run_until_complete(setup())
    yield engine

    async def teardown():
        await engine.dispose()

    loop.run_until_complete(teardown())
    loop.close()


@pytest.fixture
def async_db_factory(async_db_engine):
    """Create an async session factory for API testing."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    return async_sessionmaker(
        async_db_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest.fixture
def api_client(async_db_factory, monkeypatch):
    """Create a FastAPI TestClient with async DB, mock auth, and mock bot_service."""
    import os
    from unittest.mock import AsyncMock, patch
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.api.dependencies import get_db, get_current_user

    # Tell lifespan to skip real-time services (price_streamer, orderbook, etc.)
    monkeypatch.setenv("TESTING", "true")

    app = create_app()

    async def override_db():
        async with async_db_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: "testuser"

    # Mock bot_service so API tests don't need ccxt/exchange
    from unittest.mock import MagicMock

    mock_executor = MagicMock()
    mock_executor.execute_signal_and_publish = AsyncMock(return_value=True)
    mock_executor.close_position = AsyncMock()

    with patch("app.api.routes.bot.bot_service") as mock_bot, \
         patch("app.bot.service.bot_service") as mock_bot2:
        for mb in (mock_bot, mock_bot2):
            mb.start = AsyncMock()
            mb.stop = AsyncMock()
            mb.pause = AsyncMock()
            mb.resume = AsyncMock()
            mb.configure = lambda **kwargs: None
            mb.status = "STOPPED"
            mb.collector = None
            mb.executor = mock_executor

        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


@pytest.fixture
def seed_db(async_db_engine):
    """Helper to seed data into the async DB. Returns a function."""
    import asyncio
    from sqlalchemy import text

    def _seed(sql: str, params: dict | None = None):
        async def _run():
            async with async_db_engine.begin() as conn:
                await conn.execute(text(sql), params or {})

        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())
        loop.close()

    return _seed


@pytest.fixture
def sample_feature_engineer():
    """Returns a FeatureEngineer instance."""
    from app.ml.features.engineer import FeatureEngineer
    return FeatureEngineer()


@pytest.fixture
def sample_feature_scaler():
    """Returns a fitted FeatureScaler instance."""
    from app.ml.features.scaler import FeatureScaler
    scaler = FeatureScaler(n_features=37)
    rng = np.random.RandomState(42)
    scaler.partial_fit(rng.randn(50, 37).astype(np.float32))
    return scaler
