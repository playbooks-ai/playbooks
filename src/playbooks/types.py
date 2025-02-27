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
    def __init__(
        self,
        fn: str,
        args: list,
        kwargs: dict,
        retval: str = None,
        yield_type: str = None,
    ):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.retval = retval
        self.yield_type = yield_type

        # Cached properties
        self._is_say = None
        self._wait_for_user_input = None
        self._playbook = None
        self._is_internal_playbook_call = None
        self._is_external_playbook_call = None

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

    def annotate(self, playbooks):
        """Annotate this tool call with additional information.

        Args:
            playbooks: Dictionary of available playbooks
        """
        self._is_say = self.fn == "Say"
        self._wait_for_user_input = self._is_say and self.kwargs.get(
            "waitForUserInput", False
        )
        self._playbook = playbooks.get(self.fn)

        from playbooks.enums import PlaybookExecutionType

        if self._playbook:
            self._is_internal_playbook_call = (
                self._playbook.execution_type == PlaybookExecutionType.INT
            )
            self._is_external_playbook_call = (
                self._playbook.execution_type == PlaybookExecutionType.EXT
            )
        else:
            self._is_internal_playbook_call = False
            self._is_external_playbook_call = False

    @property
    def is_say(self):
        """Check if this is a Say call."""
        if self._is_say is None:
            self._is_say = self.fn == "Say"
        return self._is_say

    @property
    def wait_for_user_input(self):
        """Check if this call waits for user input."""
        if self._wait_for_user_input is None:
            self._wait_for_user_input = self.is_say and self.kwargs.get(
                "waitForUserInput", False
            )
        return self._wait_for_user_input

    @property
    def is_internal_playbook_call(self):
        """Check if this is an internal playbook call."""
        return self._is_internal_playbook_call

    @property
    def is_external_playbook_call(self):
        """Check if this is an external playbook call."""
        return self._is_external_playbook_call

    @property
    def playbook(self):
        """Get the playbook for this call."""
        return self._playbook


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
