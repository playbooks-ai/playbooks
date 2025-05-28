"""Execution state management for the interpreter.

This module provides the ExecutionState class, which encapsulates the state
tracked during interpreter execution, including call stack, exit conditions,
and execution control flags.
"""

from typing import Any, Dict

from playbooks.artifacts import Artifacts
from playbooks.call_stack import CallStack
from playbooks.event_bus import EventBus
from playbooks.session_log import SessionLog
from playbooks.variables import Variables


class ExecutionState:
    """Encapsulates execution state including call stack, variables, and artifacts.

    Attributes:
        bus: The event bus
        session_log: Log of session activity
        call_stack: Stack tracking the execution path
        variables: Collection of variables with change history
        artifacts: Store for execution artifacts
    """

    def __init__(self, event_bus: EventBus):
        """Initialize execution state with an event bus.

        Args:
            bus: The event bus to use for all components
        """
        self.event_bus = event_bus
        self.session_log = SessionLog()
        self.call_stack = CallStack(event_bus)
        self.variables = Variables(event_bus)
        self.artifacts = Artifacts()
        self.last_llm_response = ""

    def __repr__(self) -> str:
        """Return a string representation of the execution state."""
        return f"{self.call_stack.__repr__()};{self.variables.__repr__()};{self.artifacts.__repr__()}"

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of the execution state."""
        return {
            "call_stack": self.call_stack.to_dict(),
            "variables": self.variables.to_dict(),
            "artifacts": self.artifacts.to_dict(),
        }

    def __str__(self) -> str:
        """Return a string representation of the execution state."""
        return f"ExecutionState(call_stack={self.call_stack}, variables={self.variables}, session_log={self.session_log})"
