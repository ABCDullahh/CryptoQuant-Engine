"""System status and diagnostics endpoints + real-time monitor."""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text

from app.api.dependencies import get_current_user, get_db
from app.api.schemas import (
    ComponentStatusDetail,
    DataFreshness,
    PingResponse,
    SystemInfo,
    SystemStatusResponse,
)
from app.config.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Background monitor state
# ---------------------------------------------------------------------------

_monitor_task: asyncio.Task | None = None


# ---------------------------------------------------------------------------
# Shared collection logic
# ---------------------------------------------------------------------------


async def _collect_system_status(
    db_session=None,
) -> dict:
    """Collect comprehensive system status. Returns dict matching SystemStatusResponse."""
    settings = get_settings()
    components: list[dict] = []
    overall_ok = True
    has_degraded = False

    # 1. Database check
    try:
        t0 = time.time()
        from app.db.database import engine as async_engine

        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ms = round((time.time() - t0) * 1000, 1)

        # Pool stats (QueuePool has these methods)
        pool_details: dict = {}
        try:
            pool = async_engine.pool
            pool_details = {
                "pool_size": pool.size(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "checked_in": pool.checkedin(),
            }
        except Exception as exc:
            logger.debug("health.pool_info_failed", error=str(exc))

        components.append({
            "name": "database",
            "status": "ok",
            "latency_ms": db_ms,
            "message": "Connected",
            "details": pool_details,
        })
    except Exception as exc:
        logger.warning("health.database_check_failed", error=str(exc))
        components.append({
            "name": "database",
            "status": "error",
            "latency_ms": None,
            "message": "Service unavailable",
            "details": {},
        })
        overall_ok = False

    # 2. Redis check
    try:
        t0 = time.time()
        from app.db.redis_client import get_redis

        redis = await get_redis()
        await redis.ping()
        redis_ms = round((time.time() - t0) * 1000, 1)

        redis_details: dict = {}
        try:
            mem_info = await redis.info("memory")
            client_info = await redis.info("clients")
            redis_details = {
                "used_memory": mem_info.get("used_memory_human", "N/A"),
                "peak_memory": mem_info.get("used_memory_peak_human", "N/A"),
                "connected_clients": client_info.get("connected_clients", 0),
            }
        except Exception as exc:
            logger.debug("health.redis_details_failed", error=str(exc))

        components.append({
            "name": "redis",
            "status": "ok",
            "latency_ms": redis_ms,
            "message": "Connected",
            "details": redis_details,
        })
    except Exception as exc:
        logger.warning("health.redis_check_failed", error=str(exc))
        components.append({
            "name": "redis",
            "status": "error",
            "latency_ms": None,
            "message": "Service unavailable",
            "details": {},
        })
        overall_ok = False

    # 3. Binance exchange check (best-effort)
    try:
        t0 = time.time()
        import ccxt.async_support as ccxt_async

        exchange = ccxt_async.binanceusdm({"enableRateLimit": True})
        server_time = await exchange.fetch_time()
        exchange_ms = round((time.time() - t0) * 1000, 1)
        await exchange.close()

        components.append({
            "name": "exchange",
            "status": "ok",
            "latency_ms": exchange_ms,
            "message": "Binance USDM reachable",
            "details": {
                "testnet": settings.binance_testnet,
                "api_configured": bool(settings.binance_api_key),
            },
        })
    except Exception as exc:
        logger.warning("health.exchange_check_failed", error=str(exc))
        has_degraded = True
        components.append({
            "name": "exchange",
            "status": "degraded",
            "latency_ms": None,
            "message": "Exchange unreachable",
            "details": {"testnet": settings.binance_testnet},
        })

    # 4. WebSocket status
    try:
        from app.api.websocket import ws_manager

        ws_count = ws_manager.active_count
        components.append({
            "name": "websocket",
            "status": "ok",
            "latency_ms": None,
            "message": f"{ws_count} active connection(s)",
            "details": {"active_connections": ws_count},
        })
    except Exception as exc:
        logger.warning("health.websocket_check_failed", error=str(exc))
        components.append({
            "name": "websocket",
            "status": "error",
            "latency_ms": None,
            "message": "Service unavailable",
            "details": {},
        })

    # 5. Bot service status
    try:
        from app.bot.service import bot_service

        bot_st = str(bot_service.status)
        components.append({
            "name": "bot_service",
            "status": "ok",
            "latency_ms": None,
            "message": bot_st,
            "details": {
                "has_collector": bot_service.collector is not None,
                "has_executor": bot_service.executor is not None,
            },
        })
    except Exception as exc:
        logger.warning("health.bot_service_check_failed", error=str(exc))
        components.append({
            "name": "bot_service",
            "status": "error",
            "latency_ms": None,
            "message": "Service unavailable",
            "details": {},
        })

    # --- Data Freshness ---
    freshness: dict = {
        "latest_candle_time": None,
        "latest_signal_time": None,
        "candle_count": 0,
        "signal_count": 0,
        "candle_age_seconds": None,
        "signal_age_seconds": None,
    }

    if db_session:
        try:
            from app.db.models import CandleModel, SignalModel

            result = await db_session.execute(
                select(func.max(CandleModel.time), func.count()).select_from(CandleModel)
            )
            row = result.one()
            if row[0]:
                freshness["latest_candle_time"] = row[0].isoformat()
                freshness["candle_age_seconds"] = round(
                    (datetime.now(tz=UTC) - row[0]).total_seconds(), 1
                )
            freshness["candle_count"] = row[1] or 0

            result = await db_session.execute(
                select(func.max(SignalModel.created_at), func.count()).select_from(
                    SignalModel
                )
            )
            row = result.one()
            if row[0]:
                freshness["latest_signal_time"] = row[0].isoformat()
                freshness["signal_age_seconds"] = round(
                    (datetime.now(tz=UTC) - row[0]).total_seconds(), 1
                )
            freshness["signal_count"] = row[1] or 0
        except Exception:
            logger.warning("system.data_freshness_check_failed")
    else:
        # Background monitor: use own session
        try:
            from app.db.database import async_session_factory

            async with async_session_factory() as session:
                from app.db.models import CandleModel, SignalModel

                result = await session.execute(
                    select(func.max(CandleModel.time), func.count()).select_from(
                        CandleModel
                    )
                )
                row = result.one()
                if row[0]:
                    freshness["latest_candle_time"] = row[0].isoformat()
                    freshness["candle_age_seconds"] = round(
                        (datetime.now(tz=UTC) - row[0]).total_seconds(), 1
                    )
                freshness["candle_count"] = row[1] or 0

                result = await session.execute(
                    select(func.max(SignalModel.created_at), func.count()).select_from(
                        SignalModel
                    )
                )
                row = result.one()
                if row[0]:
                    freshness["latest_signal_time"] = row[0].isoformat()
                    freshness["signal_age_seconds"] = round(
                        (datetime.now(tz=UTC) - row[0]).total_seconds(), 1
                    )
                freshness["signal_count"] = row[1] or 0
        except Exception as exc:
            logger.debug("health.signal_freshness_failed", error=str(exc))

    # --- System Info ---
    from app.main import _start_time

    uptime = time.time() - _start_time if _start_time else 0
    sys_info = {
        "uptime_seconds": round(uptime, 1),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "environment": settings.environment,
        "trading_enabled": settings.trading_enabled,
        "version": "0.1.0",
        "started_at": (
            datetime.fromtimestamp(_start_time, tz=UTC).isoformat()
            if _start_time
            else None
        ),
    }

    # --- Overall status ---
    if not overall_ok:
        overall_status = "offline"
    elif has_degraded:
        overall_status = "degraded"
    else:
        overall_status = "ready"

    return {
        "overall_status": overall_status,
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "components": components,
        "data_freshness": freshness,
        "system_info": sys_info,
    }


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    db=Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Comprehensive system status with component health, data freshness, and system info."""
    data = await _collect_system_status(db_session=db)
    return SystemStatusResponse(**data)


@router.get("/ping", response_model=PingResponse)
async def ping():
    """Simple ping endpoint for client-side RTT measurement. No auth required."""
    now = datetime.now(tz=UTC)
    return PingResponse(
        timestamp=time.time(),
        server_time=now.isoformat(),
    )


# ---------------------------------------------------------------------------
# Real-time background monitor
# ---------------------------------------------------------------------------


async def _system_monitor_loop() -> None:
    """Background loop — measures all component health every 2s and broadcasts via WebSocket."""
    # Wait a moment for app to fully start
    await asyncio.sleep(3)
    logger.info("system_monitor.started")

    while True:
        try:
            status_data = await _collect_system_status()
            from app.api.websocket import ws_manager

            if ws_manager.active_count > 0:
                await ws_manager.broadcast(
                    {"type": "system_status", "data": status_data}
                )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug("system_monitor.error", error=str(exc))
        await asyncio.sleep(2)

    logger.info("system_monitor.stopped")


async def start_system_monitor() -> None:
    """Start the system status monitor background task."""
    global _monitor_task
    _monitor_task = asyncio.create_task(_system_monitor_loop())


async def stop_system_monitor() -> None:
    """Stop the system status monitor background task."""
    global _monitor_task
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()
        try:
            await _monitor_task
        except asyncio.CancelledError:
            pass
    _monitor_task = None
