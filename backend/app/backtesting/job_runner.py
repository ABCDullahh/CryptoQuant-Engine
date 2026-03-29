"""Async backtest job runner — executes backtest engine in background tasks."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.api.schemas import BacktestRunRequest, OptimizeRequest, WalkForwardRequest
from app.backtesting.data_loader import load_candles, normalize_symbol
from app.backtesting.strategy_factory import create_strategies
from app.core.events import event_bus
from app.core.models import BacktestConfig

logger = structlog.get_logger(__name__)


async def _publish_progress(job_id: str, progress: int, status: str) -> None:
    """Publish backtest progress event through EventBus."""
    try:
        await event_bus.publish_raw(
            "backtest.progress",
            {"job_id": job_id, "progress": progress, "status": status},
        )
    except Exception as exc:
        logger.debug("backtest.progress_publish_failed", error=str(exc))


class BacktestJobRunner:
    """Manages async backtest job execution with concurrency control."""

    def __init__(self, max_concurrent: int = 2):
        self._jobs: dict[str, dict[str, Any]] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get current status of a job."""
        return self._jobs.get(job_id)

    def register_job(self, job_id: str, job_type: str = "backtest") -> None:
        """Register a new job in QUEUED state."""
        self._jobs[job_id] = {
            "status": "QUEUED",
            "progress": 0,
            "type": job_type,
            "error": None,
        }

    async def run_backtest(
        self,
        job_id: str,
        request: BacktestRunRequest,
        db_factory,
    ) -> None:
        """Run a backtest job asynchronously."""
        async with self._semaphore:
            self._jobs[job_id] = {
                "status": "RUNNING",
                "progress": 10,
                "type": "backtest",
                "error": None,
            }
            await _publish_progress(job_id, 10, "RUNNING")

            try:
                # 1. Load candle data
                async with db_factory() as session:
                    candles = await load_candles(
                        symbol=request.symbol,
                        timeframe=request.timeframe,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        db_session=session,
                    )

                if not candles:
                    raise ValueError("No candle data available for the specified period")

                self._jobs[job_id]["progress"] = 30
                await _publish_progress(job_id, 30, "RUNNING")

                # 2. Create strategies
                strategies = create_strategies(request.strategy_name, request.parameters)

                # 3. Build config
                config = BacktestConfig(
                    strategy_name=request.strategy_name,
                    symbol=normalize_symbol(request.symbol),
                    timeframe=request.timeframe,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    initial_capital=request.initial_capital,
                    risk_per_trade=getattr(request, "risk_per_trade", 0.02),
                    max_positions=getattr(request, "max_positions", 5),
                    slippage_bps=request.slippage_bps,
                    taker_fee=request.taker_fee,
                    parameters=request.parameters,
                )

                self._jobs[job_id]["progress"] = 40
                await _publish_progress(job_id, 40, "RUNNING")

                # 4. Run engine in thread (CPU-bound)
                from app.backtesting.engine import BacktestEngine

                engine = BacktestEngine(strategies, config)
                result = await asyncio.to_thread(engine.run, candles)

                self._jobs[job_id]["progress"] = 80
                await _publish_progress(job_id, 80, "RUNNING")

                # 5. Persist to DB
                async with db_factory() as session:
                    from sqlalchemy import update
                    from app.db.models import BacktestRunModel

                    stmt = (
                        update(BacktestRunModel)
                        .where(BacktestRunModel.id == job_id)
                        .values(
                            status="COMPLETED",
                            final_capital=config.initial_capital + (config.initial_capital * result.total_return),
                            total_return=result.total_return,
                            sharpe_ratio=result.sharpe_ratio,
                            sortino_ratio=result.sortino_ratio,
                            max_drawdown=result.max_drawdown,
                            win_rate=result.win_rate,
                            profit_factor=result.profit_factor,
                            total_trades=result.total_trades,
                            annual_return=result.annual_return,
                            expectancy=result.expectancy,
                            avg_win=result.avg_win,
                            avg_loss=result.avg_loss,
                            calmar_ratio=result.calmar_ratio,
                            avg_holding_period=float(result.avg_holding_period.split()[0]) if result.avg_holding_period and result.avg_holding_period[0].isdigit() else 0,
                            equity_curve=result.equity_curve,
                            trades=result.trades,
                        )
                    )
                    await session.execute(stmt)
                    await session.commit()

                self._jobs[job_id] = {
                    "status": "COMPLETED",
                    "progress": 100,
                    "type": "backtest",
                    "error": None,
                }
                await _publish_progress(job_id, 100, "COMPLETED")
                logger.info("backtest.completed", job_id=job_id, trades=result.total_trades)

            except Exception as exc:
                error_msg = str(exc)
                logger.error("backtest.failed", job_id=job_id, error=error_msg)
                self._jobs[job_id] = {
                    "status": "FAILED",
                    "progress": 0,
                    "type": "backtest",
                    "error": error_msg,
                }
                await _publish_progress(job_id, 0, "FAILED")
                # Persist error to DB
                try:
                    async with db_factory() as session:
                        from sqlalchemy import update
                        from app.db.models import BacktestRunModel

                        stmt = (
                            update(BacktestRunModel)
                            .where(BacktestRunModel.id == job_id)
                            .values(status="FAILED", error_message=error_msg)
                        )
                        await session.execute(stmt)
                        await session.commit()
                except Exception as exc:
                    logger.warning("backtest.failed_status_update_error", error=str(exc))

    async def run_optimization(
        self,
        job_id: str,
        request: OptimizeRequest,
        db_factory,
    ) -> None:
        """Run an optimization job asynchronously."""
        async with self._semaphore:
            self._jobs[job_id] = {
                "status": "RUNNING",
                "progress": 10,
                "type": "optimization",
                "error": None,
            }

            try:
                async with db_factory() as session:
                    candles = await load_candles(
                        symbol=request.symbol,
                        timeframe=request.timeframe,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        db_session=session,
                    )

                if not candles:
                    raise ValueError("No candle data available")

                config = BacktestConfig(
                    strategy_name=request.strategy_name,
                    symbol=normalize_symbol(request.symbol),
                    timeframe=request.timeframe,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    initial_capital=request.initial_capital,
                )

                from app.backtesting.optimizer import StrategyOptimizer, ParamSpace

                param_spaces = []
                for name, spec in request.param_ranges.items():
                    param_spaces.append(ParamSpace(
                        name=name,
                        low=float(spec.get("low", 0)),
                        high=float(spec.get("high", 100)),
                        step=float(spec["step"]) if "step" in spec else None,
                        param_type=str(spec.get("type", "float")),
                    ))

                def strategy_factory(params):
                    return create_strategies(request.strategy_name, params)

                optimizer = StrategyOptimizer(
                    strategy_factory=strategy_factory,
                    config=config,
                    param_spaces=param_spaces,
                    n_trials=request.max_trials,
                    objective=request.optimization_metric.replace("_ratio", ""),
                )

                opt_result = await asyncio.to_thread(optimizer.optimize, candles)

                self._jobs[job_id] = {
                    "status": "COMPLETED",
                    "progress": 100,
                    "type": "optimization",
                    "error": None,
                    "result": {
                        "best_params": opt_result.best_params,
                        "best_sharpe": opt_result.best_sharpe,
                        "n_trials": opt_result.n_trials,
                        "n_feasible": opt_result.n_feasible,
                    },
                }
                logger.info("optimization.completed", job_id=job_id)

            except Exception as exc:
                self._jobs[job_id] = {
                    "status": "FAILED",
                    "progress": 0,
                    "type": "optimization",
                    "error": str(exc),
                }

    async def run_walk_forward(
        self,
        job_id: str,
        request: WalkForwardRequest,
        db_factory,
    ) -> None:
        """Run a walk-forward analysis job asynchronously."""
        async with self._semaphore:
            self._jobs[job_id] = {
                "status": "RUNNING",
                "progress": 10,
                "type": "walk_forward",
                "error": None,
            }

            try:
                async with db_factory() as session:
                    candles = await load_candles(
                        symbol=request.symbol,
                        timeframe=request.timeframe,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        db_session=session,
                    )

                if not candles:
                    raise ValueError("No candle data available")

                strategies = create_strategies(request.strategy_name)

                config = BacktestConfig(
                    strategy_name=request.strategy_name,
                    symbol=normalize_symbol(request.symbol),
                    timeframe=request.timeframe,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    initial_capital=request.initial_capital,
                )

                from app.backtesting.walk_forward import WalkForwardAnalyzer

                analyzer = WalkForwardAnalyzer(
                    strategies=strategies,
                    config=config,
                    in_sample_size=request.in_sample_size,
                    oos_size=request.oos_size,
                )

                wf_result = await asyncio.to_thread(analyzer.analyze, candles)

                self._jobs[job_id] = {
                    "status": "COMPLETED",
                    "progress": 100,
                    "type": "walk_forward",
                    "error": None,
                    "result": {
                        "n_windows": wf_result.n_windows,
                        "avg_oos_return": wf_result.avg_oos_return,
                        "avg_oos_sharpe": wf_result.avg_oos_sharpe,
                        "consistency_score": wf_result.consistency_score,
                        "avg_efficiency_ratio": wf_result.avg_efficiency_ratio,
                    },
                }
                logger.info("walkforward.completed", job_id=job_id)

            except Exception as exc:
                self._jobs[job_id] = {
                    "status": "FAILED",
                    "progress": 0,
                    "type": "walk_forward",
                    "error": str(exc),
                }


# Module-level singleton
job_runner = BacktestJobRunner()
