"""
Production logging configuration for Playbooks framework.
This configures Python's standard logging for production use,
separate from the debug_logger used for development.
"""

import logging
import logging.handlers
import os
import sys
import threading
from typing import Optional

from playbooks.infrastructure.logging.constants import (
    ENV_LOG_LEVEL,
    ENV_LOG_FILE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_FORMAT,
    DEBUG_LOG_FORMAT,
)

# Global lock for thread-safe configuration
_config_lock: threading.Lock = threading.Lock()
_configured: bool = False


def setup_production_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
) -> None:
    """
    Configure Python's standard logging for production use.

    This is for structured logging of production events, errors, and metrics.
    It's separate from debug_logger which is for developer troubleshooting.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for logging output
        format_string: Optional custom format string
    """
    # Get configuration from environment or use defaults
    log_level = level or os.getenv(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL)
    log_file_path = log_file or os.getenv(ENV_LOG_FILE)

    # Default format for structured logging with context
    if format_string is None:
        format_string = DEFAULT_LOG_FORMAT
        if log_level == "DEBUG":
            # More detailed format for debug mode
            format_string = DEBUG_LOG_FORMAT

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Thread-safe handler management to avoid duplicates
    # Only clear if handlers exist and we're reconfiguring
    if root_logger.handlers:
        # Make a copy to avoid modification during iteration
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()

    # Console handler for stderr (production logs shouldn't interfere with stdout)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(logging.Formatter(format_string))
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file_path:
        # Use rotating file handler to prevent unbounded growth
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
        )
        file_handler.setFormatter(logging.Formatter(format_string))
        root_logger.addHandler(file_handler)

    # Set specific log levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)

    # Playbooks-specific loggers can be more verbose
    if log_level == "DEBUG":
        logging.getLogger("playbooks").setLevel(logging.DEBUG)
    else:
        # Even in INFO mode, keep framework internals at INFO level
        logging.getLogger("playbooks").setLevel(logging.INFO)
        # But reduce noise from specific subsystems
        logging.getLogger("playbooks.transport").setLevel(logging.WARNING)
        logging.getLogger("playbooks.debug.server").setLevel(logging.INFO)


def configure_logging() -> None:
    """
    Apply both debug and production logging configuration.
    Call this at application startup.
    Thread-safe: can be called multiple times safely.
    """
    global _configured

    with _config_lock:
        if _configured:
            return  # Already configured, skip

        # Setup production logging
        setup_production_logging()

        # Apply user output configuration
        from playbooks.infrastructure.logging.config import apply_config

        apply_config()

        _configured = True
