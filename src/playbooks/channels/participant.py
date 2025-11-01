"""Participant interface for channel communication."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents.base_agent import BaseAgent
    from ..message import Message


class Participant(ABC):
    """Base interface for all channel participants.

    Participants can be agents, humans, or remote entities.
    The participant abstraction enables polymorphic message delivery.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """Get the unique identifier for this participant."""
        pass

    @property
    @abstractmethod
    def klass(self) -> str:
        """Get the class/type of this participant."""
        pass

    @abstractmethod
    async def deliver(self, message: "Message") -> None:
        """Deliver a message to this participant.

        Args:
            message: The message to deliver
        """
        pass


class AgentParticipant(Participant):
    """AI Agent participant."""

    def __init__(self, agent: "BaseAgent"):
        """Initialize agent participant.

        Args:
            agent: The agent instance
        """
        self.agent = agent

    @property
    def id(self) -> str:
        """Get agent ID."""
        return self.agent.id

    @property
    def klass(self) -> str:
        """Get agent class."""
        return self.agent.klass

    async def deliver(self, message: "Message") -> None:
        """Deliver message to agent's buffer.

        Args:
            message: The message to deliver
        """
        await self.agent._add_message_to_buffer(message)

    def __repr__(self) -> str:
        return f"AgentParticipant({self.klass}:{self.id})"


class HumanParticipant(Participant):
    """Human participant (terminal, web, etc.).

    Note: Human message delivery is handled by observers, not direct delivery.
    This allows the same human participant to be displayed in multiple ways
    (terminal, web UI, etc.) by subscribing different observers.
    """

    def __init__(
        self,
        human_id: str = "human",
        human_klass: str = "human",
        agent: "BaseAgent" = None,
    ):
        """Initialize human participant.

        Args:
            human_id: Unique identifier for this human
            human_klass: Class/type identifier for this human
            agent: Optional HumanAgent instance for buffer delivery
        """
        self._id = human_id
        self._klass = human_klass
        self.agent = agent  # Optional reference for testing/direct delivery

    @property
    def id(self) -> str:
        """Get human ID."""
        return self._id

    @property
    def klass(self) -> str:
        """Get human class."""
        return self._klass

    async def deliver(self, message: "Message") -> None:
        """Deliver message to human agent's buffer if available.

        If an agent reference is provided, delivers to buffer.
        Otherwise, this is a no-op (observers handle display).

        Args:
            message: The message to deliver
        """
        if self.agent:
            await self.agent._add_message_to_buffer(message)

    def __repr__(self) -> str:
        return f"HumanParticipant({self.klass}:{self.id})"
