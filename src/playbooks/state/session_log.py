"""Session logging system for playbook execution.

This module provides logging infrastructure for tracking playbook execution,
including message logs, variable changes, and execution state for debugging
and monitoring purposes.
"""

import textwrap
from abc import ABC
from typing import Dict, Iterator, List

from playbooks.llm.messages.timestamp import get_timestamp


class SessionLogItem(ABC):
    """Base class for all session log items."""

    def shorten(
        self, message: str, max_length: int = 100, placeholder: str = "..."
    ) -> str:
        """Shorten a message to fit within max_length.

        Args:
            message: Message to shorten
            max_length: Maximum length of the shortened message
            placeholder: String to append when shortening

        Returns:
            Shortened message or empty string if too short after shortening
        """
        if len(message) <= max_length:
            return message
        message = textwrap.shorten(message, max_length, placeholder=placeholder)
        if len(message) < 10 + len(placeholder):
            return ""
        else:
            return message


class SessionLogItemMessage(SessionLogItem):
    """Simple text message log item."""

    def __init__(self, message: str) -> None:
        """Initialize a message log item.

        Args:
            message: The message text
        """
        self.message = message

    def __repr__(self) -> str:
        """Return string representation."""
        return self.message

    def to_log_full(self) -> str:
        """Return full log message."""
        return self.message


class SessionLog:
    """Log of session activity for an agent.

    Maintains a chronological list of log items representing playbook calls,
    messages, variable updates, and other execution events.
    """

    def __init__(self, klass: str, agent_id: str) -> None:
        """Initialize a session log.

        Args:
            klass: Agent class name
            agent_id: Agent identifier
        """
        self.klass = klass
        self.agent_id = agent_id
        self.log: List[Dict[str, SessionLogItem]] = []

    def add(self, item: SessionLogItem) -> None:
        """Add a log item (alias for append).

        Args:
            item: Log item to add
        """
        self.append(item)

    def __getitem__(self, index: int) -> SessionLogItem:
        """Get log item by index.

        Args:
            index: Index of the log item

        Returns:
            SessionLogItem at the given index
        """
        return self.log[index]["item"]

    def __iter__(self) -> Iterator[SessionLogItem]:
        """Iterate over log items."""
        return iter(entry["item"] for entry in self.log)

    def __len__(self) -> int:
        """Return number of log items."""
        return len(self.log)

    def __repr__(self) -> str:
        """Return string representation of the log."""
        return repr(self.log)

    def append(self, item: SessionLogItem | str) -> None:
        """Append a log item or string message.

        Args:
            item: Log item or string message to append
        """
        if isinstance(item, str):
            if not item.strip():
                return
            item = SessionLogItemMessage(item)
        self.log.append({"item": item, "timestamp": get_timestamp()})

    def __str__(self) -> str:
        """Return formatted log as string."""
        parts = []
        for item in self.log:
            message = item["item"].to_log_full()
            if message:
                parts.append(message)
        return "\n".join(parts)

    def to_log_full(self) -> str:
        """Return full formatted log with all messages.

        Returns:
            String containing all log messages joined by newlines
        """
        parts = []
        for item in self.log:
            message = item["item"].to_log_full()
            if message:
                parts.append(message)
        return "\n".join(parts)
