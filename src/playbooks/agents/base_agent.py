import asyncio
from abc import ABC
from typing import TYPE_CHECKING, Any, Dict, List

from playbooks.constants import EOM
from playbooks.enums import LLMMessageRole
from playbooks.meetings import MeetingMessageHandler

if TYPE_CHECKING:
    from src.playbooks.program import Program


class BaseAgent(ABC):
    """
    Base class for all agent implementations.

    Agents define behavior - what they do, their methods, and internal state.
    The runtime (Program) decides when and where they run.
    """

    def __init__(self, klass: str, agent_id: str, program: "Program", **kwargs):
        """Initialize a new BaseAgent."""
        self.id = agent_id
        self.klass = klass
        self.kwargs = kwargs
        self.program = program

        # Message handling - simple buffer managed by runtime
        self._message_buffer = []

        # Initialize meeting message handler
        self.meeting_message_handler = MeetingMessageHandler(self.id, self.klass)

    async def process_message(self, message):
        """Process a received message. Override in subclasses."""
        # Simple default: add to buffer for WaitForMessage to pick up
        self._message_buffer.append(message)

    async def begin(self):
        """Agent startup logic. Override in subclasses."""
        pass

    async def initialize(self):
        """Agent initialization logic. Override in subclasses."""
        pass

    # Built-in playbook methods
    async def SendMessage(self, target_agent_id: str, message: str):
        """Send a message to another agent."""
        if not self.program:
            return

        # Add to current frame context if available
        if hasattr(self, "state") and self.state.call_stack.peek():
            current_frame = self.state.call_stack.peek()
            target_agent = self.program.agents_by_id.get(target_agent_id)
            target_name = (
                str(target_agent)
                if target_agent
                else self.unknown_agent_str(target_agent_id)
            )
            current_frame.add_uncached_llm_message(
                f"I {str(self)} sent message to {target_name}: {message}",
                role=LLMMessageRole.ASSISTANT,
            )

        # Route through program runtime
        self.program.route_message(self.id, target_agent_id, message)

    async def WaitForMessage(self, source_agent_id: str) -> str | None:
        """Wait for messages from a specific agent."""
        collected_messages = []

        while True:
            # Wait for messages in buffer
            import time

            timeout = 30.0
            start_time = time.time()

            while time.time() - start_time < timeout:
                # Check message buffer
                for i, msg in enumerate(self._message_buffer):
                    if msg.sender_id == source_agent_id:
                        # Check for EOM
                        if msg.content == EOM:
                            # Remove EOM and return collected messages
                            self._message_buffer.pop(i)
                            return self._process_collected_messages(
                                source_agent_id, collected_messages
                            )

                        # Collect regular message
                        collected_messages.append(self._message_buffer.pop(i))
                        break

                await asyncio.sleep(0.1)

            return None  # Timeout

    def _process_collected_messages(
        self, source_agent_id: str, collected_messages: List
    ) -> str:
        """Process collected messages and return formatted result."""
        processed_messages = []

        for msg in collected_messages:
            if hasattr(self, "state"):
                self.state.session_log.append(
                    f"Received message from {source_agent_id}: {msg.content}"
                )

                if self.state.call_stack.peek():
                    current_frame = self.state.call_stack.peek()
                    source_agent = self.program.agents_by_id.get(source_agent_id)
                    source_name = (
                        str(source_agent)
                        if source_agent
                        else self.unknown_agent_str(source_agent_id)
                    )
                    current_frame.add_uncached_llm_message(
                        f"{source_name} said to me {str(self)}: {msg.content}",
                        role=LLMMessageRole.ASSISTANT,
                    )

            processed_messages.append(msg.content)

        return "\n".join(processed_messages)

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
