"""
Unit tests for exception hierarchy in backend/app/core/exceptions.py
"""

import pytest
from app.core.exceptions import (
    CryptoQuantError,
    ExchangeError,
    ExchangeConnectionError,
    RateLimitError,
    AuthenticationError,
    InsufficientBalanceError,
    OrderRejectedError,
    DataError,
    DataGapError,
    StaleDataError,
    StrategyError,
    InsufficientDataError,
    StrategyDisabledError,
    RiskError,
    RiskLimitExceededError,
    CircuitBreakerError,
    InvalidRiskParameterError,
    ExecutionError,
    PositionNotFoundError,
    OrderNotFoundError,
    DatabaseError,
    DatabaseConnectionError,
)


def test_base_exception_is_exception():
    """Test that CryptoQuantError is a subclass of Exception."""
    assert issubclass(CryptoQuantError, Exception)

    # Verify it can be instantiated and raised
    error = CryptoQuantError("test error")
    assert isinstance(error, Exception)


def test_exception_hierarchy():
    """Test that each error is a subclass of its parent."""
    # ExchangeError hierarchy
    assert issubclass(ExchangeError, CryptoQuantError)
    assert issubclass(ExchangeConnectionError, ExchangeError)
    assert issubclass(RateLimitError, ExchangeError)
    assert issubclass(AuthenticationError, ExchangeError)
    assert issubclass(InsufficientBalanceError, ExchangeError)
    assert issubclass(OrderRejectedError, ExchangeError)

    # DataError hierarchy
    assert issubclass(DataError, CryptoQuantError)
    assert issubclass(DataGapError, DataError)
    assert issubclass(StaleDataError, DataError)

    # StrategyError hierarchy
    assert issubclass(StrategyError, CryptoQuantError)
    assert issubclass(InsufficientDataError, StrategyError)
    assert issubclass(StrategyDisabledError, StrategyError)

    # RiskError hierarchy
    assert issubclass(RiskError, CryptoQuantError)
    assert issubclass(RiskLimitExceededError, RiskError)
    assert issubclass(CircuitBreakerError, RiskError)
    assert issubclass(InvalidRiskParameterError, RiskError)

    # ExecutionError hierarchy
    assert issubclass(ExecutionError, CryptoQuantError)
    assert issubclass(PositionNotFoundError, ExecutionError)
    assert issubclass(OrderNotFoundError, ExecutionError)

    # DatabaseError hierarchy
    assert issubclass(DatabaseError, CryptoQuantError)
    assert issubclass(DatabaseConnectionError, DatabaseError)


def test_all_exchange_errors_catchable():
    """Test that all exchange errors can be caught with except ExchangeError."""
    exchange_errors = [
        ExchangeConnectionError("connection failed"),
        RateLimitError("rate limit exceeded"),
        AuthenticationError("invalid credentials"),
        InsufficientBalanceError("not enough funds"),
        OrderRejectedError("order rejected"),
    ]

    for error in exchange_errors:
        try:
            raise error
        except ExchangeError as e:
            assert isinstance(e, ExchangeError)
            assert isinstance(e, CryptoQuantError)
        except Exception:
            pytest.fail(f"{type(error).__name__} not caught by ExchangeError")


def test_all_data_errors_catchable():
    """Test that all data errors can be caught with except DataError."""
    data_errors = [
        DataGapError("missing data"),
        StaleDataError("data is stale"),
    ]

    for error in data_errors:
        try:
            raise error
        except DataError as e:
            assert isinstance(e, DataError)
            assert isinstance(e, CryptoQuantError)
        except Exception:
            pytest.fail(f"{type(error).__name__} not caught by DataError")


def test_all_strategy_errors_catchable():
    """Test that all strategy errors can be caught with except StrategyError."""
    strategy_errors = [
        InsufficientDataError("not enough data"),
        StrategyDisabledError("strategy is disabled"),
    ]

    for error in strategy_errors:
        try:
            raise error
        except StrategyError as e:
            assert isinstance(e, StrategyError)
            assert isinstance(e, CryptoQuantError)
        except Exception:
            pytest.fail(f"{type(error).__name__} not caught by StrategyError")


def test_all_risk_errors_catchable():
    """Test that all risk errors can be caught with except RiskError."""
    risk_errors = [
        RiskLimitExceededError("risk limit exceeded"),
        CircuitBreakerError("circuit breaker triggered"),
        InvalidRiskParameterError("invalid risk parameter"),
    ]

    for error in risk_errors:
        try:
            raise error
        except RiskError as e:
            assert isinstance(e, RiskError)
            assert isinstance(e, CryptoQuantError)
        except Exception:
            pytest.fail(f"{type(error).__name__} not caught by RiskError")


def test_all_execution_errors_catchable():
    """Test that all execution errors can be caught with except ExecutionError."""
    execution_errors = [
        PositionNotFoundError("position not found"),
        OrderNotFoundError("order not found"),
    ]

    for error in execution_errors:
        try:
            raise error
        except ExecutionError as e:
            assert isinstance(e, ExecutionError)
            assert isinstance(e, CryptoQuantError)
        except Exception:
            pytest.fail(f"{type(error).__name__} not caught by ExecutionError")


def test_exception_message():
    """Test that exception messages are stored and retrieved correctly."""
    test_message = "This is a test error message"

    # Test base exception
    error = CryptoQuantError(test_message)
    assert str(error) == test_message

    # Test a few specific exceptions
    exchange_error = ExchangeConnectionError(test_message)
    assert str(exchange_error) == test_message

    data_error = DataGapError(test_message)
    assert str(data_error) == test_message

    risk_error = RiskLimitExceededError(test_message)
    assert str(risk_error) == test_message


def test_catch_all_with_base():
    """Test that all specific errors can be caught with except CryptoQuantError."""
    all_errors = [
        # Exchange errors
        ExchangeConnectionError("connection error"),
        RateLimitError("rate limit"),
        AuthenticationError("auth error"),
        InsufficientBalanceError("no balance"),
        OrderRejectedError("order rejected"),
        # Data errors
        DataGapError("data gap"),
        StaleDataError("stale data"),
        # Strategy errors
        InsufficientDataError("insufficient data"),
        StrategyDisabledError("strategy disabled"),
        # Risk errors
        RiskLimitExceededError("risk exceeded"),
        CircuitBreakerError("circuit breaker"),
        InvalidRiskParameterError("invalid parameter"),
        # Execution errors
        PositionNotFoundError("position not found"),
        OrderNotFoundError("order not found"),
        # Database errors
        DatabaseConnectionError("db connection failed"),
    ]

    for error in all_errors:
        try:
            raise error
        except CryptoQuantError as e:
            assert isinstance(e, CryptoQuantError)
        except Exception:
            pytest.fail(f"{type(error).__name__} not caught by CryptoQuantError")
