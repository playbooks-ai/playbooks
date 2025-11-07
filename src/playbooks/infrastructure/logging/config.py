"""
Minimal logging configuration for Playbooks framework.

Environment Variables:
    PLAYBOOKS_DEBUG=false           # Enable/disable debug output
    PLAYBOOKS_OUTPUT_HANDLER=console # console|websocket|silent
    PLAYBOOKS_DEBUG_FILE=           # Optional debug log file path
"""

import os
from typing import Optional

from playbooks.infrastructure.logging.constants import (
    ENV_DEBUG_ENABLED,
    ENV_OUTPUT_HANDLER,
    ENV_DEBUG_FILE,
    DEFAULT_DEBUG_ENABLED,
    DEFAULT_OUTPUT_HANDLER,
    HANDLER_CONSOLE,
    HANDLER_SILENT,
    parse_boolean_env,
)


class Config:
    """Minimal logging configuration with sensible defaults.

    Provides configuration for debug logging, output handlers, and debug file
    output based on environment variables.
    """

    DEBUG_ENABLED: bool = parse_boolean_env(
        os.getenv(ENV_DEBUG_ENABLED, DEFAULT_DEBUG_ENABLED)
    )
    OUTPUT_HANDLER: str = os.getenv(ENV_OUTPUT_HANDLER, DEFAULT_OUTPUT_HANDLER)
    DEBUG_FILE: Optional[str] = os.getenv(ENV_DEBUG_FILE)

    @classmethod
    def is_debug_enabled(cls) -> bool:
        """Check if debug logging is enabled."""
        return cls.DEBUG_ENABLED

    @classmethod
    def get_output_handler(cls) -> str:
        """Get the configured output handler type."""
        return cls.OUTPUT_HANDLER

    @classmethod
    def get_debug_file(cls) -> Optional[str]:
        """Get the debug file path if configured."""
        return cls.DEBUG_FILE


def apply_config() -> None:
    """Apply configuration to logging system."""
    from playbooks.infrastructure.user_output import (
        setup_for_console,
        setup_for_testing,
    )

    handler_type = Config.get_output_handler()

    if handler_type == HANDLER_CONSOLE:
        setup_for_console()
    elif handler_type == HANDLER_SILENT:
        setup_for_testing()
    # WebSocket handler is set up explicitly in web applications
    # via setup_for_web(emit_function)
