"""Tests for zone data models."""

from datetime import datetime, timezone

import pytest

from app.zones.models import Zone, ZoneType, ZoneEvent


class TestZoneType:
    def test_supply_zone_value(self):
        assert ZoneType.SUPPLY == "SUPPLY"

    def test_demand_zone_value(self):
        assert ZoneType.DEMAND == "DEMAND"


class TestZone:
    def test_create_demand_zone(self):
        z = Zone(
            type=ZoneType.DEMAND,
            top=69000.0,
            bottom=68500.0,
            origin_time=datetime(2026, 3, 25, tzinfo=timezone.utc),
            trigger="BOS",
            volume_ratio=1.8,
        )
        assert z.type == ZoneType.DEMAND
        assert z.top == 69000.0
        assert z.bottom == 68500.0
        assert z.trigger == "BOS"
        assert z.touch_count == 0
        assert z.is_fresh is True
        assert z.mitigated is False

    def test_create_supply_zone(self):
        z = Zone(
            type=ZoneType.SUPPLY,
            top=72000.0,
            bottom=71500.0,
            origin_time=datetime(2026, 3, 25, tzinfo=timezone.utc),
            trigger="CHoCH",
            volume_ratio=2.1,
        )
        assert z.type == ZoneType.SUPPLY
        assert z.trigger == "CHoCH"

    def test_zone_width(self):
        z = Zone(
            type=ZoneType.DEMAND,
            top=69000.0,
            bottom=68500.0,
            origin_time=datetime(2026, 3, 25, tzinfo=timezone.utc),
            trigger="BOS",
            volume_ratio=1.5,
        )
        assert z.width == 500.0

    def test_zone_midpoint(self):
        z = Zone(
            type=ZoneType.DEMAND,
            top=69000.0,
            bottom=68500.0,
            origin_time=datetime(2026, 3, 25, tzinfo=timezone.utc),
            trigger="BOS",
            volume_ratio=1.5,
        )
        assert z.midpoint == 68750.0

    def test_zone_contains_price(self):
        z = Zone(
            type=ZoneType.DEMAND,
            top=69000.0,
            bottom=68500.0,
            origin_time=datetime(2026, 3, 25, tzinfo=timezone.utc),
            trigger="BOS",
            volume_ratio=1.5,
        )
        assert z.contains(68750.0) is True
        assert z.contains(68500.0) is True
        assert z.contains(69000.0) is True
        assert z.contains(68499.0) is False
        assert z.contains(69001.0) is False

    def test_zone_defaults(self):
        z = Zone(
            type=ZoneType.DEMAND,
            top=69000.0,
            bottom=68500.0,
            origin_time=datetime(2026, 3, 25, tzinfo=timezone.utc),
            trigger="BOS",
            volume_ratio=1.5,
        )
        assert z.touch_count == 0
        assert z.is_fresh is True
        assert z.strength == 0.0
        assert z.mitigated is False
        assert z.age_candles == 0

    def test_zone_mark_tested(self):
        z = Zone(
            type=ZoneType.DEMAND,
            top=69000.0,
            bottom=68500.0,
            origin_time=datetime(2026, 3, 25, tzinfo=timezone.utc),
            trigger="BOS",
            volume_ratio=1.5,
        )
        z.mark_tested()
        assert z.touch_count == 1
        assert z.is_fresh is False

    def test_zone_mark_mitigated(self):
        z = Zone(
            type=ZoneType.DEMAND,
            top=69000.0,
            bottom=68500.0,
            origin_time=datetime(2026, 3, 25, tzinfo=timezone.utc),
            trigger="BOS",
            volume_ratio=1.5,
        )
        z.mark_mitigated()
        assert z.mitigated is True


class TestZoneEvent:
    def test_zone_created_event(self):
        z = Zone(
            type=ZoneType.DEMAND,
            top=69000.0,
            bottom=68500.0,
            origin_time=datetime(2026, 3, 25, tzinfo=timezone.utc),
            trigger="BOS",
            volume_ratio=1.5,
        )
        evt = ZoneEvent(event_type="created", zone=z)
        assert evt.event_type == "created"
        assert evt.zone is z

    def test_zone_mitigated_event(self):
        z = Zone(
            type=ZoneType.SUPPLY,
            top=72000.0,
            bottom=71500.0,
            origin_time=datetime(2026, 3, 25, tzinfo=timezone.utc),
            trigger="BOS",
            volume_ratio=1.5,
        )
        evt = ZoneEvent(event_type="mitigated", zone=z)
        assert evt.event_type == "mitigated"
