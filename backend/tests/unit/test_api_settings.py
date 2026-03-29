"""Tests for settings API endpoints."""

from __future__ import annotations

import pytest


class TestGetSettings:
    def test_initial_settings(self, api_client):
        resp = api_client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "exchange" in data
        assert "risk_params" in data
        assert "notification_config" in data

    def test_default_risk_params(self, api_client):
        resp = api_client.get("/api/settings")
        data = resp.json()
        assert data["risk_params"]["default_risk_pct"] == 0.02
        assert data["risk_params"]["max_leverage"] == 10


class TestUpdateExchange:
    def test_update_keys(self, api_client):
        resp = api_client.put("/api/settings/exchange", json={
            "api_key": "test_key", "api_secret": "test_secret", "testnet": True
        })
        assert resp.status_code == 200
        assert resp.json()["testnet"] is True

    def test_verify_configured(self, api_client):
        api_client.put("/api/settings/exchange", json={
            "api_key": "key", "api_secret": "secret"
        })
        resp = api_client.get("/api/settings")
        assert resp.json()["exchange"]["configured"] is True


class TestUpdateRisk:
    def test_update_risk_partial(self, api_client):
        resp = api_client.put("/api/settings/risk", json={
            "default_risk_pct": 0.03, "max_leverage": 5
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_params"]["default_risk_pct"] == 0.03
        assert data["risk_params"]["max_leverage"] == 5

    def test_update_preserves_other_fields(self, api_client):
        api_client.get("/api/settings")
        api_client.put("/api/settings/risk", json={"max_drawdown": 0.20})
        resp = api_client.get("/api/settings")
        data = resp.json()
        assert data["risk_params"]["max_drawdown"] == 0.20
        assert data["risk_params"]["default_risk_pct"] == 0.02


class TestUpdateNotifications:
    def test_update_telegram(self, api_client):
        resp = api_client.put("/api/settings/notifications", json={
            "telegram_enabled": True,
            "telegram_chat_id": "123456",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["notification_config"]["telegram_enabled"] is True
        assert data["notification_config"]["telegram_chat_id"] == "123456"

    def test_update_discord(self, api_client):
        resp = api_client.put("/api/settings/notifications", json={
            "discord_enabled": True,
            "discord_webhook_url": "https://discord.com/api/webhooks/test",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["notification_config"]["discord_enabled"] is True

    def test_update_preserves_other_notification_fields(self, api_client):
        api_client.put("/api/settings/notifications", json={
            "telegram_enabled": True,
            "telegram_chat_id": "123456",
        })
        api_client.put("/api/settings/notifications", json={
            "discord_enabled": True,
        })
        resp = api_client.get("/api/settings")
        notif = resp.json()["notification_config"]
        assert notif["telegram_enabled"] is True
        assert notif["discord_enabled"] is True


class TestSettingsExchangeEncryption:
    def test_exchange_keys_are_masked(self, api_client):
        """After saving keys, GET /settings should show masked key."""
        api_client.put("/api/settings/exchange", json={
            "api_key": "my_key", "api_secret": "my_secret", "testnet": False
        })
        resp = api_client.get("/api/settings")
        assert resp.json()["exchange"]["api_key_masked"] == "***"
        assert resp.json()["exchange"]["configured"] is True
        assert resp.json()["exchange"]["source"] == "database"

    def test_exchange_not_configured_initially(self, api_client):
        resp = api_client.get("/api/settings")
        exchange = resp.json()["exchange"]
        # In test env, BINANCE_API_KEY is empty so env_configured=False
        # If env has a key, source would be "env" and configured=True
        if exchange.get("source") == "env":
            assert exchange["configured"] is True
            assert exchange["api_key_masked"] is not None
        else:
            assert exchange["configured"] is False
            assert exchange["api_key_masked"] is None


class TestExchangeSourceField:
    def test_db_keys_have_database_source(self, api_client):
        """When keys saved via API, source should be 'database'."""
        api_client.put("/api/settings/exchange", json={
            "api_key": "k", "api_secret": "s", "testnet": True
        })
        resp = api_client.get("/api/settings")
        assert resp.json()["exchange"]["source"] == "database"

    def test_exchange_response_has_source_field(self, api_client):
        resp = api_client.get("/api/settings")
        assert "source" in resp.json()["exchange"]

    def test_exchange_response_has_testnet_field(self, api_client):
        resp = api_client.get("/api/settings")
        assert "testnet" in resp.json()["exchange"]


class TestRiskParamsValidation:
    def test_update_multiple_risk_fields(self, api_client):
        resp = api_client.put("/api/settings/risk", json={
            "default_risk_pct": 0.01,
            "max_leverage": 20,
            "default_leverage": 5,
            "max_positions": 10,
        })
        assert resp.status_code == 200
        params = resp.json()["risk_params"]
        assert params["default_risk_pct"] == 0.01
        assert params["max_leverage"] == 20
        assert params["default_leverage"] == 5
        assert params["max_positions"] == 10

    def test_update_single_risk_field_preserves_rest(self, api_client):
        """Updating one field should not reset others."""
        api_client.get("/api/settings")  # ensure defaults
        api_client.put("/api/settings/risk", json={"max_leverage": 15})
        resp = api_client.get("/api/settings")
        params = resp.json()["risk_params"]
        assert params["max_leverage"] == 15
        assert params["default_risk_pct"] == 0.02  # default preserved

    def test_drawdown_params(self, api_client):
        resp = api_client.put("/api/settings/risk", json={
            "max_daily_loss": 0.10,
            "max_drawdown": 0.25,
            "max_portfolio_heat": 0.15,
        })
        assert resp.status_code == 200
        params = resp.json()["risk_params"]
        assert params["max_daily_loss"] == 0.10
        assert params["max_drawdown"] == 0.25
        assert params["max_portfolio_heat"] == 0.15


class TestSettingsComplete:
    def test_all_sections_present(self, api_client):
        resp = api_client.get("/api/settings")
        data = resp.json()
        assert "exchange" in data
        assert "risk_params" in data
        assert "strategy_config" in data
        assert "notification_config" in data

    def test_default_risk_has_all_keys(self, api_client):
        resp = api_client.get("/api/settings")
        params = resp.json()["risk_params"]
        for key in ("default_risk_pct", "max_leverage", "default_leverage",
                     "max_positions", "max_portfolio_heat", "max_daily_loss",
                     "max_drawdown"):
            assert key in params
