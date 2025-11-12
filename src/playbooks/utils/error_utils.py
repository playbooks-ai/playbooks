"""
Utility functions for error handling and visibility across the playbooks framework.
"""

import logging
from typing import List, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

logger = logging.getLogger(__name__)
console = Console(stderr=True)  # All error output to stderr


def print_agent_errors_summary(
    errors: List[Dict[str, Any]], title: str = "Agent Errors"
) -> None:
    """Print a formatted summary of agent errors for CLI visibility.

    Args:
        errors: List of error dictionaries from get_agent_errors()
        title: Title for the error summary panel
    """
    if not errors:
        return

    error_text = Text()
    error_text.append(f"Found {len(errors)} agent error(s):\n\n", style="bold red")

    for i, error_info in enumerate(errors, 1):
        error_text.append(f"{i}. ", style="bold")
        error_text.append(f"Agent {error_info['agent_name']}", style="cyan")
        error_text.append(f" ({error_info['agent_id']})\n", style="dim cyan")
        error_text.append("   Error: ", style="bold")
        error_text.append(f"{error_info['error_type']}: ", style="yellow")
        error_text.append(f"{error_info['error']}\n\n", style="red")

    error_text.append(
        "💡 Check logs with --verbose for full stack traces", style="dim yellow"
    )

    panel = Panel(error_text, title=f"⚠️  {title}", border_style="red", expand=False)
    console.print(panel)


def log_agent_errors(errors: List[Dict[str, Any]], context: str = "execution") -> None:
    """Log agent errors to structured logging for debugging.

    Args:
        errors: List of error dictionaries from get_agent_errors()
        context: Context where the errors occurred (e.g., "execution", "test", "initialization")
    """
    if not errors:
        return

    logger.error(f"Agent errors detected during {context}: {len(errors)} error(s)")

    for error_info in errors:
        logger.error(
            f"Agent error - Agent: {error_info['agent_name']} ({error_info['agent_id']}), "
            f"Error: {error_info['error_type']}: {error_info['error']}",
            extra={
                "agent_id": error_info["agent_id"],
                "agent_name": error_info["agent_name"],
                "error_type": error_info["error_type"],
                "error_message": error_info["error"],
                "context": context,
            },
            exc_info=error_info.get("error_obj"),
        )


def raise_on_agent_errors(
    errors: List[Dict[str, Any]], context: str = "execution"
) -> None:
    """Raise an exception if agent errors are present, for use in tests and strict contexts.

    Args:
        errors: List of error dictionaries from get_agent_errors()
        context: Context where the errors occurred

    Raises:
        RuntimeError: If any agent errors are present
    """
    if not errors:
        return

    error_summary = f"Agent errors detected during {context}:\n"
    for error_info in errors:
        error_summary += f"  - Agent {error_info['agent_name']}: {error_info['error_type']} - {error_info['error']}\n"

    raise RuntimeError(error_summary.strip())


def check_playbooks_health(
    playbooks: Any,
    print_errors: bool = True,
    log_errors: bool = True,
    raise_on_errors: bool = False,
    context: str = "execution",
) -> Dict[str, Any]:
    """Comprehensive health check for a Playbooks instance.

    Args:
        playbooks: Playbooks instance to check
        print_errors: Whether to print errors to console
        log_errors: Whether to log errors to structured logging
        raise_on_errors: Whether to raise an exception if errors are found
        context: Context for error reporting

    Returns:
        Dictionary with health status and error information

    Raises:
        RuntimeError: If raise_on_errors=True and errors are found
    """
    if not playbooks or not playbooks.program:
        return {
            "status": "not_initialized",
            "has_errors": False,
            "error_count": 0,
            "errors": [],
        }

    health = playbooks.check_execution_health()

    if health["has_errors"]:
        errors = health["errors"]

        if log_errors:
            log_agent_errors(errors, context)

        if print_errors:
            print_agent_errors_summary(
                errors, f"Playbooks Health Check - {context.title()}"
            )

        if raise_on_errors:
            raise_on_agent_errors(errors, context)

    return health


class PlaybooksErrorChecker:
    """Context manager for automatic error checking in playbooks execution.

    Usage:
        with PlaybooksErrorChecker(playbooks, raise_on_errors=True):
            await playbooks.program.run_till_exit()
    """

    def __init__(
        self,
        playbooks: Any,
        print_errors: bool = True,
        log_errors: bool = True,
        raise_on_errors: bool = False,
        context: str = "execution",
    ) -> None:
        """Initialize error checker.

        Args:
            playbooks: Playbooks instance to monitor
            print_errors: Whether to print errors to console
            log_errors: Whether to log errors to structured logging
            raise_on_errors: Whether to raise exception if errors found
            context: Context string for error reporting
        """
        self.playbooks = playbooks
        self.print_errors = print_errors
        self.log_errors = log_errors
        self.raise_on_errors = raise_on_errors
        self.context = context

    def __enter__(self) -> "PlaybooksErrorChecker":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Exit context manager and check for errors.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)

        Returns:
            False (doesn't suppress exceptions)
        """
        check_playbooks_health(
            self.playbooks,
            print_errors=self.print_errors,
            log_errors=self.log_errors,
            raise_on_errors=self.raise_on_errors,
            context=self.context,
        )
        return False  # Don't suppress exceptions
