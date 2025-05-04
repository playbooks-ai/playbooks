"""Execution state management for the interpreter.

This module provides the ExecutionState class, which encapsulates the state
tracked during interpreter execution, including call stack, exit conditions,
and execution control flags.
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from playbooks.artifacts import Artifacts
from playbooks.call_stack import CallStack
from playbooks.session_log import SessionLog
from playbooks.variables import Variables


@dataclass
class ExecutionState:
    # Core execution state
    session_log: SessionLog = field(default_factory=SessionLog)
    call_stack: CallStack = field(default_factory=CallStack)
    variables: Variables = field(default_factory=Variables)
    artifacts: Artifacts = field(default_factory=Artifacts)

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
