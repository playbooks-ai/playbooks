from typing import NamedTuple


class ToolCall(NamedTuple):
    fn: str
    args: list
    kwargs: dict

    def __str__(self):
        code = []
        code.append(self.fn)
        code.append("(")
        if self.args:
            code.append(", ".join(self.args))
        if self.kwargs:
            code.append(", ".join(f"{k}={v}" for k, v in self.kwargs.items()))
        code.append(")")
        code = "".join(code)

        return code


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
