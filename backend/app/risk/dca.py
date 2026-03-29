"""DCA (Dollar Cost Averaging / Average Down) calculator.

Determines when and how much to add to an existing losing position
based on user-configurable DCA levels.
"""

from __future__ import annotations

import structlog

from app.core.models import Direction

logger = structlog.get_logger(__name__)

# Default DCA config
DEFAULT_DCA_CONFIG = {
    "enabled": False,
    "max_dca_orders": 3,
    "trigger_drop_pct": [2.0, 4.0, 6.0],
    "qty_multiplier": [1.0, 1.5, 2.0],
    "max_total_risk_pct": 5.0,
    "sl_recalc_mode": "follow",   # "fixed" | "follow"
    "tp_recalc_mode": "recalculate",  # "fixed" | "recalculate"
}


class DCACalculator:
    """Calculate DCA order parameters for an existing position."""

    def __init__(self, dca_config: dict | None = None):
        self.config = {**DEFAULT_DCA_CONFIG, **(dca_config or {})}

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled", False))

    @property
    def max_orders(self) -> int:
        return int(self.config.get("max_dca_orders", 3))

    @property
    def triggers(self) -> list[float]:
        return self.config.get("trigger_drop_pct", [2.0, 4.0, 6.0])

    @property
    def multipliers(self) -> list[float]:
        return self.config.get("qty_multiplier", [1.0, 1.5, 2.0])

    @property
    def max_total_risk_pct(self) -> float:
        return float(self.config.get("max_total_risk_pct", 5.0))

    def should_trigger_dca(
        self,
        entry_price: float,
        current_price: float,
        direction: str,
        dca_orders_filled: int,
    ) -> int | None:
        """Check if a DCA order should be triggered.

        Returns the DCA level (0-indexed) to trigger, or None.
        """
        if not self.enabled:
            return None
        if dca_orders_filled >= self.max_orders:
            return None

        # Calculate price drop from entry
        if direction == "LONG" or direction == str(Direction.LONG):
            drop_pct = ((entry_price - current_price) / entry_price) * 100
        else:  # SHORT
            drop_pct = ((current_price - entry_price) / entry_price) * 100

        if drop_pct <= 0:
            return None  # Position is in profit, no DCA needed

        # Check which level to trigger (next unfilled)
        next_level = dca_orders_filled
        if next_level >= len(self.triggers):
            return None

        trigger_threshold = self.triggers[next_level]
        if drop_pct >= trigger_threshold:
            logger.info(
                "dca.trigger_detected",
                level=next_level,
                drop_pct=round(drop_pct, 2),
                threshold=trigger_threshold,
            )
            return next_level

        return None

    def calculate_dca_quantity(
        self,
        initial_quantity: float,
        dca_level: int,
    ) -> float:
        """Calculate the quantity for a DCA order at the given level."""
        if dca_level >= len(self.multipliers):
            return initial_quantity
        multiplier = self.multipliers[dca_level]
        return initial_quantity * multiplier

    def calculate_new_average_entry(
        self,
        old_qty: float,
        old_entry: float,
        new_qty: float,
        new_price: float,
    ) -> float:
        """Calculate the new weighted average entry price after DCA."""
        total_qty = old_qty + new_qty
        if total_qty == 0:
            return old_entry
        return (old_qty * old_entry + new_qty * new_price) / total_qty

    def should_recalc_sl(self) -> bool:
        """Whether to recalculate SL based on new average entry."""
        return self.config.get("sl_recalc_mode", "follow") == "follow"

    def should_recalc_tp(self) -> bool:
        """Whether to recalculate TP based on new average entry."""
        return self.config.get("tp_recalc_mode", "recalculate") == "recalculate"

    def recalculate_sl(
        self,
        original_entry: float,
        original_sl: float,
        new_avg_entry: float,
        direction: str,
    ) -> float:
        """Recalculate SL based on new average entry price.

        Maintains the same percentage distance from entry.
        """
        if not self.should_recalc_sl() or original_entry == 0:
            return original_sl

        sl_distance_pct = abs(original_entry - original_sl) / original_entry

        if direction == "LONG" or direction == str(Direction.LONG):
            return new_avg_entry * (1 - sl_distance_pct)
        else:
            return new_avg_entry * (1 + sl_distance_pct)

    def recalculate_tp(
        self,
        original_entry: float,
        original_tp: float,
        new_avg_entry: float,
        direction: str,
    ) -> float:
        """Recalculate TP based on new average entry price.

        Maintains the same percentage distance from entry.
        """
        if not self.should_recalc_tp() or original_entry == 0:
            return original_tp

        tp_distance_pct = abs(original_tp - original_entry) / original_entry

        if direction == "LONG" or direction == str(Direction.LONG):
            return new_avg_entry * (1 + tp_distance_pct)
        else:
            return new_avg_entry * (1 - tp_distance_pct)

    def check_risk_budget(
        self,
        current_total_risk_pct: float,
        additional_risk_pct: float,
    ) -> bool:
        """Check if adding a DCA order would exceed the risk budget."""
        return (current_total_risk_pct + additional_risk_pct) <= self.max_total_risk_pct
