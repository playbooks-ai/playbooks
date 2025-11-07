"""Participant interface for channel communication.

## Architectural Rationale

The Participant abstraction provides a clean boundary between the channel routing
system and message delivery mechanisms. While the current implementation has two
similar participant types (AgentParticipant and HumanParticipant), this abstraction
is retained for future extensibility.

## Why Keep This Abstraction?

1. **Extensibility for Network Participants**: Enables future support for remote agents,
   distributed systems, or external integrations without changing the channel architecture.

2. **Clean Separation of Concerns**: Keeps channel routing logic separate from delivery
   mechanisms, making the system easier to understand and test.

3. **Minimal Overhead**: The abstraction is lightweight (~150 lines) and doesn't introduce
   significant performance overhead.

4. **Future-Proofing**: Aligns with planned architecture for distributed agents and
   multi-process communication.

## Future Extensibility Use Cases

### Remote Participant (Network Communication)
```python
class RemoteParticipant(Participant):
    \"\"\"Participant connected via network (WebSocket, gRPC, etc.).\"\"\"

    def __init__(self, remote_id: str, connection):
        self._id = remote_id
        self.connection = connection

    @property
    def id(self) -> str:
        return self._id

    @property
    def klass(self) -> str:
        return "RemoteAgent"

    async def deliver(self, message: Message) -> None:
        # Serialize and send over network
        await self.connection.send_json(message.to_dict())
```

### Database Participant (Persistent Storage)
```python
class DatabaseParticipant(Participant):
    \"\"\"Participant that logs messages to database.\"\"\"

    async def deliver(self, message: Message) -> None:
        # Store message in database for audit/replay
        await self.db.insert_message(message.to_dict())
```

### External API Participant (Webhooks)
```python
class WebhookParticipant(Participant):
    \"\"\"Participant that forwards messages to external webhook.\"\"\"

    async def deliver(self, message: Message) -> None:
        # Forward to external system
        await self.http_client.post(self.webhook_url, json=message.to_dict())
```

## Design Principles

- **Interface Segregation**: Keep the Participant interface minimal (id, klass, deliver)
- **Open/Closed**: Open for extension (new participant types) but closed for modification
- **Dependency Inversion**: Channels depend on the abstraction, not concrete implementations
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from playbooks.agents.base_agent import BaseAgent
    from playbooks.core.message import Message


class Participant(ABC):
    """Base interface for all channel participants.

    This abstraction enables polymorphic message delivery across different
    participant types (local agents, humans, remote systems, external integrations).

    The interface is intentionally minimal to support diverse delivery mechanisms
    while maintaining type safety and clear contracts.
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
    """AI Agent participant for local agent instances.

    Wraps a BaseAgent instance to provide the Participant interface.
    Messages are delivered to the agent's internal message buffer.

    This implementation handles in-process AI agents, whether they are
    running LLM-based playbooks or Python-based playbooks.
    """

    def __init__(self, agent: "BaseAgent"):
        """Initialize agent participant.

        Args:
            agent: The agent instance (AIAgent or HumanAgent)
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
    """Human participant for user-facing communication.

    Represents a human user interacting with the system. Message delivery is
    primarily handled by StreamObservers (for real-time display) rather than
    direct buffer delivery. This design enables:

    1. **Multi-modal Display**: Same human can receive messages via terminal,
       web UI, mobile app, etc. by subscribing different observers

    2. **Flexible Delivery**: Supports streaming (character-by-character) or
       buffered (complete message) delivery based on observer preferences

    3. **Optional Buffering**: Can optionally deliver to HumanAgent buffer for
       testing or programmatic access

    Note: The distinction between AgentParticipant and HumanParticipant is
    important for determining when to use streaming (humans get streaming,
    agents typically don't).
    """

    def __init__(
        self,
        human_id: str = "human",
        human_klass: str = "human",
        agent: Optional["BaseAgent"] = None,
    ) -> None:
        """Initialize human participant.

        Args:
            human_id: Unique identifier for this human (e.g., "human", "human_alice")
            human_klass: Class/type identifier for this human (typically "human")
            agent: Optional HumanAgent instance for buffer delivery and testing
        """
        self._id = human_id
        self._klass = human_klass
        self.agent = agent

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

        Primary display is handled by StreamObservers. This method provides
        optional buffer delivery for testing or programmatic access.

        Args:
            message: The message to deliver
        """
        if self.agent:
            await self.agent._add_message_to_buffer(message)

    def __repr__(self) -> str:
        return f"HumanParticipant({self.klass}:{self.id})"
