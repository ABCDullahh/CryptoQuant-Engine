"""E2E test fixtures -- requires running server at localhost:8000."""

import pytest
import httpx

E2E_BASE_URL = "http://localhost:8000"


@pytest.fixture
async def client():
    """Async HTTP client for E2E tests."""
    async with httpx.AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as c:
        yield c


@pytest.fixture(autouse=True)
async def check_server_running(client):
    """Skip E2E tests if server is not running."""
    try:
        resp = await client.get("/health")
        if resp.status_code != 200:
            pytest.skip("Backend server not running")
    except httpx.ConnectError:
        pytest.skip("Backend server not running at localhost:8000")
