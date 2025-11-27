"""
Clean user-facing output for all Playbooks applications.

Usage:
    from playbooks.infrastructure.user_output import user_output

    user_output.agent_message("assistant", "Processing your request...")
    user_output.success("Playbook completed successfully")
    user_output.error("Connection failed", details="Check network settings")
"""

import json
from typing import Optional, Protocol, Any, Callable
from rich.console import Console


class OutputHandler(Protocol):
    """Interface for different output handlers."""

    def display(self, message: str, level: str = "info", **context: Any) -> None: ...


class ConsoleHandler:
    """Rich console output for CLI applications."""

    def __init__(self) -> None:
        # Use stderr for all console output (diagnostics)
        self.console: Console = Console(stderr=True)

    def display(self, message: str, level: str = "info", **context: Any) -> None:
        if level == "error":
            self.console.print(f"[red]✗[/red] {message}")
        elif level == "success":
            self.console.print(f"[green]✓[/green] {message}")
        elif level == "agent":
            agent_name = context.get("agent_name", "Agent")
            if context.get("streaming"):
                self.console.print(f"\n[green]{agent_name}:[/green] ", end="")
            else:
                self.console.print(f"\n[green]{agent_name}:[/green] {message}")
        elif level == "info":
            self.console.print(f"[blue]ℹ[/blue] {message}")
        else:
            self.console.print(message)


class WebSocketHandler:
    """JSON event output for web applications."""

    def __init__(self, emit_func: Callable[[str], None]) -> None:
        self.emit: Callable[[str], None] = emit_func

    def display(self, message: str, level: str = "info", **context: Any) -> None:
        event = {
            "type": f"user_output_{level}",
            "message": message,
            "timestamp": context.get("timestamp"),
            **{k: v for k, v in context.items() if k != "timestamp"},
        }
        self.emit(json.dumps(event))


class SilentHandler:
    """Silent handler for testing or headless operation."""

    def display(self, message: str, level: str = "info", **context: Any) -> None:
        pass  # Do nothing


class UserOutput:
    """Simple user output system with pluggable handlers."""

    def __init__(self, handler: Optional[OutputHandler] = None) -> None:
        self.handler: OutputHandler = handler or ConsoleHandler()

    def agent_message(
        self, agent_name: str, content: str, streaming: bool = False
    ) -> None:
        """Display agent message with rich formatting."""
        self.handler.display(
            content, level="agent", agent_name=agent_name, streaming=streaming
        )

    def success(self, message: str) -> None:
        """Display success message."""
        self.handler.display(message, level="success")

    def error(self, message: str, details: Optional[str] = None) -> None:
        """Display error message with optional details."""
        if details:
            full_message = f"{message}: {details}"
        else:
            full_message = message
        self.handler.display(full_message, level="error")

    def info(self, message: str) -> None:
        """Display info message."""
        self.handler.display(message, level="info")

    def print(self, message: str) -> None:
        """Display plain message."""
        self.handler.display(message, level="plain")

    def set_handler(self, handler: OutputHandler) -> None:
        """Change the output handler."""
        self.handler = handler


# Global instance with default console handler
user_output: UserOutput = UserOutput()


def setup_for_web(emit_function: Callable[[str], None]) -> None:
    """Configure for web applications with WebSocket handler."""
    user_output.set_handler(WebSocketHandler(emit_function))


def setup_for_testing() -> None:
    """Configure for testing with silent handler."""
    user_output.set_handler(SilentHandler())


def setup_for_console() -> None:
    """Configure for console applications (default)."""
    user_output.set_handler(ConsoleHandler())
