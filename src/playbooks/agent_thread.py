"""Agent thread module for the playbooks package."""

import uuid
from typing import TYPE_CHECKING, Any, Dict, Generator

from playbooks.enums import RoutingType
from playbooks.interpreter.execution_state import ExecutionState
from playbooks.interpreter.interpreter import Interpreter
from playbooks.playbook import Playbook
from playbooks.trace_mixin import TraceMixin
from playbooks.utils.langfuse_helper import LangfuseHelper

if TYPE_CHECKING:
    from playbooks.agent import Agent
    from playbooks.config import LLMConfig
    from playbooks.types import AgentResponseChunk


class Message(TraceMixin):
    """A message in an agent thread.

    This class represents a message in an agent thread, including its
    content, routing type, and sender information.

    Attributes:
        content: The content of the message.
        from_agent: The sender of the message.
        routing_type: The routing type of the message.
        state: The execution state associated with this message.
        langfuse: The Langfuse helper instance for tracing.
    """

    def __init__(
        self,
        content: str,
        routing_type: RoutingType,
        from_agent: str = "User",
        state: ExecutionState = None,
    ):
        """Initialize a message.

        Args:
            content: The content of the message.
            routing_type: The routing type of the message.
            from_agent: The sender of the message.
            state: The execution state to use for this message.
        """
        super().__init__()
        self.content = content
        self.from_agent = from_agent
        self.routing_type = routing_type
        self.state = state
        self.langfuse = LangfuseHelper.instance()

    def get_trace_metadata(self) -> Dict[str, Any]:
        """Get metadata for tracing this message.

        Returns:
            Dictionary containing trace metadata.
        """
        return {
            "content": self.content,
            "routing_type": self.routing_type,
            "from_agent": self.from_agent,
        }

    def execute(
        self,
        playbooks: Dict[str, Playbook],
        llm_config: "LLMConfig",
        stream: bool,
    ) -> Generator["AgentResponseChunk", None, None]:
        """Execute a message using the interpreter.

        Args:
            playbooks: The playbooks to use for execution.
            llm_config: The LLM configuration to use.
            stream: Whether to stream the response.

        Yields:
            AgentResponseChunk objects representing the response.
        """
        self.state.add_conversation_history(self.__repr__())

        # Create instruction from message
        instruction = self.__repr__()

        # Create interpreter
        interpreter = Interpreter(state=self.state)
        self.state.interpreter = interpreter
        self.trace(interpreter)

        # Execute the interpreter
        yield from interpreter.execute(
            playbooks=playbooks,
            instruction=instruction,
            llm_config=llm_config,
            stream=stream,
        )

    def __repr__(self) -> str:
        """Return a string representation of the message.

        Returns:
            A string representation of the message.
        """
        return f'{self.from_agent if self.from_agent else "System"}: {self.content}'


class AgentThread(TraceMixin):
    """An agent thread.

    This class represents a thread of interaction between agents, managing
    state and message processing.

    Attributes:
        id: Unique identifier for this thread.
        agent_id: The ID of the associated agent.
        agent_klass: The class of the associated agent.
        playbooks: The playbooks available to this thread.
        state: The execution state for this thread.
        langfuse_span: The Langfuse span for tracing this thread.
    """

    def __init__(self, agent: "Agent", playbooks: Dict[str, Playbook]):
        """Initialize an agent thread.

        Args:
            agent: The agent associated with this thread.
            playbooks: The playbooks available to this thread.
        """
        super().__init__()
        self.id = str(uuid.uuid4())
        self.agent_id = agent.id
        self.agent_klass = agent.klass
        self.playbooks = playbooks
        self.state = ExecutionState()
        self.state.agent = agent
        self.state.agent_thread = self
        self.langfuse_span = LangfuseHelper.instance().trace(
            name="agent_thread",
            metadata=self.get_trace_metadata(),
        )

    def get_trace_metadata(self) -> Dict[str, Any]:
        """Get metadata for tracing this thread.

        Returns:
            Dictionary containing trace metadata.
        """
        return {
            "agent_thread_id": self.id,
            "agent_id": self.agent_id,
            "agent_klass": self.agent_klass,
        }

    def __repr__(self) -> str:
        """Return a string representation of the agent thread.

        Returns:
            A string representation of the agent thread.
        """
        return f"AgentThread({self.agent_klass})"

    def process_message(
        self,
        message: str,
        from_agent: Any,
        routing_type: str,
        llm_config: "LLMConfig",
        stream: bool,
    ) -> Generator["AgentResponseChunk", None, None]:
        """Process a message and return response chunks.

        Args:
            message: The message to process.
            from_agent: The agent that sent the message.
            routing_type: The routing type of the message.
            llm_config: The LLM configuration to use.
            stream: Whether to stream the response.

        Yields:
            AgentResponseChunk objects representing the response.
        """
        message_obj = Message(
            content=message,
            routing_type=routing_type,
            from_agent=from_agent,
            state=self.state,
        )

        self.trace(message_obj)

        yield from message_obj.execute(
            playbooks=self.playbooks, llm_config=llm_config, stream=stream
        )
