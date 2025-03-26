from typing import Dict, Generator, List, Optional

from playbooks.interpreter.output_item import OutputItem
from playbooks.trace_mixin import TraceMixin
from playbooks.types import AgentResponseChunk
from playbooks.utils.llm_helper import get_completion


class LLMCall(TraceMixin):
    """Represents a call to an LLM.

    This class encapsulates a call to an LLM, including the configuration,
    messages, and execution parameters. It provides methods for executing
    the call and tracing the results.
    """

    def __init__(
        self,
        llm_config,
        messages: List[Dict[str, str]],
        stream: bool = False,
        json_mode: bool = False,
        session_id: Optional[str] = None,
    ):
        """Initialize an LLM call.

        Args:
            llm_config: The LLM configuration.
            messages: The messages to send to the LLM.
            stream: Whether to stream the response.
            json_mode: Whether to use JSON mode.
        """
        super().__init__()
        self.llm_config = llm_config
        self.messages = messages
        self.stream = stream
        self.json_mode = json_mode
        self._trace_items: List[OutputItem] = []
        self.session_id = session_id
        self.response = None

    def get_trace_items(self) -> List[OutputItem]:
        return {}

    def execute(self) -> Generator[AgentResponseChunk, None, None]:
        """Execute the LLM call.

        Returns:
            A generator of agent response chunks.
        """
        # Execute the LLM call
        response_chunks = []

        for chunk in get_completion(
            self.llm_config,
            self.messages,
            stream=self.stream,
            json_mode=self.json_mode,
            session_id=self.session_id,
            langfuse_span=self.langfuse_span,
        ):
            response_chunks.append(chunk)
            yield AgentResponseChunk(raw=chunk)

        # Move token counting outside the loop
        self.response = "".join(response_chunks)

    def to_session_context(self) -> str:
        """Return a session context representation of the LLM call.

        Returns:
            A session context representation of the LLM call.
        """
        return self.response

    def __repr__(self) -> str:
        """Return a string representation of the LLM call.

        Returns:
            A string representation of the LLM call.
        """
        return f"LLMCall({self.llm_config.model})"
