import uuid
from typing import TYPE_CHECKING, Dict, Generator, Optional

from .agent_thread import AgentThread
from .base_agent import BaseAgent
from .exceptions import (
    AgentAlreadyRunningError,
    AgentConfigurationError,
)
from .playbook import Playbook

if TYPE_CHECKING:
    from playbooks.config import LLMConfig
    from playbooks.types import AgentResponseChunk


class Agent(BaseAgent):
    """
    Base class for AI agents.

    An Agent represents an AI entity capable of processing messages through playbooks
    using a main execution thread.

    Attributes:
        id: Unique identifier for this agent.
        klass: The class/type of this agent.
        description: Human-readable description of the agent.
        playbooks: Dictionary of playbooks available to this agent.
        main_thread: The primary execution thread for this agent.
    """

    def __init__(
        self,
        klass: str,
        description: str,
        playbooks: Dict[str, Playbook] = None,
    ):
        """Initialize a new Agent.

        Args:
            klass: The class/type of this agent.
            description: Human-readable description of the agent.
            playbooks: Dictionary of playbooks available to this agent.
        """
        super().__init__(klass)
        self.id = str(uuid.uuid4())
        self.description = description
        self.playbooks = playbooks or {}
        self.main_thread: Optional[AgentThread] = None

    def run(
        self, llm_config: "LLMConfig", stream: bool
    ) -> Generator["AgentResponseChunk", None, None]:
        """Run the agent with the initial 'Begin' message.

        Args:
            llm_config: Configuration for the language model.
            stream: Whether to stream the response.

        Yields:
            Response chunks from processing the initial message.

        Raises:
            AgentAlreadyRunningError: If the agent is already running.
        """
        if self.main_thread is not None:
            raise AgentAlreadyRunningError("AI agent is already running")

        # TODO: add support for filtering playbooks
        yield from self.process_message(
            message="Begin",
            from_agent=None,
            routing_type="direct",
            llm_config=llm_config,
            stream=stream,
        )

    def process_message(
        self,
        message: str,
        from_agent: Optional["Agent"],
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
            Response chunks from processing the message.

        Raises:
            AgentConfigurationError: If no playbooks are defined.
        """
        if not self.playbooks:
            raise AgentConfigurationError("No playbooks defined for AI agent")

        if self.main_thread is None:
            self.main_thread = AgentThread(
                agent=self,
                playbooks=self.playbooks,
            )

        yield from self.main_thread.process_message(
            message=message,
            from_agent=from_agent,
            routing_type=routing_type,
            llm_config=llm_config,
            stream=stream,
        )

    def __repr__(self) -> str:
        """Return string representation of the Agent.

        Returns:
            The class name of this agent.
        """
        return self.klass
