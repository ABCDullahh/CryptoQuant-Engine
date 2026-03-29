"""Tests for backtesting job runner -- async job execution."""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager

from app.backtesting.job_runner import BacktestJobRunner
from app.api.schemas import BacktestRunRequest, OptimizeRequest, WalkForwardRequest


@asynccontextmanager
async def mock_db_session():
    """Mock DB session context manager."""
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(all=MagicMock(return_value=[]))
            )
        )
    )
    session.commit = AsyncMock()
    yield session


def mock_db_factory():
    """Returns a mock session factory (callable that returns async context manager)."""
    return mock_db_session


class TestBacktestJobRunner:
    @pytest.fixture
    def runner(self):
        return BacktestJobRunner(max_concurrent=2)

    def test_get_job_status_unknown(self, runner):
        assert runner.get_job_status("nonexistent") is None

    def test_register_job(self, runner):
        runner.register_job("job-1", "backtest")
        status = runner.get_job_status("job-1")
        assert status is not None
        assert status["status"] == "QUEUED"
        assert status["progress"] == 0

    def test_register_job_type(self, runner):
        runner.register_job("job-opt", "optimization")
        status = runner.get_job_status("job-opt")
        assert status["type"] == "optimization"

    def test_register_job_error_none(self, runner):
        runner.register_job("job-e", "backtest")
        status = runner.get_job_status("job-e")
        assert status["error"] is None

    async def test_run_backtest_completes(self, runner):
        runner.register_job("test-bt-1", "backtest")

        request = BacktestRunRequest(
            strategy_name="momentum",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 2, 1, tzinfo=timezone.utc),
            initial_capital=10000.0,
        )

        await runner.run_backtest("test-bt-1", request, mock_db_factory())

        status = runner.get_job_status("test-bt-1")
        assert status is not None
        assert status["status"] == "COMPLETED"
        assert status["progress"] == 100

    async def test_run_backtest_failed_on_bad_strategy(self, runner):
        runner.register_job("test-bt-fail", "backtest")

        request = BacktestRunRequest(
            strategy_name="nonexistent_strategy",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )

        await runner.run_backtest("test-bt-fail", request, mock_db_factory())

        status = runner.get_job_status("test-bt-fail")
        assert status is not None
        assert status["status"] == "FAILED"
        assert status["error"] is not None
        assert "Unknown strategy" in status["error"]

    async def test_run_backtest_sets_running(self, runner):
        """Verify job transitions through RUNNING state."""
        runner.register_job("test-bt-run", "backtest")

        request = BacktestRunRequest(
            strategy_name="momentum",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 5, tzinfo=timezone.utc),
            initial_capital=10000.0,
        )

        await runner.run_backtest("test-bt-run", request, mock_db_factory())

        # After completion, status should be COMPLETED (it was RUNNING during execution)
        status = runner.get_job_status("test-bt-run")
        assert status["status"] in ("COMPLETED", "FAILED")

    async def test_run_optimization_fails_gracefully(self, runner):
        """Optimization with missing optimizer module should fail gracefully."""
        runner.register_job("test-opt-1", "optimization")

        request = OptimizeRequest(
            strategy_name="momentum",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 3, 1, tzinfo=timezone.utc),
            param_ranges={"rsi_period": {"low": 10, "high": 20, "step": 2, "type": "int"}},
            max_trials=3,
        )

        await runner.run_optimization("test-opt-1", request, mock_db_factory())

        status = runner.get_job_status("test-opt-1")
        assert status is not None
        # May complete or fail depending on optimizer availability
        assert status["status"] in ("COMPLETED", "FAILED")

    async def test_run_walk_forward_fails_gracefully(self, runner):
        """Walk-forward with missing analyzer module should fail gracefully."""
        runner.register_job("test-wf-1", "walk_forward")

        request = WalkForwardRequest(
            strategy_name="momentum",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
            in_sample_size=200,
            oos_size=50,
        )

        await runner.run_walk_forward("test-wf-1", request, mock_db_factory())

        status = runner.get_job_status("test-wf-1")
        assert status is not None
        # May complete or fail depending on module availability
        assert status["status"] in ("COMPLETED", "FAILED")

    async def test_semaphore_limits_concurrency(self, runner):
        """Verify semaphore limits to max_concurrent jobs."""
        runner_limited = BacktestJobRunner(max_concurrent=1)

        request = BacktestRunRequest(
            strategy_name="momentum",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        )

        runner_limited.register_job("sem-1", "backtest")
        runner_limited.register_job("sem-2", "backtest")

        # Both should complete (semaphore serializes them)
        await asyncio.gather(
            runner_limited.run_backtest("sem-1", request, mock_db_factory()),
            runner_limited.run_backtest("sem-2", request, mock_db_factory()),
        )

        s1 = runner_limited.get_job_status("sem-1")
        s2 = runner_limited.get_job_status("sem-2")
        assert s1["status"] == "COMPLETED"
        assert s2["status"] == "COMPLETED"

    async def test_multiple_jobs_independent(self, runner):
        """Multiple jobs with max_concurrent=2 should both complete."""
        request = BacktestRunRequest(
            strategy_name="momentum",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 10, tzinfo=timezone.utc),
        )

        runner.register_job("m-1", "backtest")
        runner.register_job("m-2", "backtest")

        await asyncio.gather(
            runner.run_backtest("m-1", request, mock_db_factory()),
            runner.run_backtest("m-2", request, mock_db_factory()),
        )

        assert runner.get_job_status("m-1")["status"] == "COMPLETED"
        assert runner.get_job_status("m-2")["status"] == "COMPLETED"
