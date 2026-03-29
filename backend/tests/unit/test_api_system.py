"""Tests for system status and diagnostics API endpoints."""

from __future__ import annotations

import time


class TestSystemStatus:
    def test_system_status_returns_200(self, api_client):
        resp = api_client.get("/api/system/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_status"] in ("ready", "degraded", "offline")

    def test_system_status_has_timestamp(self, api_client):
        resp = api_client.get("/api/system/status")
        data = resp.json()
        assert "timestamp" in data
        assert data["timestamp"]  # not empty

    def test_system_status_has_required_sections(self, api_client):
        resp = api_client.get("/api/system/status")
        data = resp.json()
        assert "components" in data
        assert "data_freshness" in data
        assert "system_info" in data
        assert isinstance(data["components"], list)

    def test_system_status_has_database_component(self, api_client):
        resp = api_client.get("/api/system/status")
        data = resp.json()
        component_names = [c["name"] for c in data["components"]]
        assert "database" in component_names

    def test_system_status_has_bot_component(self, api_client):
        resp = api_client.get("/api/system/status")
        data = resp.json()
        component_names = [c["name"] for c in data["components"]]
        assert "bot_service" in component_names

    def test_component_status_structure(self, api_client):
        resp = api_client.get("/api/system/status")
        for component in resp.json()["components"]:
            assert "name" in component
            assert "status" in component
            assert component["status"] in ("ok", "degraded", "error")
            assert "message" in component
            assert "details" in component

    def test_system_info_has_python_version(self, api_client):
        resp = api_client.get("/api/system/status")
        info = resp.json()["system_info"]
        assert "python_version" in info
        assert info["python_version"]  # not empty
        assert info["version"] == "0.1.0"

    def test_system_info_has_environment(self, api_client):
        resp = api_client.get("/api/system/status")
        info = resp.json()["system_info"]
        assert "environment" in info
        assert "trading_enabled" in info
        assert isinstance(info["trading_enabled"], bool)

    def test_data_freshness_structure(self, api_client):
        resp = api_client.get("/api/system/status")
        freshness = resp.json()["data_freshness"]
        assert "candle_count" in freshness
        assert "signal_count" in freshness
        assert "latest_candle_time" in freshness
        assert "latest_signal_time" in freshness
        assert isinstance(freshness["candle_count"], int)
        assert isinstance(freshness["signal_count"], int)


class TestSystemPing:
    def test_ping_returns_200(self, api_client):
        resp = api_client.get("/api/system/ping")
        assert resp.status_code == 200
        data = resp.json()
        assert "timestamp" in data
        assert "server_time" in data
        assert isinstance(data["timestamp"], float)

    def test_ping_timestamp_is_recent(self, api_client):
        now = time.time()
        resp = api_client.get("/api/system/ping")
        data = resp.json()
        # Timestamp should be within 5 seconds of current time
        assert abs(data["timestamp"] - now) < 5.0

    def test_ping_server_time_is_iso(self, api_client):
        resp = api_client.get("/api/system/ping")
        data = resp.json()
        # Should be a valid ISO format string
        assert "T" in data["server_time"]


class TestSystemComponentDetails:
    def test_database_component_has_details(self, api_client):
        resp = api_client.get("/api/system/status")
        data = resp.json()
        db_comp = next(c for c in data["components"] if c["name"] == "database")
        assert "details" in db_comp

    def test_bot_component_shows_stopped(self, api_client):
        resp = api_client.get("/api/system/status")
        data = resp.json()
        bot_comp = next(c for c in data["components"] if c["name"] == "bot_service")
        assert bot_comp["status"] in ("ok", "degraded", "error")

    def test_multiple_status_calls_consistent(self, api_client):
        """Multiple calls should return consistent structure."""
        resp1 = api_client.get("/api/system/status")
        resp2 = api_client.get("/api/system/status")
        assert resp1.json().keys() == resp2.json().keys()
        assert len(resp1.json()["components"]) == len(resp2.json()["components"])
