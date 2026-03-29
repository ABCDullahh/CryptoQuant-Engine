"""Triple Barrier Labeling for ML training data.

Implements Marcos Lopez de Prado's triple barrier method from
"Advances in Financial Machine Learning". Labels each trade event
based on which barrier is hit first:

- Upper barrier (take profit) → label = 1 (win)
- Lower barrier (stop loss) → label = -1 (loss)
- Time barrier (expiry) → label based on return at expiry

This produces cleaner ML labels than simple fixed-horizon returns
because it matches how we actually trade (with SL/TP levels).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BarrierEvent:
    """A single triple barrier labeled event."""

    entry_idx: int
    entry_price: float
    exit_idx: int
    exit_price: float
    return_pct: float
    label: int  # 1 = win, -1 = loss, 0 = neutral
    barrier_hit: str  # "upper" | "lower" | "time"
    holding_period: int


def triple_barrier_labels(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    upper_pct: float = 0.02,
    lower_pct: float = 0.02,
    max_holding: int = 24,
    min_return: float = 0.001,
) -> list[BarrierEvent]:
    """Apply triple barrier labeling to price series.

    Args:
        closes: Close prices (oldest first).
        highs: High prices (optional, uses closes if None).
        lows: Low prices (optional, uses closes if None).
        upper_pct: Upper barrier as % of entry (e.g., 0.02 = 2%).
        lower_pct: Lower barrier as % of entry (e.g., 0.02 = 2%).
        max_holding: Maximum bars to hold before time expiry.
        min_return: Minimum |return| to label as win/loss at time barrier.

    Returns:
        List of BarrierEvent with labels.
    """
    n = len(closes)
    if n < max_holding + 1:
        return []

    prices = np.array(closes, dtype=np.float64)
    h = np.array(highs if highs else closes, dtype=np.float64)
    l = np.array(lows if lows else closes, dtype=np.float64)

    events: list[BarrierEvent] = []

    for i in range(n - max_holding):
        entry = prices[i]
        upper = entry * (1 + upper_pct)
        lower = entry * (1 - lower_pct)

        exit_idx = i + max_holding
        exit_price = prices[exit_idx]
        barrier_hit = "time"

        # Check each subsequent bar
        for j in range(i + 1, min(i + max_holding + 1, n)):
            # Check upper barrier (using high)
            if h[j] >= upper:
                exit_idx = j
                exit_price = upper
                barrier_hit = "upper"
                break
            # Check lower barrier (using low)
            if l[j] <= lower:
                exit_idx = j
                exit_price = lower
                barrier_hit = "lower"
                break

        # Calculate return
        ret = (exit_price - entry) / entry

        # Label
        if barrier_hit == "upper":
            label = 1
        elif barrier_hit == "lower":
            label = -1
        else:
            # Time barrier — label based on return
            if ret > min_return:
                label = 1
            elif ret < -min_return:
                label = -1
            else:
                label = 0

        events.append(BarrierEvent(
            entry_idx=i,
            entry_price=entry,
            exit_idx=exit_idx,
            exit_price=exit_price,
            return_pct=ret,
            label=label,
            barrier_hit=barrier_hit,
            holding_period=exit_idx - i,
        ))

    return events


def compute_label_stats(events: list[BarrierEvent]) -> dict:
    """Compute statistics from triple barrier labels.

    Returns:
        Stats dict with win_rate, avg_return, barrier distribution, etc.
    """
    if not events:
        return {}

    labels = [e.label for e in events]
    returns = [e.return_pct for e in events]
    barriers = [e.barrier_hit for e in events]
    holdings = [e.holding_period for e in events]

    wins = sum(1 for l in labels if l == 1)
    losses = sum(1 for l in labels if l == -1)
    neutral = sum(1 for l in labels if l == 0)
    total = len(labels)

    return {
        "total_events": total,
        "wins": wins,
        "losses": losses,
        "neutral": neutral,
        "win_rate": wins / total if total > 0 else 0,
        "avg_return": float(np.mean(returns)),
        "avg_win": float(np.mean([r for r, l in zip(returns, labels) if l == 1])) if wins > 0 else 0,
        "avg_loss": float(np.mean([r for r, l in zip(returns, labels) if l == -1])) if losses > 0 else 0,
        "upper_barrier_pct": barriers.count("upper") / total if total > 0 else 0,
        "lower_barrier_pct": barriers.count("lower") / total if total > 0 else 0,
        "time_barrier_pct": barriers.count("time") / total if total > 0 else 0,
        "avg_holding_period": float(np.mean(holdings)),
    }
