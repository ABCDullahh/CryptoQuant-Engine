"""Data models for Supply/Demand zones."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ZoneType(StrEnum):
    """Supply or Demand zone."""
    SUPPLY = "SUPPLY"
    DEMAND = "DEMAND"


@dataclass
class Zone:
    """A single supply or demand zone detected from price action."""

    type: ZoneType
    top: float
    bottom: float
    origin_time: datetime
    trigger: str  # "BOS" or "CHoCH"
    volume_ratio: float  # volume at formation / SMA20

    touch_count: int = 0
    is_fresh: bool = True
    strength: float = 0.0
    mitigated: bool = False
    age_candles: int = 0

    @property
    def width(self) -> float:
        return self.top - self.bottom

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    def mark_tested(self) -> None:
        self.touch_count += 1
        self.is_fresh = False

    def mark_mitigated(self) -> None:
        self.mitigated = True


@dataclass
class ZoneEvent:
    """An event emitted by the ZoneDetector."""
    event_type: str  # "created", "mitigated", "tested", "expired"
    zone: Zone
