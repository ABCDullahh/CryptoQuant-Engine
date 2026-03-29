"""Strategy factory for backtesting — resolves strategy names to instances."""

from __future__ import annotations

import inspect

import structlog

from app.strategies import STRATEGY_REGISTRY
from app.strategies.base import BaseStrategy

logger = structlog.get_logger(__name__)


def _create_instance(cls: type[BaseStrategy], parameters: dict | None = None) -> BaseStrategy:
    """Create a strategy instance, applying parameters if the constructor accepts them."""
    if not parameters:
        return cls()

    # Check which params the constructor actually accepts
    sig = inspect.signature(cls.__init__)
    accepted = {
        name for name, param in sig.parameters.items()
        if name != "self" and param.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    }
    has_kwargs = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )

    if has_kwargs:
        return cls(**parameters)

    if accepted:
        filtered = {k: v for k, v in parameters.items() if k in accepted}
        return cls(**filtered)

    # Constructor takes no params — ignore optimizer params, log warning
    logger.debug(
        "strategy_factory.params_ignored",
        strategy=cls.name,
        params=list(parameters.keys()),
    )
    return cls()


def create_strategies(
    strategy_name: str,
    parameters: dict | None = None,
) -> list[BaseStrategy]:
    """Create strategy instances from a strategy name.

    Args:
        strategy_name: Name from STRATEGY_REGISTRY or "all" for all strategies.
        parameters: Optional parameters to pass to strategy constructors.

    Returns:
        List of BaseStrategy instances.

    Raises:
        ValueError: If strategy_name is not found in registry.
    """
    if strategy_name.lower() == "all":
        return [_create_instance(cls, parameters) for cls in STRATEGY_REGISTRY.values()]

    cls = STRATEGY_REGISTRY.get(strategy_name.lower())
    if cls is None:
        available = ", ".join(sorted(STRATEGY_REGISTRY.keys()))
        raise ValueError(
            f"Unknown strategy '{strategy_name}'. Available: {available}"
        )

    return [_create_instance(cls, parameters)]
