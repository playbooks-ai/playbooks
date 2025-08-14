from abc import ABC, ABCMeta
from typing import TYPE_CHECKING, Any, Dict

from playbooks.enums import LLMMessageRole
from playbooks.utils.spec_utils import SpecUtils

from .messaging_mixin import MessagingMixin

if TYPE_CHECKING:
    from src.playbooks.program import Program


class BaseAgentMeta(ABCMeta):
    """Meta class for BaseAgent."""

    def should_create_instance_at_start(self) -> bool:
        """Whether to create an instance of the agent at start.

        Override in subclasses to control whether to create an instance at start.
        """
        return False


class BaseAgent(MessagingMixin, ABC, metaclass=BaseAgentMeta):
    """
    Base class for all agent implementations.

    Agents define behavior - what they do, their methods, and internal state.
    The runtime (Program) decides when and where they run.
    """

    def __init__(self, agent_id: str, program: "Program", **kwargs):
        """Initialize a new BaseAgent."""
        super().__init__()
        self.klass = self.__class__.klass
        self.description = self.__class__.description
        self.metadata = self.__class__.metadata.copy()

        self.id = agent_id
        self.kwargs = kwargs
        self.program = program

        # Debug context
        self._debug_thread_id: int = None
        self._debug_status: str = "not_started"

    async def begin(self):
        """Agent startup logic. Override in subclasses."""
        pass

    async def initialize(self):
        """Agent initialization logic. Override in subclasses."""
        pass

    # Built-in playbook methods
    async def Say(self, target: str, message: str):
        resolved_target = self.resolve_target(target, allow_fallback=True)

        # Handle meeting targets with broadcasting
        if SpecUtils.is_meeting_spec(resolved_target):
            meeting_id = SpecUtils.extract_meeting_id(resolved_target)
            if (
                hasattr(self, "state")
                and hasattr(self.state, "owned_meetings")
                and meeting_id in self.state.owned_meetings
            ):
                await self.meeting_manager.broadcast_to_meeting_as_owner(
                    meeting_id, message
                )
            elif (
                hasattr(self, "state")
                and hasattr(self.state, "joined_meetings")
                and meeting_id in self.state.joined_meetings
            ):
                await self.meeting_manager.broadcast_to_meeting_as_participant(
                    meeting_id, message
                )
            else:
                # Error: not in this meeting
                self.state.session_log.append(
                    f"Cannot broadcast to meeting {meeting_id} - not a participant"
                )
            return

        # Track last message target (only for 1:1 messages, not meetings)
        if not (
            SpecUtils.is_meeting_spec(resolved_target) or resolved_target == "human"
        ):
            self.state.last_message_target = resolved_target

        await self.SendMessage(resolved_target, message)

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
        await self.program.route_message(
            sender_id=self.id,
            sender_klass=self.klass,
            receiver_spec=target_agent_id,
            message=message,
        )

    async def start_streaming_say(self, recipient=None):
        """Start displaying a streaming Say() message. Override in subclasses."""
        pass

    async def stream_say_update(self, content: str):
        """Add content to the current streaming Say() message. Override in subclasses."""
        pass

    async def complete_streaming_say(self):
        """Complete the current streaming Say() message. Override in subclasses."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {**self.kwargs, "type": self.klass, "agent_id": self.id}

    def add_uncached_llm_message(
        self, message: str, role: str = LLMMessageRole.ASSISTANT
    ) -> None:
        if (
            hasattr(self, "state")
            and hasattr(self.state, "call_stack")
            and self.state.call_stack.peek() is not None
        ):
            self.state.call_stack.peek().add_uncached_llm_message(message, role)

    def add_cached_llm_message(
        self, message: str, role: str = LLMMessageRole.ASSISTANT
    ) -> None:
        if (
            hasattr(self, "state")
            and hasattr(self.state, "call_stack")
            and self.state.call_stack.peek() is not None
        ):
            self.state.call_stack.peek().add_cached_llm_message(message, role)

    def get_debug_thread_id(self) -> int:
        """Get the debug thread ID for this agent."""
        return self._debug_thread_id

    def set_debug_thread_id(self, thread_id: int) -> None:
        """Set the debug thread ID for this agent."""
        self._debug_thread_id = thread_id

    def get_debug_status(self) -> str:
        """Get the current debug status."""
        return self._debug_status

    def set_debug_status(self, status: str) -> None:
        """Set the debug status."""
        self._debug_status = status

        # Update debug server if available
        if (
            self.program
            and hasattr(self.program, "_debug_server")
            and self.program._debug_server
        ):
            self.program._debug_server.update_agent_status(self.id, status)

    def emit_agent_paused_event(
        self, reason: str = "pause", source_line_number: int = 0
    ) -> None:
        """Emit an agent paused event for debugging."""
        if (
            self.program
            and hasattr(self.program, "event_bus")
            and self.program.event_bus
        ):
            from playbooks.events import AgentPausedEvent

            agent_name = str(self)
            event = AgentPausedEvent(
                agent_id=self.id,
                agent_name=agent_name,
                thread_id=self._debug_thread_id or 1,
                reason=reason,
                source_line_number=source_line_number,
            )
            self.program.event_bus.publish(event)

    def emit_agent_resumed_event(self) -> None:
        """Emit an agent resumed event for debugging."""
        if (
            self.program
            and hasattr(self.program, "event_bus")
            and self.program.event_bus
        ):
            from playbooks.events import AgentResumedEvent

            agent_name = str(self)
            event = AgentResumedEvent(
                agent_id=self.id,
                agent_name=agent_name,
                thread_id=self._debug_thread_id or 1,
            )
            self.program.event_bus.publish(event)
