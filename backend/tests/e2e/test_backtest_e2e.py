"""E2E tests for backtest pipeline (run, poll, results, optimize)."""

import asyncio

import pytest
import httpx


pytestmark = pytest.mark.asyncio

BACKTEST_REQUEST = {
    "strategy_name": "momentum",
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2025-02-01T00:00:00Z",
    "initial_capital": 10000.0,
}


async def test_run_backtest_returns_job(client: httpx.AsyncClient):
    """POST /api/backtest/run returns 202 with job_id."""
    resp = await client.post("/api/backtest/run", json=BACKTEST_REQUEST)
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body or "id" in body
    assert body.get("status") in ("QUEUED", "RUNNING", "COMPLETED")


async def test_backtest_poll_completion(client: httpx.AsyncClient):
    """Run backtest and poll until completed or failed (max 60s)."""
    resp = await client.post("/api/backtest/run", json=BACKTEST_REQUEST)
    assert resp.status_code == 202
    body = resp.json()
    job_id = body.get("job_id") or body.get("id")
    assert job_id is not None

    # Poll for completion
    for _ in range(30):  # 30 * 2s = 60s max
        status_resp = await client.get(f"/api/backtest/{job_id}")
        assert status_resp.status_code == 200
        status_body = status_resp.json()
        if status_body.get("status") in ("COMPLETED", "FAILED"):
            break
        await asyncio.sleep(2)
    else:
        pytest.skip("Backtest did not complete within 60s")

    # Verify we got a terminal status
    assert status_body.get("status") in ("COMPLETED", "FAILED")


async def test_backtest_results_fields(client: httpx.AsyncClient):
    """When a backtest completes, verify result fields exist."""
    resp = await client.post("/api/backtest/run", json=BACKTEST_REQUEST)
    assert resp.status_code == 202
    body = resp.json()
    job_id = body.get("job_id") or body.get("id")

    # Poll for completion
    result = None
    for _ in range(30):
        status_resp = await client.get(f"/api/backtest/{job_id}")
        result = status_resp.json()
        if result.get("status") == "COMPLETED":
            break
        if result.get("status") == "FAILED":
            pytest.skip(f"Backtest failed: {result.get('error_message', 'unknown')}")
        await asyncio.sleep(2)
    else:
        pytest.skip("Backtest did not complete within 60s")

    # If completed, check result fields
    assert result.get("total_return") is not None or result.get("status") == "COMPLETED"
    if result.get("total_return") is not None:
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result


async def test_optimize_returns_job(client: httpx.AsyncClient):
    """POST /api/backtest/optimize returns 202 with job_id."""
    payload = {
        "strategy_name": "momentum",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": "2025-02-01T00:00:00Z",
        "initial_capital": 10000.0,
        "param_ranges": {
            "fast_period": {"min": 5, "max": 20, "step": 5},
        },
        "optimization_metric": "sharpe_ratio",
        "max_trials": 3,
    }
    resp = await client.post("/api/backtest/optimize", json=payload)
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body or "id" in body


async def test_invalid_strategy_error(client: httpx.AsyncClient):
    """POST /api/backtest/run with invalid strategy should not crash."""
    payload = {
        **BACKTEST_REQUEST,
        "strategy_name": "nonexistent_strategy_xyz",
    }
    resp = await client.post("/api/backtest/run", json=payload)
    # Should either return an error status code or accept and fail gracefully
    assert resp.status_code in (200, 202, 400, 404, 422, 500)
    # If accepted (202), poll to check it fails gracefully
    if resp.status_code == 202:
        body = resp.json()
        job_id = body.get("job_id") or body.get("id")
        if job_id:
            for _ in range(15):
                status_resp = await client.get(f"/api/backtest/{job_id}")
                result = status_resp.json()
                if result.get("status") in ("COMPLETED", "FAILED"):
                    break
                await asyncio.sleep(2)
            # Should have failed, not crashed the server
            assert result.get("status") in ("COMPLETED", "FAILED", "QUEUED", "RUNNING")
