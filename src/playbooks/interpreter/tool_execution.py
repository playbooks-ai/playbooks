"""Tool execution module for the interpreter."""

from typing import Any, Dict, Optional

from playbooks.trace_mixin import TraceMixin
from playbooks.types import ToolCall


class ToolExecutionResult:
    """Result of a tool execution.

    This class represents the result of a tool execution, including the
    tool call details, result value, and any error information.

    This is the canonical implementation of ToolExecutionResult.
    Always import this class from playbooks.interpreter.tool_execution.

    Attributes:
        tool_call: The ToolCall object that was executed.
        result: The result of the function execution.
        error: The error that occurred during execution, if any.
        message: A message describing the result.
    """

    def __init__(
        self,
        tool_call: ToolCall,
        result: Any = None,
        error: Optional[Exception] = None,
        message: Optional[str] = None,
    ):
        """Initialize a tool execution result.

        Args:
            tool_call: The ToolCall object that was executed.
            result: The result of the function execution.
            error: The error that occurred during execution, if any.
            message: A message describing the result.
        """
        self.tool_call: ToolCall = tool_call
        self.result: Any = result
        self.error: Optional[Exception] = error
        self.message: Optional[str] = message

    def __repr__(self) -> str:
        """Return a string representation of the tool execution result.

        Returns:
            A string representation of the tool execution result.
        """
        if self.error:
            return f"{self.tool_call} returned error {self.error}"
        return f"{self.tool_call} returned {self.result}"

    # Use __repr__ for all string conversion methods
    to_trace = __repr__
    to_session_context = __repr__
    __str__ = __repr__


class ToolExecution(TraceMixin):
    """Execution of a tool.

    This class represents the execution of a tool, including its
    tool call details and execution result.

    Attributes:
        tool_call: The ToolCall object to be executed.
        result: The ToolExecutionResult after execution.
    """

    def __init__(
        self,
        tool_call: ToolCall,
    ):
        """Initialize a tool execution.

        Args:
            tool_call: The ToolCall object to be executed.
        """
        super().__init__()
        self.tool_call: ToolCall = tool_call
        self.result: Optional[ToolExecutionResult] = None

    def get_trace_metadata(self) -> Dict[str, Any]:
        """Get metadata for tracing.

        Returns:
            Dictionary containing trace metadata.
        """
        return {
            "tool_call": self.tool_call,
        }

    def execute(self, func: callable) -> ToolExecutionResult:
        """Execute the tool.

        This method executes the tool, tracing the execution and returning
        the result.

        Args:
            func: The function to execute.

        Returns:
            The result of the tool execution.
        """
        self.trace(f"Executing tool {self.tool_call}")

        try:
            # Sanitize kwargs by removing any leading $ in keys
            kwargs = {k.lstrip("$"): v for k, v in self.tool_call.kwargs.items()}

            # If values start with $, then use that variable's value
            for k, v in kwargs.items():
                if isinstance(v, str) and v.startswith("$"):
                    # Check if state and variables exist before accessing
                    if hasattr(self, "state") and hasattr(self.state, "variables"):
                        kwargs[k] = self.state.variables.get(v.strip(), v)

            result = func(*self.tool_call.args, **kwargs)

            # Create the result object
            tool_result = ToolExecutionResult(
                tool_call=self.tool_call,
                result=result,
                message=f"Tool {self.tool_call.fn} executed successfully",
            )
            self.result = tool_result

            # Trace the result object
            self.trace(
                tool_result,
                metadata={
                    "tool_call": self.tool_call,
                    "result": result,
                },
            )

            return tool_result
        except Exception as e:
            import traceback

            # Create the error result object
            error_result = ToolExecutionResult(
                tool_call=self.tool_call,
                error=e,
                message=f"Error executing tool {self.tool_call.fn}: {str(e)}",
            )
            self.result = error_result

            # Trace the error result object
            self.trace(
                error_result,
                metadata={
                    "tool_call": self.tool_call,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                },
                level="ERROR",
            )

            return error_result

    def __repr__(self) -> str:
        """Return a string representation of the tool execution.

        Returns:
            A string representation of the tool execution.
        """
        return f"{self.result}"
