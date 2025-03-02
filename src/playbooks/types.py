from typing import AsyncIterator, Protocol

from typing_extensions import NamedTuple


class Agent(Protocol):
    """Protocol for agents that can process messages."""

    async def run(self, message: str) -> str:
        """Process a message and return a response."""
        ...

    async def stream(self, message: str) -> AsyncIterator[str]:
        """Process a message and stream the response."""
        ...


class ToolCall:
    def __init__(self, fn: str, args: list, kwargs: dict, retval: str = None):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.retval = retval

    def __str__(self):
        code = []
        code.append(self.fn)
        code.append("(")
        if self.args:
            code.append(", ".join([str(a) for a in self.args]))
        if self.kwargs:
            code.append(", ".join(f"{k}={v}" for k, v in self.kwargs.items()))
        code.append(")")
        code = "".join(code)

        return code

    def __repr__(self):
        return str(self)


class ToolResponse(NamedTuple):
    code: str
    output: str


class AgentResponseChunk(NamedTuple):
    """Agent response chunk."""

    """
    Attributes:
        raw: The raw response chunk from the LLM.
        tool_call: A tool call extracted from the response, if any.
        response: Output from a Say() call, if any.
    """

    raw: str | None = None
    tool_call: ToolCall | None = None
    agent_response: str | None = None
    tool_response: ToolResponse | None = None
    trace: str | None = None
