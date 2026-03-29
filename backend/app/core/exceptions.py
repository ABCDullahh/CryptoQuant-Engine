"""Custom exceptions for CryptoQuant Engine."""


class CryptoQuantError(Exception):
    """Base exception for all CryptoQuant errors."""


# --- Exchange Errors ---

class ExchangeError(CryptoQuantError):
    """Base exception for exchange-related errors."""


class ExchangeConnectionError(ExchangeError):
    """Failed to connect to exchange."""


class RateLimitError(ExchangeError):
    """Exchange rate limit exceeded."""


class AuthenticationError(ExchangeError):
    """Invalid API key or authentication failure."""


class InsufficientBalanceError(ExchangeError):
    """Insufficient balance to place order."""


class OrderRejectedError(ExchangeError):
    """Order was rejected by the exchange."""


# --- Data Errors ---

class DataError(CryptoQuantError):
    """Base exception for data-related errors."""


class DataGapError(DataError):
    """Gap detected in market data."""


class StaleDataError(DataError):
    """Market data is stale (too old)."""


# --- Strategy Errors ---

class StrategyError(CryptoQuantError):
    """Base exception for strategy-related errors."""


class InsufficientDataError(StrategyError):
    """Not enough data for indicator calculation (warmup period)."""


class StrategyDisabledError(StrategyError):
    """Strategy has been auto-disabled due to errors."""


# --- Risk Errors ---

class RiskError(CryptoQuantError):
    """Base exception for risk management errors."""


class RiskLimitExceededError(RiskError):
    """Risk limit exceeded (portfolio heat, position count, etc.)."""


class CircuitBreakerError(RiskError):
    """Circuit breaker is active, trading halted."""


class InvalidRiskParameterError(RiskError):
    """Invalid risk parameter (e.g., RR too low)."""


# --- Execution Errors ---

class ExecutionError(CryptoQuantError):
    """Base exception for execution errors."""


class PositionNotFoundError(ExecutionError):
    """Position not found."""


class OrderNotFoundError(ExecutionError):
    """Order not found."""


# --- Database Errors ---

class DatabaseError(CryptoQuantError):
    """Base exception for database errors."""


class DatabaseConnectionError(DatabaseError):
    """Failed to connect to database."""
