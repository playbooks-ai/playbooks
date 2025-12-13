"""Playbook call tracking and result handling.

This module provides classes for tracking playbook function calls,
their arguments, and execution results during playbook runtime.
"""

from typing import Any, Dict, List, Optional

from playbooks.state.session_log import SessionLogItem
from playbooks.state.variables import Artifact


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
        # Normalize arguments - convert Message objects to dicts for consistent logging
        self.args = self._normalize_args(args)
        self.kwargs = {k: self._normalize_arg(v) for k, v in kwargs.items()}
        self.variable_to_assign = variable_to_assign  # e.g., "$result"
        self.type_annotation = type_annotation  # e.g., "bool"

    def _normalize_arg(self, arg: Any) -> Any:
        """Normalize a single argument by converting Message objects to dicts.

        This ensures consistent representation in logs and avoids serialization issues.

        Args:
            arg: Argument value to normalize

        Returns:
            Normalized argument (Messages converted to dicts)
        """
        from playbooks.core.message import Message

        if isinstance(arg, Message):
            return arg.to_dict()
        elif isinstance(arg, list):
            return [self._normalize_arg(item) for item in arg]
        elif isinstance(arg, dict) and not any(
            isinstance(v, Message) for v in arg.values()
        ):
            # Already a dict and doesn't contain Messages
            return arg
        elif isinstance(arg, dict):
            # Dict that might contain Messages
            return {k: self._normalize_arg(v) for k, v in arg.items()}
        else:
            return arg

    def _normalize_args(self, args: List[Any]) -> List[Any]:
        """Normalize all arguments in the list.

        Args:
            args: List of arguments

        Returns:
            List with normalized arguments
        """
        return [self._normalize_arg(arg) for arg in args]

    def __str__(self) -> str:
        """Return formatted string representation of the playbook call.

        Formats arguments and keyword arguments using proper syntax,
        handling VariableReference, LiteralValue, and Artifact types.

        Returns:
            String like "PlaybookName(arg1, arg2, kwarg=value)"
        """
        from playbooks.core.argument_types import LiteralValue, VariableReference
        from playbooks.state.variables import Artifact

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
                    formatted_args.append(self._format_arg(arg))
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
                    formatted_kwargs.append(f"{k}={self._format_arg(v)}")
            code.append(", ".join(formatted_kwargs))

        code.append(")")
        return "".join(code)

    def _format_arg(self, arg: Any) -> str:
        """Format a single argument for display in playbook call string.

        Uses compact representation for Message dicts and lists of message dicts.

        Args:
            arg: Argument value to format

        Returns:
            Formatted string representation of the argument
        """

        def _format_message_dict(msg_dict: Dict[str, Any]) -> str:
            """Format a message dict in the same compact style as Message.to_compact_str()."""
            from playbooks.utils.text_utils import simple_shorten

            sender_id = msg_dict.get("sender_id")
            sender_klass = msg_dict.get("sender_klass")
            recipient_id = msg_dict.get("recipient_id")
            recipient_klass = msg_dict.get("recipient_klass")
            meeting_id = msg_dict.get("meeting_id")
            message_type = msg_dict.get("message_type")
            content = simple_shorten(str(msg_dict.get("content", "")), 100)

            # Sender
            if (
                sender_id == "human"
                or sender_klass == "HumanAgent"
                or sender_klass == "User"
            ):
                sender = "User"
            else:
                sender = f"{sender_klass}({sender_id})"

            # Recipient
            if recipient_id == "human":
                recipient = "User"
            elif recipient_klass is None or recipient_id is None:
                recipient = "Everyone"
            else:
                recipient = f"{recipient_klass}({recipient_id})"

            # Meeting info
            meeting_info = ""
            if message_type == "meeting_invitation" and meeting_id:
                meeting_info = f" [MEETING_INVITATION for meeting {meeting_id}]"
            elif message_type == "meeting_broadcast" and meeting_id:
                meeting_info = f" [in meeting {meeting_id}]"

            return f"{sender} → {recipient}{meeting_info}: {content}"

        # Handle list of message dicts compactly
        if isinstance(arg, list) and len(arg) > 0:
            first_elem = arg[0]
            # Check if this looks like a list of message dicts
            if (
                isinstance(first_elem, dict)
                and "content" in first_elem
                and "sender_id" in first_elem
            ):
                if all(isinstance(item, dict) and "content" in item for item in arg):
                    formatted_messages = []
                    for msg_dict in arg:
                        formatted_messages.append(f'"{_format_message_dict(msg_dict)}"')
                    return f"[{', '.join(formatted_messages)}]"

        # Handle single message dict compactly
        if isinstance(arg, dict) and "content" in arg and "sender_id" in arg:
            return f'"{_format_message_dict(arg)}"'

        # Default to str() for other types
        return str(arg)

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
