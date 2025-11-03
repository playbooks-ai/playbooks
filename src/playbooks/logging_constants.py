"""
Constants for logging configuration across the Playbooks framework.
Centralizes magic strings and values used in multiple places.
"""

from typing import Tuple

# Environment variable names
ENV_DEBUG_ENABLED: str = "PLAYBOOKS_DEBUG"
ENV_DEBUG_FILE: str = "PLAYBOOKS_DEBUG_FILE"
ENV_OUTPUT_HANDLER: str = "PLAYBOOKS_OUTPUT_HANDLER"
ENV_LOG_LEVEL: str = "PLAYBOOKS_LOG_LEVEL"
ENV_LOG_FILE: str = "PLAYBOOKS_LOG_FILE"

# Default values
DEFAULT_DEBUG_ENABLED: str = "false"
DEFAULT_OUTPUT_HANDLER: str = "console"
DEFAULT_LOG_LEVEL: str = "INFO"

# Boolean parsing constants
TRUTHY_VALUES: Tuple[str, ...] = ("true", "1", "yes")
FALSY_VALUES: Tuple[str, ...] = ("false", "0", "no")

# Logging format constants
DEFAULT_LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEBUG_LOG_FORMAT: str = (
    "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
DEBUG_PREFIX: str = "DEBUG: "

# Logger names
DEBUG_LOGGER_NAME: str = "playbooks.debug"
ROOT_LOGGER_NAME: str = ""

# Output handler types
HANDLER_CONSOLE: str = "console"
HANDLER_WEBSOCKET: str = "websocket"
HANDLER_SILENT: str = "silent"


def parse_boolean_env(value: str) -> bool:
    """Parse a string environment variable to boolean.

    Args:
        value: String value to parse (case-insensitive)

    Returns:
        True if value is in TRUTHY_VALUES, False otherwise
    """
    return value.lower() in TRUTHY_VALUES
