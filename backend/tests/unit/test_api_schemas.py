"""Tests for API schemas — request/response models validation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.schemas import (
    BacktestJobResponse,
    BacktestRunRequest,
    BotPaperModeUpdate,
    BotStrategyUpdate,
    ClosePositionRequest,
    ErrorDetail,
    ErrorResponse,
    ExchangeSettingsUpdate,
    ExecuteOrderRequest,
    HealthResponse,
    NotificationSettingsUpdate,
    OptimizeRequest,
    PaginatedResponse,
    PaginationParams,
    RiskSettingsUpdate,
    SignalListParams,
    TokenRequest,
    TokenResponse,
    UpdateStopLossRequest,
    UpdateTakeProfitRequest,
    WalkForwardRequest,
)


class TestPagination:
    def test_defaults(self):
        p = PaginationParams()
        assert p.limit == 20
        assert p.offset == 0

    def test_custom(self):
        p = PaginationParams(limit=50, offset=10)
        assert p.limit == 50
        assert p.offset == 10

    def test_limit_bounds(self):
        with pytest.raises(ValidationError):
            PaginationParams(limit=0)
        with pytest.raises(ValidationError):
            PaginationParams(limit=101)

    def test_paginated_response(self):
        r = PaginatedResponse(items=[1, 2, 3], total=100, limit=20, offset=0)
        assert len(r.items) == 3
        assert r.total == 100


class TestAuthSchemas:
    def test_token_request(self):
        t = TokenRequest(username="user", password="pass")
        assert t.username == "user"

    def test_token_response(self):
        t = TokenResponse(access_token="abc", expires_in=3600)
        assert t.token_type == "bearer"


class TestOrderSchemas:
    def test_execute_order_defaults(self):
        r = ExecuteOrderRequest(signal_id=str(uuid4()))
        assert r.mode == "ONE_CLICK"
        assert r.order_type == "MARKET"

    def test_execute_order_advanced(self):
        r = ExecuteOrderRequest(
            signal_id=str(uuid4()), mode="ADVANCED",
            entry_price=43000.0, leverage=5,
        )
        assert r.mode == "ADVANCED"
        assert r.leverage == 5


class TestPositionSchemas:
    def test_update_sl(self):
        r = UpdateStopLossRequest(new_sl=42000.0)
        assert r.new_sl == 42000.0

    def test_update_sl_invalid(self):
        with pytest.raises(ValidationError):
            UpdateStopLossRequest(new_sl=-100)

    def test_close_position_defaults(self):
        r = ClosePositionRequest()
        assert r.close_pct == 100.0

    def test_close_position_partial(self):
        r = ClosePositionRequest(close_pct=50.0)
        assert r.close_pct == 50.0


class TestBotSchemas:
    def test_strategy_update(self):
        r = BotStrategyUpdate(strategies={"momentum": True, "smc": False})
        assert r.strategies["momentum"] is True
        assert r.strategies["smc"] is False

    def test_paper_mode_update(self):
        r = BotPaperModeUpdate(paper_mode=True)
        assert r.paper_mode is True


class TestBacktestSchemas:
    def test_backtest_run_request(self):
        r = BacktestRunRequest(
            strategy_name="momentum",
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 1, tzinfo=UTC),
        )
        assert r.initial_capital == 10000.0
        assert r.symbol == "BTC/USDT"

    def test_backtest_job_response(self):
        r = BacktestJobResponse(job_id="abc", status="QUEUED")
        assert r.progress == 0

    def test_optimize_request(self):
        r = OptimizeRequest(
            strategy_name="momentum",
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 1, tzinfo=UTC),
            param_ranges={"rsi_period": {"min": 10, "max": 20}},
        )
        assert r.max_trials == 50

    def test_walkforward_request(self):
        r = WalkForwardRequest(
            strategy_name="momentum",
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 1, tzinfo=UTC),
        )
        assert r.in_sample_size == 500
        assert r.oos_size == 168


class TestSettingsSchemas:
    def test_exchange_update_defaults_to_testnet(self):
        """ExchangeSettingsUpdate should default to testnet=True for safety."""
        r = ExchangeSettingsUpdate(api_key="key", api_secret="secret")
        assert r.testnet is True

    def test_risk_update_partial(self):
        r = RiskSettingsUpdate(default_risk_pct=0.03)
        assert r.max_leverage is None

    def test_notification_update(self):
        r = NotificationSettingsUpdate(telegram_enabled=True)
        assert r.discord_enabled is None


class TestErrorSchemas:
    def test_error_response(self):
        r = ErrorResponse(error=ErrorDetail(code="NOT_FOUND", message="Item not found"))
        assert r.error.code == "NOT_FOUND"

    def test_health_response(self):
        r = HealthResponse()
        assert r.status == "ok"
        assert r.version == "0.1.0"
