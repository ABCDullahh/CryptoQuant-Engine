"""Tests for API dependencies — auth dependency injection.

Tests verify JWT-based authentication and optional_auth behavior.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import create_access_token
from app.api.dependencies import get_current_user, optional_auth


def _make_app():
    """Create a minimal app to test dependency injection."""
    app = FastAPI()

    @app.get("/protected")
    async def protected(user: str = pytest.importorskip("fastapi").Depends(get_current_user)):
        return {"user": user}

    @app.get("/optional")
    async def optional(user: str | None = pytest.importorskip("fastapi").Depends(optional_auth)):
        return {"user": user}

    return app


def _auth_header(username: str = "testuser") -> dict[str, str]:
    """Create a valid Authorization header with JWT."""
    token = create_access_token(subject=username)
    return {"Authorization": f"Bearer {token}"}


class TestGetCurrentUser:
    def test_rejects_missing_token(self):
        """No Authorization header should return 401."""
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 401
        assert "Missing" in resp.json()["detail"]

    def test_rejects_invalid_token(self):
        """Invalid JWT token should return 401."""
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/protected", headers={"Authorization": "Bearer bad-token"})
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    def test_accepts_valid_token(self):
        """Valid JWT token should return the username."""
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/protected", headers=_auth_header("alice"))
        assert resp.status_code == 200
        assert resp.json()["user"] == "alice"

    def test_rejects_bad_scheme(self):
        """Non-Bearer scheme should be rejected."""
        app = _make_app()
        client = TestClient(app)
        token = create_access_token(subject="alice")
        resp = client.get("/protected", headers={"Authorization": f"Basic {token}"})
        assert resp.status_code == 401


class TestOptionalAuth:
    def test_no_header_returns_none(self):
        """optional_auth returns None when no Authorization header."""
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/optional")
        assert resp.status_code == 200
        assert resp.json()["user"] is None

    def test_with_valid_token_returns_user(self):
        """optional_auth returns username with valid token."""
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/optional", headers=_auth_header("bob"))
        assert resp.status_code == 200
        assert resp.json()["user"] == "bob"

    def test_with_invalid_token_returns_none(self):
        """optional_auth returns None with invalid token (graceful)."""
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/optional", headers={"Authorization": "Bearer bad-token"})
        assert resp.status_code == 200
        assert resp.json()["user"] is None
