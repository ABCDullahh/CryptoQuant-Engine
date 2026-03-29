"""CryptoQuant Engine — FastAPI application entry point."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.schemas import (
    ComponentHealth,
    DetailedHealthResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
)
from app.config.settings import get_settings

logger = structlog.get_logger(__name__)

_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    import os

    global _start_time
    _start_time = time.time()
    is_testing = os.environ.get("TESTING") == "true"
    logger.info("app.starting", host=get_settings().api_host, port=get_settings().api_port)

    # Initialize database tables
    try:
        from app.db.database import init_db
        logger.info("db.initializing")
        await init_db()
        logger.info("db.tables_created")
    except Exception as exc:
        logger.warning("db.init_failed", error=str(exc))

    # Create TimescaleDB hypertable (best-effort — only works with actual TimescaleDB)
    try:
        from app.db.database import init_timescale_hypertables
        await init_timescale_hypertables()
        logger.info("db.hypertables_created")
    except Exception:
        logger.warning("db.hypertables_skipped")

    # Ensure ml_models directory exists
    os.makedirs(get_settings().ml_models_dir, exist_ok=True)

    # Skip real-time services during testing (they connect to Binance/Redis and loop forever)
    if not is_testing:
        # Start WebSocket-EventBus bridge (best-effort; skip if Redis unavailable)
        try:
            from app.api.ws_bridge import start_ws_bridge, stop_ws_bridge
            await start_ws_bridge()
            # Start the EventBus listener so ws_bridge handlers receive Redis pub/sub events
            from app.core.events import event_bus
            await event_bus.start()
        except Exception:
            logger.warning("ws_bridge.start_failed")

        # Start system status real-time monitor
        try:
            from app.api.routes.system import start_system_monitor
            await start_system_monitor()
        except Exception:
            logger.warning("system_monitor.start_failed")

        # Start real-time price streamer (independent of bot)
        try:
            from app.services.price_streamer import start_price_streamer
            await start_price_streamer()
        except Exception:
            logger.warning("price_streamer.start_failed")

        # Start real-time order book streamer
        try:
            from app.services.orderbook_streamer import start_orderbook_streamer
            await start_orderbook_streamer()
        except Exception:
            logger.warning("orderbook_streamer.start_failed")
    else:
        logger.info("app.testing_mode", skip="real-time services")

    yield

    # Stop system monitor
    try:
        from app.api.routes.system import stop_system_monitor
        await stop_system_monitor()
    except Exception as exc:
        logger.warning("shutdown.system_monitor_failed", error=str(exc))

    # Stop price streamer
    try:
        from app.services.price_streamer import stop_price_streamer
        await stop_price_streamer()
    except Exception as exc:
        logger.warning("shutdown.price_streamer_failed", error=str(exc))

    # Stop orderbook streamer
    try:
        from app.services.orderbook_streamer import stop_orderbook_streamer
        await stop_orderbook_streamer()
    except Exception as exc:
        logger.warning("shutdown.orderbook_streamer_failed", error=str(exc))

    # Stop bot service if running
    try:
        from app.bot.service import bot_service
        await bot_service.stop()
    except Exception as exc:
        logger.warning("shutdown.bot_failed", error=str(exc))

    try:
        from app.api.ws_bridge import stop_ws_bridge
        await stop_ws_bridge()
    except Exception as exc:
        logger.warning("shutdown.ws_bridge_failed", error=str(exc))

    # Close database and Redis connections
    try:
        from app.db.database import close_db
        from app.db.redis_client import close_redis
        await close_db()
        await close_redis()
        logger.info("connections.closed")
    except Exception:
        logger.warning("connections.close_failed")

    logger.info("app.shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="CryptoQuant Engine",
        description="Crypto Quantitative Trading Platform API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Rate limiting (must be added before CORS so it runs after CORS in the middleware stack)
    from app.api.middleware import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    # Import and include routers
    from app.api.routes.signals import router as signals_router
    from app.api.routes.orders import router as orders_router
    from app.api.routes.positions import router as positions_router
    from app.api.routes.bot import router as bot_router
    from app.api.routes.backtest import router as backtest_router
    from app.api.routes.settings import router as settings_router
    from app.api.routes.candles import router as candles_router
    from app.api.routes.auth import router as auth_router
    from app.api.routes.system import router as system_router
    from app.api.routes.markets import router as markets_router
    from app.api.routes.indicators import router as indicators_router
    from app.api.routes.metadata import router as metadata_router
    from app.api.routes.wallet import router as wallet_router
    from app.api.routes.analytics import router as analytics_router

    app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
    app.include_router(system_router, prefix="/api/system", tags=["System"])
    app.include_router(signals_router, prefix="/api/signals", tags=["Signals"])
    app.include_router(orders_router, prefix="/api/orders", tags=["Orders"])
    app.include_router(positions_router, prefix="/api/positions", tags=["Positions"])
    app.include_router(bot_router, prefix="/api/bot", tags=["Auto-Bot"])
    app.include_router(backtest_router, prefix="/api/backtest", tags=["Backtest"])
    app.include_router(settings_router, prefix="/api/settings", tags=["Settings"])
    app.include_router(candles_router, prefix="/api/candles", tags=["Candles"])
    app.include_router(markets_router, prefix="/api/markets", tags=["Markets"])
    app.include_router(indicators_router, prefix="/api/indicators", tags=["Indicators"])
    app.include_router(metadata_router, prefix="/api/metadata", tags=["Metadata"])
    app.include_router(wallet_router, prefix="/api/wallet", tags=["Wallet"])
    app.include_router(analytics_router, prefix="/api/analytics", tags=["Analytics"])

    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket, token: str | None = None):
        from app.api.websocket import ws_manager
        await ws_manager.handle_client(websocket, token=token)

    # Health check
    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        uptime = time.time() - _start_time if _start_time else 0
        return HealthResponse(uptime_seconds=round(uptime, 1))

    @app.get("/health/detailed", response_model=DetailedHealthResponse, tags=["System"])
    async def detailed_health_check():
        """Detailed health check with component diagnostics."""
        uptime = time.time() - _start_time if _start_time else 0
        components: dict[str, ComponentHealth] = {}
        overall_ok = True

        # Check database
        try:
            t0 = time.time()
            from app.db.database import engine as async_engine
            from sqlalchemy import text
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_ms = round((time.time() - t0) * 1000, 1)
            components["database"] = ComponentHealth(status="ok", latency_ms=db_ms)
        except Exception as exc:
            logger.warning("health.database_check_failed", error=str(exc))
            components["database"] = ComponentHealth(status="error", message="Service unavailable")
            overall_ok = False

        # Check Redis
        try:
            t0 = time.time()
            from app.db.redis_client import get_redis
            redis = await get_redis()
            await redis.ping()
            redis_ms = round((time.time() - t0) * 1000, 1)
            components["redis"] = ComponentHealth(status="ok", latency_ms=redis_ms)
        except Exception as exc:
            logger.warning("health.redis_check_failed", error=str(exc))
            components["redis"] = ComponentHealth(status="error", message="Service unavailable")
            overall_ok = False

        # Check bot service
        try:
            from app.bot.service import bot_service
            bot_st = bot_service.status
            components["bot"] = ComponentHealth(status="ok", message=bot_st)
        except Exception as exc:
            logger.warning("health.bot_check_failed", error=str(exc))
            bot_st = "UNKNOWN"
            components["bot"] = ComponentHealth(status="error", message="Service unavailable")

        return DetailedHealthResponse(
            status="ok" if overall_ok else "degraded",
            uptime_seconds=round(uptime, 1),
            environment=settings.environment,
            trading_enabled=settings.trading_enabled,
            bot_status=bot_st,
            components=components,
        )

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("unhandled_error", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(code="INTERNAL_ERROR", message="An internal error occurred")
            ).model_dump(),
        )

    return app


# Module-level app instance for uvicorn
app = create_app()
