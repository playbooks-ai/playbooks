from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generator, Optional

if TYPE_CHECKING:
    # Import types only for type checking to avoid circular imports
    from .types import AgentResponseChunk


class BaseAgent(ABC):
    """
    Abstract base class for all agent implementations.

    Agents are entities that can process messages and generate responses. This class
    defines the common interface that all agent implementations must adhere to.

    Attributes:
        klass: A string identifier for the agent class/type.
    """

    def __init__(self, klass: str):
        """
        Initialize a new BaseAgent.

        Args:
            klass: The class/type identifier for this agent.
        """
        self.klass = klass

    @abstractmethod
    def process_message(
        self,
        message: str,
        from_agent: Optional["BaseAgent"],
        routing_type: str,
        llm_config: Optional[dict] = None,
        stream: bool = False,
    ) -> Generator["AgentResponseChunk", None, None]:
        """
        Process an incoming message and generate a response.

        Args:
            message: The message content to process.
            from_agent: The agent that sent the message, if any.
            routing_type: The type of routing used for the message (e.g., "direct").
            llm_config: Configuration for language model, if applicable.
            stream: Whether to stream the response incrementally.

        Returns:
            A generator yielding response chunks.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement process_message()")
