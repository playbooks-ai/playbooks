"""
Zero-overhead debug logging for Playbooks framework development.

Usage:
    from playbooks.debug_logger import debug

    debug("Agent processing message", agent_id="1234", message_type="USER_INPUT")
    debug("Performance: operation took {duration:.2f}ms", duration=15.5)
"""

import os
import logging
from typing import Any, Optional

from .logging_constants import (
    ENV_DEBUG_ENABLED,
    ENV_DEBUG_FILE,
    DEFAULT_DEBUG_ENABLED,
    DEBUG_LOGGER_NAME,
    DEBUG_PREFIX,
    parse_boolean_env,
)

# Global debug state - checked once at module load for zero overhead
_DEBUG_ENABLED: bool = parse_boolean_env(
    os.getenv(ENV_DEBUG_ENABLED, DEFAULT_DEBUG_ENABLED)
)
_debug_logger: Optional[logging.Logger] = None


def debug(message: str, **context: Any) -> None:
    """Zero-overhead debug logging when disabled."""
    if not _DEBUG_ENABLED:
        return

    global _debug_logger
    if _debug_logger is None:
        _setup_debug_logger()

    if context:
        try:
            # Safely format context, handling circular refs and non-serializable objects
            context_parts = []
            for k, v in context.items():
                try:
                    # Try repr first (safer than str for some objects)
                    context_parts.append(f"{k}={repr(v)}")
                except Exception:
                    # Fallback to type name if repr fails
                    context_parts.append(f"{k}=<{type(v).__name__}>")
            context_str = " | ".join(context_parts)
            _debug_logger.debug(f"{message} | {context_str}")
        except Exception:
            # Last resort: just log the message without context
            _debug_logger.debug(f"{message} | <context formatting failed>")
    else:
        _debug_logger.debug(message)


def _setup_debug_logger() -> None:
    """Setup debug logger once when first debug call is made."""
    global _debug_logger

    _debug_logger = logging.getLogger(DEBUG_LOGGER_NAME)
    _debug_logger.setLevel(logging.DEBUG)

    # Console handler
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(f"{DEBUG_PREFIX}%(message)s"))
    _debug_logger.addHandler(handler)

    # Optional file handler
    debug_file = os.getenv(ENV_DEBUG_FILE)
    if debug_file:
        file_handler = logging.FileHandler(debug_file)
        file_handler.setFormatter(
            logging.Formatter(f"%(asctime)s {DEBUG_PREFIX}%(message)s")
        )
        _debug_logger.addHandler(file_handler)

    # Prevent propagation to root logger
    _debug_logger.propagate = False


def is_debug_enabled() -> bool:
    """Check if debug logging is enabled."""
    return _DEBUG_ENABLED
