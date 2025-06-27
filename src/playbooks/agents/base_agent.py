import asyncio
import uuid
from abc import ABC
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict

from playbooks.constants import EOM
from playbooks.enums import LLMMessageRole

if TYPE_CHECKING:
    from src.playbooks.program import Program


class AgentCommunicationMixin:
    def __init__(self):
        self.program: Program | None = None
        self.inboxes = defaultdict(asyncio.Queue)

    async def SendMessage(self, target_agent_id: str, message: str):
        target_agent = self.program.agents_by_id.get(target_agent_id)
        current_frame = self.state.call_stack.peek()
        if current_frame:
            if target_agent:
                target_agent_name = str(target_agent)
            else:
                target_agent_name = BaseAgent.unknown_agent_str(target_agent_id)
            current_frame.add_uncached_llm_message(
                f"I {str(self)} sent message to {target_agent_name}: {message}",
                role=LLMMessageRole.ASSISTANT,
            )

        await self.program.route_message(self.id, target_agent_id, message)

    async def WaitForMessage(self, source_agent_id: str) -> str | None:
        messages = []

        while not self.inboxes[source_agent_id].empty():
            message = self.inboxes[source_agent_id].get_nowait()
            if message == EOM:
                break
            messages.append(message)

        if not messages:
            messages.append(await self.inboxes[source_agent_id].get())

        # Process each message for special types
        processed_messages = []
        for message in messages:
            self.state.session_log.append(
                f"Received message from {source_agent_id}: {message}"
            )
            current_frame = self.state.call_stack.peek()
            if current_frame:
                source_agent = self.program.agents_by_id.get(source_agent_id)
                if source_agent:
                    source_agent_name = str(source_agent)
                else:
                    source_agent_name = BaseAgent.unknown_agent_str(source_agent_id)
                current_frame.add_uncached_llm_message(
                    f"{source_agent_name} said to me {str(self)}: {message}",
                    role=LLMMessageRole.ASSISTANT,
                )
            # Check for meeting response messages
            if await self._handle_special_message(source_agent_id, message):
                # Special message was handled, don't pass to LLM
                continue

            processed_messages.append(message)

        return "\n".join(processed_messages)

    async def _handle_special_message(self, source_agent_id: str, message: str) -> bool:
        """Handle special message types automatically.

        Args:
            source_agent_id: ID of the agent that sent the message
            message: The message content

        Returns:
            True if the message was handled as a special type, False otherwise
        """
        # Handle JOINED responses
        if message.startswith("JOINED meeting "):
            try:
                # Parse "JOINED meeting <meeting_id>:" format
                parts = message.split(":")
                if len(parts) >= 1:
                    meeting_part = parts[0]  # "JOINED meeting <meeting_id>"
                    meeting_id = meeting_part.split(" ")[-1]  # Extract <meeting_id>
                    if hasattr(self.state, "handle_join_request"):
                        self.state.handle_join_request(
                            source_agent_id, source_agent_id, meeting_id
                        )
                        self.state.session_log.append(
                            f"Agent {source_agent_id} joined meeting {meeting_id}"
                        )
                    return True
            except (ValueError, IndexError):
                pass

        # Handle REJECTED responses
        elif message.startswith("REJECTED meeting "):
            try:
                # Parse "REJECTED meeting <meeting_id>:" format
                parts = message.split(":")
                if len(parts) >= 1:
                    meeting_part = parts[0]  # "REJECTED meeting <meeting_id>"
                    meeting_id = meeting_part.split(" ")[-1]  # Extract <meeting_id>
                    # Remove from pending invitations
                    if (
                        hasattr(self.state, "invitations")
                        and source_agent_id in self.state.invitations
                    ):
                        self.state.invitations[source_agent_id].discard(meeting_id)
                        if not self.state.invitations[source_agent_id]:
                            del self.state.invitations[source_agent_id]
                    self.state.session_log.append(
                        f"Agent {source_agent_id} rejected meeting {meeting_id}"
                    )
                    return True
            except (ValueError, IndexError):
                pass

        # Handle ENDED meeting messages
        elif message.startswith("ENDED meeting "):
            try:
                # Parse "ENDED meeting <meeting_id>:" format
                parts = message.split(":")
                if len(parts) >= 1:
                    meeting_part = parts[0]  # "ENDED meeting <meeting_id>"
                    meeting_id = meeting_part.split(" ")[-1]  # Extract <meeting_id>
                    self.state.session_log.append(f"Meeting {meeting_id} has ended")
                    return True
            except (ValueError, IndexError):
                pass

        # Not a special message
        return False


class BaseAgent(AgentCommunicationMixin, ABC):
    """
    Abstract base class for all agent implementations.

    Agents are entities that can process messages and generate responses. This class
    defines the common interface that all agent implementations must adhere to.

    Attributes:
        klass: A string identifier for the agent class/type.
    """

    def __init__(self, klass: str, agent_id: str = None):
        """
        Initialize a new BaseAgent.

        Args:
            klass: The class/type identifier for this agent.
            agent_id: Optional agent ID. If not provided, will generate UUID (for backward compatibility).
        """
        super().__init__()
        self.id = agent_id if agent_id is not None else str(uuid.uuid4())
        self.klass = klass

    async def begin(self):
        pass

    async def initialize(self):
        pass

    async def start_streaming_say(self, recipient=None):
        """Start displaying a streaming Say() message. Override in subclasses."""
        pass

    async def stream_say_update(self, content: str):
        """Add content to the current streaming Say() message. Override in subclasses."""
        pass

    async def complete_streaming_say(self):
        """Complete the current streaming Say() message. Override in subclasses."""
        pass

    @staticmethod
    def unknown_agent_str(agent_id: str):
        return f"Agent (agent {agent_id})"

    def to_dict(self) -> Dict[str, Any]:
        return {**self.kwargs, "type": self.klass, "agent_id": self.id}
