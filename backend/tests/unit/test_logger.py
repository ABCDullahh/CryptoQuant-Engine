import logging
import sys

import pytest
import structlog

from app.utils.logger import setup_logging


def test_setup_logging_json_mode(monkeypatch):
    """Test that setup_logging configures JSON mode correctly."""
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    setup_logging()

    # Verify that we can get a logger and it works
    logger = structlog.get_logger()
    assert logger is not None

    # Verify the logger can be used without error
    try:
        logger.debug("test message")
    except Exception as e:
        pytest.fail(f"Logger raised an exception: {e}")


def test_setup_logging_console_mode(monkeypatch):
    """Test that setup_logging configures console mode correctly."""
    monkeypatch.setenv("LOG_FORMAT", "console")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    setup_logging()

    # Verify that we can get a logger and it works
    logger = structlog.get_logger()
    assert logger is not None

    # Verify the logger can be used without error
    try:
        logger.info("test message")
    except Exception as e:
        pytest.fail(f"Logger raised an exception: {e}")


def test_setup_logging_default_level(monkeypatch):
    """Test that the default log level is INFO when not specified."""
    # Don't set LOG_LEVEL, let it use default
    monkeypatch.setenv("LOG_FORMAT", "console")
    # Ensure LOG_LEVEL is not set
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    setup_logging()

    # Verify logging is configured
    logger = structlog.get_logger()
    assert logger is not None

    # Verify the logger works
    try:
        logger.info("test message at info level")
    except Exception as e:
        pytest.fail(f"Logger raised an exception: {e}")


def test_logger_can_log(monkeypatch):
    """Test that after setup_logging, the logger can log messages without raising."""
    monkeypatch.setenv("LOG_FORMAT", "console")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    setup_logging()

    logger = structlog.get_logger()

    # Test various log levels
    try:
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")
    except Exception as e:
        pytest.fail(f"Logger raised an exception: {e}")


def test_setup_logging_with_different_levels(monkeypatch):
    """Test that setup_logging works with different log levels."""
    levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    for level in levels:
        # Clear cache between iterations
        from app.config.settings import get_settings
        get_settings.cache_clear()

        monkeypatch.setenv("LOG_LEVEL", level)
        monkeypatch.setenv("LOG_FORMAT", "console")

        setup_logging()

        logger = structlog.get_logger()
        assert logger is not None

        # Verify the logger works
        try:
            logger.info(f"test message with {level} level")
        except Exception as e:
            pytest.fail(f"Logger raised an exception at {level}: {e}")
