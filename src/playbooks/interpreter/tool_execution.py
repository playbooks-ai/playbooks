"""Tool execution module for the interpreter."""

from typing import TYPE_CHECKING, Dict, Generator

from ..enums import PlaybookExecutionType
from ..trace_mixin import TraceItem, TraceMixin
from ..types import AgentResponseChunk, ToolCall

if TYPE_CHECKING:
    from ..playbook import Playbook
    from .interpreter import Interpreter


class ToolExecutionResult(TraceItem):
    """Result of a tool execution."""

    def __init__(self, message: str, tool_call: ToolCall):
        """Initialize a tool execution result.

        Args:
            message: The message from the tool execution.
            tool_call: The tool call that was executed.
        """
        super().__init__(item=message, metadata={"tool_call": tool_call})
        self.tool_call = tool_call

    def __repr__(self):
        """Return a string representation of the tool execution result."""
        return self.tool_call.__repr__() + ": " + self.item


class ToolExecution(TraceMixin):
    """Represents the execution of a tool."""

    def __init__(
        self,
        interpreter: "Interpreter",
        playbooks: Dict[str, "Playbook"],
        tool_call: ToolCall,
    ):
        """Initialize a tool execution.

        Args:
            interpreter: The interpreter executing the tool.
            playbooks: The available playbooks.
            tool_call: The tool call to execute.
        """
        super().__init__()
        self.interpreter = interpreter
        self.playbooks = playbooks
        self.tool_call = tool_call

    def execute(self) -> Generator[AgentResponseChunk, None, None]:
        """Execute the tool call.

        Returns:
            A generator of agent response chunks.
        """
        tool_call = self.tool_call
        # Look up an EXT playbook with the same name as the tool call
        ext_playbook = next(
            (
                p
                for p in self.playbooks.values()
                if p.execution_type == PlaybookExecutionType.EXT
                and p.klass == tool_call.fn
            ),
            None,
        )

        if ext_playbook is None:
            self.trace(
                ToolExecutionResult(
                    f"Error: {tool_call.fn} not found",
                    tool_call=tool_call,
                )
            )
            raise Exception(f"EXT playbook {tool_call.fn} not found")

        # If found, run the playbook
        func = ext_playbook.func
        retval = func(*tool_call.args, **tool_call.kwargs)
        self.trace(ToolExecutionResult(f"{retval}", tool_call=tool_call))
        tool_call.retval = retval
        yield AgentResponseChunk(tool_call=tool_call)

    def __repr__(self):
        """Return a string representation of the tool execution."""
        return self.tool_call.__repr__()
