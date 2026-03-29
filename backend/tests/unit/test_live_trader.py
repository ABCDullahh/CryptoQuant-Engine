"""Unit tests for LiveTrader - real exchange execution via CCXT."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.config.constants import Direction, OrderSide, OrderStatus, OrderType, TAKER_FEE
from app.core.models import OrderIntent, TakeProfit
from app.execution.live_trader import LiveTrader


def _make_order(
    symbol: str = "BTC/USDT",
    side: OrderSide = OrderSide.BUY,
    order_type: OrderType = OrderType.MARKET,
    quantity: float = 0.5,
    price: float = 43200.0,
    stop_loss: float = 42900.0,
    leverage: int = 3,
) -> OrderIntent:
    return OrderIntent(
        signal_id=uuid4(),
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_loss=stop_loss,
        take_profits=[
            TakeProfit(level="TP1", price=43650.0, close_pct=50, rr_ratio=1.5),
            TakeProfit(level="TP2", price=44100.0, close_pct=30, rr_ratio=3.0),
        ],
        leverage=leverage,
    )


def _mock_provider() -> AsyncMock:
    """Create a mock BinanceProvider with standard responses."""
    provider = AsyncMock()
    provider.set_leverage.return_value = {"leverage": 3}
    provider.create_order.return_value = {
        "id": "EXCHANGE-ORDER-123",
        "average": 43200.0,
        "filled": 0.5,
        "fee": {"cost": 5.4},
        "status": "closed",
    }
    provider.cancel_order.return_value = {"id": "cancelled"}
    # Precision methods are sync — use MagicMock so they return floats, not coroutines
    provider.amount_to_precision = MagicMock(side_effect=lambda sym, amt: amt)
    provider.price_to_precision = MagicMock(side_effect=lambda sym, px: px)
    return provider


# ---------------------------------------------------------------------------
# Execute Order
# ---------------------------------------------------------------------------


class TestLiveTraderExecuteOrder:
    async def test_execute_order_success(self):
        provider = _mock_provider()
        trader = LiveTrader(provider)
        order = _make_order()

        result = await trader.execute_order(order, current_price=43200.0)

        assert result.success is True
        assert result.filled_price == 43200.0
        assert result.filled_quantity == 0.5
        assert result.exchange_order_id == "EXCHANGE-ORDER-123"
        assert result.fees == 5.4
        assert result.status == OrderStatus.FILLED

    async def test_sets_leverage_before_order(self):
        provider = _mock_provider()
        trader = LiveTrader(provider)
        order = _make_order(leverage=5)

        await trader.execute_order(order)

        provider.set_leverage.assert_called_once_with("BTC/USDT", 5)

    async def test_places_market_order(self):
        provider = _mock_provider()
        trader = LiveTrader(provider)
        order = _make_order(side=OrderSide.BUY)

        await trader.execute_order(order)

        # First call is main order, subsequent are SL/TP
        main_call = provider.create_order.call_args_list[0]
        assert main_call.kwargs["symbol"] == "BTC/USDT"
        assert main_call.kwargs["side"] == "buy"
        assert main_call.kwargs["order_type"] == "market"
        assert main_call.kwargs["amount"] == 0.5

    async def test_places_sl_order(self):
        provider = _mock_provider()
        trader = LiveTrader(provider)
        order = _make_order()

        await trader.execute_order(order)

        # Find STOP_MARKET call
        sl_calls = [
            c for c in provider.create_order.call_args_list
            if c.kwargs.get("order_type") == "STOP_MARKET"
        ]
        assert len(sl_calls) == 1
        assert sl_calls[0].kwargs["params"]["stopPrice"] == 42900.0
        assert sl_calls[0].kwargs["params"]["reduceOnly"] is True

    async def test_places_tp_orders(self):
        provider = _mock_provider()
        trader = LiveTrader(provider)
        order = _make_order()

        await trader.execute_order(order)

        tp_calls = [
            c for c in provider.create_order.call_args_list
            if c.kwargs.get("order_type") == "TAKE_PROFIT_MARKET"
        ]
        assert len(tp_calls) == 2

    async def test_tracks_sl_tp_order_ids(self):
        provider = _mock_provider()
        trader = LiveTrader(provider)
        order = _make_order()

        await trader.execute_order(order)

        pos_key = str(order.id)
        assert pos_key in trader._sl_order_ids
        assert pos_key in trader._tp_order_ids
        assert len(trader._tp_order_ids[pos_key]) == 2

    async def test_execute_order_failure(self):
        provider = AsyncMock()
        provider.set_leverage.side_effect = Exception("Connection refused")
        trader = LiveTrader(provider)
        order = _make_order()

        result = await trader.execute_order(order)

        assert result.success is False
        assert "Connection refused" in result.message
        assert result.status == OrderStatus.REJECTED

    async def test_fallback_fee_calculation(self):
        """When exchange doesn't return fee, calculate from TAKER_FEE."""
        provider = _mock_provider()
        provider.create_order.return_value = {
            "id": "ORDER-456",
            "average": 43200.0,
            "filled": 0.5,
            "fee": {},
            "status": "closed",
        }
        trader = LiveTrader(provider)
        order = _make_order()

        result = await trader.execute_order(order)

        expected_fee = 0.5 * 43200.0 * TAKER_FEE
        assert result.fees == expected_fee

    async def test_sl_placement_failure_doesnt_block_order(self):
        """SL placement failure should not fail the main order."""
        provider = _mock_provider()
        call_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("order_type") == "STOP_MARKET":
                raise Exception("SL placement failed")
            return {
                "id": f"ORDER-{call_count}",
                "average": 43200.0,
                "filled": 0.5,
                "fee": {"cost": 5.0},
            }

        provider.create_order = mock_create
        trader = LiveTrader(provider)
        order = _make_order()

        result = await trader.execute_order(order)
        assert result.success is True


# ---------------------------------------------------------------------------
# Close Position
# ---------------------------------------------------------------------------


class TestLiveTraderClosePosition:
    async def test_close_long_position(self):
        provider = _mock_provider()
        trader = LiveTrader(provider)

        result = await trader.close_position(
            position_id="pos-1",
            symbol="BTC/USDT",
            direction=Direction.LONG,
            quantity=0.5,
            close_price=43500.0,
            reason="SL_HIT",
        )

        assert result.success is True
        # Close a LONG = sell
        main_call = provider.create_order.call_args
        assert main_call.kwargs["side"] == "sell"
        assert main_call.kwargs["params"]["reduceOnly"] is True

    async def test_close_short_position(self):
        provider = _mock_provider()
        trader = LiveTrader(provider)

        result = await trader.close_position(
            position_id="pos-2",
            symbol="BTC/USDT",
            direction=Direction.SHORT,
            quantity=0.5,
            close_price=42000.0,
        )

        assert result.success is True
        main_call = provider.create_order.call_args
        assert main_call.kwargs["side"] == "buy"

    async def test_close_cancels_sl_tp_orders(self):
        """Closing a position should cancel associated SL/TP orders."""
        provider = _mock_provider()
        trader = LiveTrader(provider)

        # Pre-populate SL/TP tracking
        trader._sl_order_ids["pos-1"] = "SL-ORDER-1"
        trader._tp_order_ids["pos-1"] = ["TP-ORDER-1", "TP-ORDER-2"]

        await trader.close_position(
            position_id="pos-1",
            symbol="BTC/USDT",
            direction=Direction.LONG,
            quantity=0.5,
            close_price=43500.0,
        )

        # Should cancel SL + 2 TPs = 3 cancel calls
        assert provider.cancel_order.call_count == 3
        # SL/TP tracking should be cleaned up
        assert "pos-1" not in trader._sl_order_ids
        assert "pos-1" not in trader._tp_order_ids

    async def test_close_failure(self):
        provider = AsyncMock()
        provider.create_order.side_effect = Exception("Exchange error")
        trader = LiveTrader(provider)

        result = await trader.close_position(
            position_id="pos-1",
            symbol="BTC/USDT",
            direction=Direction.LONG,
            quantity=0.5,
            close_price=43500.0,
        )

        assert result.success is False
        assert "Exchange error" in result.message

    async def test_cancel_order_failure_doesnt_block_close(self):
        """Cancel failure on SL/TP should not fail the close."""
        provider = _mock_provider()
        provider.cancel_order.side_effect = Exception("Already cancelled")
        trader = LiveTrader(provider)

        trader._sl_order_ids["pos-1"] = "SL-1"
        trader._tp_order_ids["pos-1"] = ["TP-1"]

        result = await trader.close_position(
            position_id="pos-1",
            symbol="BTC/USDT",
            direction=Direction.LONG,
            quantity=0.5,
            close_price=43500.0,
        )

        # Close itself should still succeed
        assert result.success is True
