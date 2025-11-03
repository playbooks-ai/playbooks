"""Playbook call tracking and result handling.

This module provides classes for tracking playbook function calls,
their arguments, and execution results during playbook runtime.
"""

from typing import Any, Dict, List, Optional

from playbooks.session_log import SessionLogItem
from playbooks.variables import Artifact


class PlaybookCall(SessionLogItem):
    """Represents a playbook function call with arguments and metadata."""

    def __init__(
        self,
        playbook_klass: str,
        args: List[Any],
        kwargs: Dict[str, Any],
        variable_to_assign: Optional[str] = None,
        type_annotation: Optional[str] = None,
    ) -> None:
        """Initialize a playbook call.

        Args:
            playbook_klass: Name of the playbook being called
            args: Positional arguments for the call
            kwargs: Keyword arguments for the call
            variable_to_assign: Variable name to assign result to (e.g., "$result")
            type_annotation: Expected return type annotation (e.g., "bool")
        """
        self.playbook_klass = playbook_klass
        self.args = args
        self.kwargs = kwargs
        self.variable_to_assign = variable_to_assign  # e.g., "$result"
        self.type_annotation = type_annotation  # e.g., "bool"

    def __str__(self) -> str:
        """Return formatted string representation of the playbook call.

        Formats arguments and keyword arguments using proper syntax,
        handling VariableReference, LiteralValue, and Artifact types.

        Returns:
            String like "PlaybookName(arg1, arg2, kwarg=value)"
        """
        from playbooks.argument_types import LiteralValue, VariableReference
        from playbooks.variables import Artifact

        code = [self.playbook_klass, "("]

        # Format args
        if self.args:
            formatted_args = []
            for arg in self.args:
                if isinstance(arg, VariableReference):
                    formatted_args.append(arg.reference)  # Show "$var"
                elif isinstance(arg, LiteralValue):
                    formatted_args.append(repr(arg.value))
                elif isinstance(arg, Artifact):
                    formatted_args.append(f"${arg.name}")  # Show reference
                else:
                    formatted_args.append(str(arg))
            code.append(", ".join(formatted_args))

        # Format kwargs
        if self.kwargs:
            if self.args:
                code.append(", ")
            formatted_kwargs = []
            for k, v in self.kwargs.items():
                if isinstance(v, VariableReference):
                    formatted_kwargs.append(f"{k}={v.reference}")
                elif isinstance(v, LiteralValue):
                    formatted_kwargs.append(f"{k}={repr(v.value)}")
                elif isinstance(v, Artifact):
                    formatted_kwargs.append(f"{k}=${v.name}")
                else:
                    formatted_kwargs.append(f"{k}={v}")
            code.append(", ".join(formatted_kwargs))

        code.append(")")
        return "".join(code)

    def to_log_full(self) -> str:
        """Return full log representation of the call.

        Returns:
            Formatted string representation of the playbook call
        """
        return str(self)


class PlaybookCallResult(SessionLogItem):
    """Represents the result of executing a playbook call."""

    def __init__(
        self, call: PlaybookCall, result: Any, execution_summary: Optional[str] = None
    ) -> None:
        """Initialize a playbook call result.

        Args:
            call: The playbook call that was executed
            result: The return value from the playbook execution
            execution_summary: Optional summary of execution (for logging)
        """
        self.call = call
        self.result = result
        self.execution_summary = execution_summary

    def __str__(self) -> str:
        """Return string representation of the result."""
        return self.to_log(str(self.result))

    def to_log(self, result_str: str) -> str:
        """Format log message for this result.

        Args:
            result_str: String representation of the result value

        Returns:
            Formatted log message (empty string for Say/SaveArtifact calls)
        """
        if (
            self.call.playbook_klass == "Say"
            or self.call.playbook_klass == "SaveArtifact"
        ):
            return ""

        output = []
        if self.execution_summary:
            output.append(self.execution_summary)

        if self.result is None:
            output.append(f"{self.call.to_log_full()} finished")
        else:
            output.append(f"{self.call.to_log_full()} → {result_str}")

        return "\n".join(output)

    def to_log_full(self) -> str:
        """Return full log representation including formatted result.

        Handles special formatting for lists and artifacts.

        Returns:
            Formatted log message with result details
        """
        # if result is a list, join str() of items with newlines
        result_str: Optional[str] = None
        if isinstance(self.result, list):
            result_str = "\n".join([str(item) for item in self.result])
        elif isinstance(self.result, Artifact):
            result_str = (
                f'Artifact ${self.result.name} with summary "{self.result.summary}"'
            )
        else:
            result_str = str(self.result)
        return self.to_log(result_str if result_str else "")
