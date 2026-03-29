"""Tests for backtesting strategy factory -- strategy name resolution."""

import pytest

from app.backtesting.strategy_factory import create_strategies
from app.strategies.base import BaseStrategy
from app.strategies import STRATEGY_REGISTRY


class TestCreateStrategies:
    def test_momentum_strategy(self):
        strategies = create_strategies("momentum")
        assert len(strategies) == 1
        assert isinstance(strategies[0], BaseStrategy)

    def test_mean_reversion_strategy(self):
        strategies = create_strategies("mean_reversion")
        assert len(strategies) == 1
        assert isinstance(strategies[0], BaseStrategy)

    def test_smart_money_strategy(self):
        strategies = create_strategies("smart_money")
        assert len(strategies) == 1
        assert isinstance(strategies[0], BaseStrategy)

    def test_volume_analysis_strategy(self):
        strategies = create_strategies("volume_analysis")
        assert len(strategies) == 1
        assert isinstance(strategies[0], BaseStrategy)

    def test_funding_arb_strategy(self):
        strategies = create_strategies("funding_arb")
        assert len(strategies) == 1
        assert isinstance(strategies[0], BaseStrategy)

    def test_all_strategies(self):
        strategies = create_strategies("all")
        assert len(strategies) == len(STRATEGY_REGISTRY)
        for s in strategies:
            assert isinstance(s, BaseStrategy)

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            create_strategies("nonexistent_strategy")

    def test_each_registry_key(self):
        for name in STRATEGY_REGISTRY:
            strategies = create_strategies(name)
            assert len(strategies) == 1
            assert isinstance(strategies[0], BaseStrategy)

    def test_case_insensitive(self):
        strategies = create_strategies("MOMENTUM")
        assert len(strategies) == 1
        assert isinstance(strategies[0], BaseStrategy)

    def test_none_parameters_ok(self):
        strategies = create_strategies("momentum", None)
        assert len(strategies) == 1

    def test_empty_parameters_ok(self):
        strategies = create_strategies("momentum", {})
        assert len(strategies) == 1

    def test_all_returns_correct_count(self):
        strategies = create_strategies("all")
        assert len(strategies) == 5  # 5 strategies in registry

    def test_strategy_has_name(self):
        strategies = create_strategies("momentum")
        assert hasattr(strategies[0], "name")
        assert strategies[0].name is not None
