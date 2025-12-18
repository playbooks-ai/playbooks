"""
Zero-overhead debug logging for Playbooks framework development.

Usage:
    from playbooks.infrastructure.logging.debug_logger import debug

    # Basic usage
    debug("Agent processing message", agent_id="1234", message_type="USER_INPUT")
    debug("Performance: operation took {duration:.2f}ms", duration=15.5)

    # With Rich markup for colored output
    debug("[green]Success![/green] Operation completed")
    debug("Status: [bold red]ERROR[/bold red] - [yellow]Retrying...[/yellow]")
    debug("[cyan]Info:[/cyan] Processing [bold magenta]agent-123[/bold magenta]")

    # Disable markup parsing if needed
    debug("Literal [brackets] in message", markup=False)

    # Custom colors via context
    debug("Custom colored message", color="purple")
    debug("Bold and italic", style="bold italic blue")
"""

import logging
import os
from typing import Any, Optional

from rich.console import Console
from rich.text import Text

from playbooks.config import config
from playbooks.infrastructure.logging.constants import (
    DEBUG_LOGGER_NAME,
    DEBUG_PREFIX,
    ENV_DEBUG_FILE,
    parse_boolean_env,
)
from playbooks.llm.messages.timestamp import get_timestamp

_debug_logger: Optional[logging.Logger] = None
_console: Optional[Console] = None

# Check if we should use Rich console (can be disabled via env var)
_USE_RICH_CONSOLE: bool = parse_boolean_env(
    os.getenv("PLAYBOOKS_DEBUG_USE_RICH", "true")
)


def debug(msg: str = None, **context: Any) -> None:
    """Zero-overhead debug logging when disabled.

    Supports Rich markup syntax for colored output when Rich console is enabled:
        debug("[green]Success![/green] Operation completed")
        debug("Status: [bold red]ERROR[/bold red] - connection failed")

    Args:
        msg: The debug message. Supports Rich markup like [color]text[/color].
             If not provided, will look for 'message' in context.
        **context: Additional context to include in the debug output.
                  Special keys:
                  - 'markup': bool - Enable/disable markup parsing (default: True)
                  - 'color': str - Apply a color to the entire message
                  - 'style': str - Apply a style to the entire message
                  - 'include_timestamp': bool - Include timestamp prefix (default: True)
    """
    if not config.debug:
        return

    # Handle the case where message is passed as keyword argument
    if msg is None and "message" in context:
        msg = context.pop("message")
    elif msg is None:
        msg = "Debug message"  # Default message

    global _debug_logger, _console
    if _debug_logger is None:
        _setup_debug_logger()

    # Extract special context keys
    enable_markup = context.pop("markup", True) if context else True
    include_timestamp = context.pop("include_timestamp", True) if context else True

    # Get timestamp for prefix (will be added with DEBUG_PREFIX later)
    timestamp = get_timestamp() if include_timestamp else None

    if "agent" in context:
        agent = context.get("agent")
        context_prefix = str(agent) + " - "
        context.pop("agent")
    else:
        context_prefix = ""

    msg = f"{context_prefix}{msg}"

    # Format the message with context
    if context:
        try:
            # Safely format context, handling circular refs and non-serializable objects
            # Skip color/style/markup keys when formatting output
            context_parts = []
            for k, v in context.items():
                # Skip internal formatting keys
                if k in ["color", "style"]:
                    continue
                try:
                    # Try repr first (safer than str for some objects)
                    context_parts.append(f"{k}={repr(v)}")
                except Exception:
                    # Fallback to type name if repr fails
                    context_parts.append(f"{k}=<{type(v).__name__}>")

            if context_parts:
                context_str = " | ".join(context_parts)
                full_msg = f"{msg} | {context_str}"
            else:
                full_msg = msg
        except Exception:
            # Last resort: just log the message without context
            full_msg = f"{msg} | <context formatting failed>"
    else:
        full_msg = msg

    # Use Rich console for colored output if enabled
    if _USE_RICH_CONSOLE and _console:
        # Also log to file if configured (strip markup for file output)
        if _debug_logger.handlers:
            for handler in _debug_logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    # Strip markup for file logging
                    from rich.text import Text

                    clean_msg = (
                        Text.from_markup(full_msg).plain if enable_markup else full_msg
                    )
                    # Add timestamp and DEBUG_PREFIX for file logging
                    if timestamp is not None:
                        clean_msg = f"{timestamp:05d}: {DEBUG_PREFIX}{clean_msg}"
                    else:
                        clean_msg = f"{DEBUG_PREFIX}{clean_msg}"
                    _debug_logger.debug(clean_msg)
                    break
        _print_with_rich(msg, full_msg, context, enable_markup, timestamp)
    else:
        # Strip markup for standard logging if markup was in the message
        if enable_markup and "[" in full_msg and "]" in full_msg:
            from rich.text import Text

            full_msg = Text.from_markup(full_msg).plain
        # Add timestamp and DEBUG_PREFIX for standard logging
        if timestamp is not None:
            full_msg = f"{timestamp:05d}: {DEBUG_PREFIX}{full_msg}"
        else:
            full_msg = f"{DEBUG_PREFIX}{full_msg}"
        _debug_logger.debug(full_msg)


def _print_with_rich(
    original_msg: str,
    full_msg: str,
    context: dict,
    enable_markup: bool,
    timestamp: int | None,
) -> None:
    """Print debug message using Rich console with colors and markup support.

    Args:
        original_msg: The original message without context (used for auto-color detection)
        full_msg: The formatted message with context
        context: The original context dict for determining colors
        enable_markup: Whether to parse Rich markup in the message
        timestamp: Optional timestamp to include in output
    """
    # Create the prefix with timestamp
    if timestamp is not None:
        prefix = f"{timestamp:05d}: {DEBUG_PREFIX}"
    else:
        prefix = DEBUG_PREFIX

    # If markup is enabled and present in the message, use Rich's markup parsing
    if enable_markup and "[" in full_msg and "]" in full_msg:
        # Print with markup - Rich will handle the colors
        _console.print(f"[bold blue]{prefix}[/bold blue]{full_msg}", highlight=False)
    else:
        # Create styled text based on context (original behavior)
        text = Text()

        # Add prefix with color (includes timestamp if provided)
        text.append(prefix, style="bold blue")

        # Determine color based on context
        style = "white"  # Default color

        # Check if color/style is explicitly specified in context
        if "color" in context:
            style = context.get("color", "white")
        elif "style" in context:
            style = context.get("style", "white")
        else:
            # Auto-detect color based on context keys or message content
            msg_lower = full_msg.lower()

            if (
                any(k in context for k in ["error", "exception", "fail", "failed"])
                or "error" in msg_lower
                or "fail" in msg_lower
                or "exception" in msg_lower
            ):
                style = "bold red"
            elif (
                any(k in context for k in ["warning", "warn"])
                or "warning" in msg_lower
                or "warn" in msg_lower
            ):
                style = "bold yellow"
            elif (
                any(k in context for k in ["success", "complete", "done"])
                or "success" in msg_lower
                or "complete" in msg_lower
            ):
                style = "bold green"
            elif any(k in context for k in ["info", "message"]):
                style = "cyan"
            elif (
                any(k in context for k in ["agent", "agent_id", "process"])
                or "agent" in msg_lower
            ):
                style = "magenta"
            elif (
                any(k in context for k in ["performance", "duration", "time"])
                or "performance" in msg_lower
            ):
                style = "blue"

        # Add the message with determined style
        text.append(full_msg, style=style)

        # Print to console immediately
        _console.print(text, highlight=False)


def _setup_debug_logger() -> None:
    """Setup debug logger once when first debug call is made."""
    global _debug_logger, _console

    _debug_logger = logging.getLogger(DEBUG_LOGGER_NAME)
    _debug_logger.setLevel(logging.DEBUG)

    # Setup Rich console if enabled
    if _USE_RICH_CONSOLE:
        _console = Console(stderr=True)  # Use stderr like logging does

    # Only add standard handler if not using Rich or for file output
    if not _USE_RICH_CONSOLE:
        # Console handler
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        _debug_logger.addHandler(handler)

    # Optional file handler (always add regardless of Rich usage)
    # Timestamp and DEBUG_PREFIX added in debug() function, but add asctime for file logging
    debug_file = os.getenv(ENV_DEBUG_FILE)
    if debug_file:
        file_handler = logging.FileHandler(debug_file)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        _debug_logger.addHandler(file_handler)

    # Prevent propagation to root logger
    _debug_logger.propagate = False


def is_debug_enabled() -> bool:
    """Check if debug logging is enabled."""
    return config.debug
