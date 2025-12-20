"""Base agent implementation for the playbooks framework.

This module provides the foundational BaseAgent class that all agent types
inherit from, along with the BaseAgentMeta metaclass for agent configuration.
"""

from abc import ABC, ABCMeta
from typing import TYPE_CHECKING, Any, Dict, Optional

from playbooks.core.events import (
    AgentPausedEvent,
    AgentResumedEvent,
    MethodCallEndedEvent,
    MethodCallStartedEvent,
)
from playbooks.core.identifiers import AgentID, MeetingID
from playbooks.core.message import MessageType
from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.llm.messages import AgentCommunicationLLMMessage

from .messaging_mixin import MessagingMixin

if TYPE_CHECKING:
    from playbooks.core.stream_result import StreamResult
    from playbooks.program import Program


class BaseAgentMeta(ABCMeta):
    """Meta class for BaseAgent."""

    def should_create_instance_at_start(self) -> bool:
        """Whether to create an instance of the agent at start.

        Override in subclasses to control whether to create an instance at start.
        """
        return False

    def __getattr__(cls, name: str) -> Any:
        """Expose playbooks as callable class attributes.

        This allows accessing playbooks via AgentClass.playbook_name syntax,
        which is used in expressions like {FilesystemAgent.read_file(...)}.

        Args:
            name: The attribute name to look up

        Returns:
            A callable for the playbook

        Raises:
            AttributeError: If the attribute is not found
        """
        # Check if playbooks dictionary exists and contains the requested name
        # Use type.__getattribute__ to avoid recursion
        try:
            playbooks = type.__getattribute__(cls, "playbooks")
            if name in playbooks:
                playbook = playbooks[name]
                # For RemotePlaybook, return the execute_fn which is already callable and bound
                if hasattr(playbook, "execute_fn") and playbook.execute_fn:
                    return playbook.execute_fn
                # For other playbooks, we'd need to create a wrapper, but this shouldn't
                # happen in practice since only remote playbooks are accessed this way
                return playbook
        except AttributeError:
            pass

        # Attribute not found - raise AttributeError
        raise AttributeError(f"type object '{cls.__name__}' has no attribute '{name}'")


class BaseAgent(MessagingMixin, ABC, metaclass=BaseAgentMeta):
    """
    Base class for all agent implementations.

    Agents define behavior - what they do, their methods, and internal state.
    The runtime (Program) decides when and where they run.
    """

    def __init__(
        self,
        agent_id: str,
        program: "Program",
        source_line_number: Optional[int] = None,
        source_file_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a new BaseAgent.

        Args:
            agent_id: Unique identifier for this agent instance
            program: Program instance managing this agent
            source_line_number: Line number in source where agent is defined
            source_file_path: Path to source file where agent is defined
            **kwargs: Additional initialization arguments
        """
        super().__init__()
        self.klass = self.__class__.klass
        self.description = self.__class__.description
        self.metadata = self.__class__.metadata.copy()

        self.id = agent_id
        self.kwargs = kwargs
        self.program = program

        # Source tracking
        self.source_line_number = source_line_number
        self.source_file_path = source_file_path

        # Debug context
        self._debug_thread_id: Optional[int] = None
        self.paused: Optional[str] = None

    async def begin(self) -> None:
        """Agent startup logic. Override in subclasses.

        Called when the agent's execution thread starts. Implement
        message processing loops and playbook execution here.
        """
        pass

    async def initialize(self) -> None:
        """Agent initialization logic. Override in subclasses.

        Called before begin() to set up agent state, load resources,
        and prepare for execution.
        """
        pass

    # Built-in playbook methods
    async def say(self, target: str, message: str) -> str:
        """Send a message to a target (agent, human, or meeting).

        This is the main entry point for message sending. It resolves the target,
        handles different routing paths, and manages streaming for human recipients.

        Args:
            target: Target specification (agent ID, "human", "meeting", etc.)
            message: Message content to send

        Returns:
            The message content (for compatibility with existing code)
        """
        # Publish method call start event for telemetry
        self.event_bus.publish(
            MethodCallStartedEvent(
                session_id=self.program.event_bus.session_id if self.program else "",
                agent_id=self.id,
                method_name="Say",
                args=[
                    target,
                    message[:100] + "..." if len(message) > 100 else message,
                ],  # Truncate long messages
                kwargs={},
            )
        )

        try:
            resolved_target = self.resolve_target(target, allow_fallback=True)

            # Route to appropriate handler based on target type
            if resolved_target.startswith("meeting "):
                result = await self._say_to_meeting(resolved_target, message)
            else:
                result = await self._say_direct(resolved_target, message)

            # Publish method call end event
            self.event_bus.publish(
                MethodCallEndedEvent(
                    session_id=(
                        self.program.event_bus.session_id if self.program else ""
                    ),
                    agent_id=self.id,
                    method_name="Say",
                    result=result,
                )
            )

            return result

        except Exception as e:
            # Publish method call end event with error
            self.event_bus.publish(
                MethodCallEndedEvent(
                    session_id=(
                        self.program.event_bus.session_id if self.program else ""
                    ),
                    agent_id=self.id,
                    method_name="Say",
                    error=str(e),
                )
            )
            raise

    async def _say_to_meeting(self, meeting_spec: str, message: str) -> str:
        """Send message to a meeting.

        Args:
            meeting_spec: Meeting specification (e.g., "meeting 123" or "meeting 123, agent 456")
            message: Message content to broadcast

        Returns:
            The message content
        """
        # Extract just the meeting ID for participation check (before any comma)
        meeting_id_part = meeting_spec.split(",")[0].strip()
        meeting_id = MeetingID.parse(meeting_id_part).id

        # Check if not a participant - log error and return early
        is_participant = False
        if hasattr(self, "owned_meetings") and meeting_id in self.owned_meetings:
            is_participant = True
        elif hasattr(self, "joined_meetings") and meeting_id in self.joined_meetings:
            is_participant = True

        if not is_participant:
            debug(
                f"{str(self)}: Cannot broadcast to meeting {meeting_id} - not a participant"
            )
            if hasattr(self, "session_log"):
                self.session_log.append(
                    f"Cannot broadcast to meeting {meeting_id} - not a participant"
                )
            return message

        # Use streaming infrastructure like _say_direct does
        already_streamed = getattr(self, "_currently_streaming", False)

        debug(f"{str(self)}: _say_to_meeting: already_streamed={already_streamed}")

        if not already_streamed and self.program:
            debug(f"{str(self)}: _say_to_meeting: Calling _say_meeting_with_streaming")
            await self._say_meeting_with_streaming(meeting_spec, message)
        else:
            debug(
                f"{str(self)}: _say_to_meeting: Calling _say_meeting_without_streaming"
            )
            await self._say_meeting_without_streaming(meeting_spec, message)

        return message

    async def _say_meeting_with_streaming(
        self, meeting_spec: str, message: str
    ) -> None:
        """Send meeting message with streaming support.

        Args:
            meeting_spec: Meeting specification
            message: Message content to broadcast
        """
        stream_result = await self.start_streaming_say_via_channel(meeting_spec)

        if stream_result.should_stream:
            # Use streaming path - this will deliver the message
            await self.stream_say_update_via_channel(
                stream_result.stream_id, meeting_spec, message
            )
            await self.complete_streaming_say_via_channel(
                stream_result.stream_id, meeting_spec, message
            )
        else:
            # Streaming was skipped (no human and agent streaming disabled) - still route via channel.
            # Extract meeting ID for message metadata, but always go through Program routing.
            meeting_id_part = meeting_spec.split(",")[0].strip()
            meeting_id = MeetingID.parse(meeting_id_part).id
            await self.program.route_message(
                sender_id=self.id,
                sender_klass=self.klass,
                receiver_spec=meeting_spec,
                message=message,
                message_type=MessageType.MEETING_BROADCAST,
                meeting_id=meeting_id,
            )

    async def _say_meeting_without_streaming(
        self, meeting_spec: str, message: str
    ) -> None:
        """Send meeting message without streaming.

        Args:
            meeting_spec: Meeting specification
            message: Message content to broadcast
        """
        # If currently in streaming context, message was already delivered via channel.complete_stream
        # Skip to avoid duplicate delivery
        if getattr(self, "_currently_streaming", False):
            debug(
                f"{str(self)}: _say_meeting_without_streaming: SKIPPING (already streamed)"
            )
            return

        # Extract meeting ID for metadata
        meeting_id_part = meeting_spec.split(",")[0].strip()
        meeting_id = MeetingID.parse(meeting_id_part).id
        await self.program.route_message(
            sender_id=self.id,
            sender_klass=self.klass,
            receiver_spec=meeting_spec,
            message=message,
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id=meeting_id,
        )

    async def _say_direct(self, resolved_target: str, message: str) -> str:
        """Send direct message to agent or human.

        Handles streaming for human recipients and direct delivery for agents.

        Args:
            resolved_target: Resolved target identifier (agent ID or "human")
            message: Message content to send

        Returns:
            The message content
        """
        # Track conversation context (skip for human and meetings)
        if resolved_target not in ["human", "user"]:
            if hasattr(self, "last_message_target"):
                self.last_message_target = resolved_target

        # Check if we're re-executing already-streamed code
        already_streamed = getattr(self, "_currently_streaming", False)

        if not already_streamed and self.program:
            await self._say_with_streaming(resolved_target, message)
        else:
            await self._say_without_streaming(resolved_target, message)

        return message

    async def _say_with_streaming(self, resolved_target: str, message: str) -> None:
        """Send message with streaming support (for human recipients).

        Args:
            resolved_target: Resolved target identifier
            message: Message content to send
        """
        stream_result = await self.start_streaming_say_via_channel(resolved_target)

        if stream_result.should_stream:
            # Human recipient - use streaming
            await self.stream_say_update_via_channel(
                stream_result.stream_id, resolved_target, message
            )
            await self.complete_streaming_say_via_channel(
                stream_result.stream_id, resolved_target, message
            )
        else:
            # Agent recipient - send directly without streaming
            target_agent_id = self._extract_agent_id(resolved_target)
            await self.SendMessage(target_agent_id, message)

    async def _say_without_streaming(self, resolved_target: str, message: str) -> None:
        """Send message without streaming (already streamed or no program).

        When _currently_streaming is True, the message was already delivered
        via the streaming path (channel.complete_stream), so we skip sending
        it again to avoid duplicate delivery.

        Args:
            resolved_target: Resolved target identifier
            message: Message content to send
        """
        # If currently in streaming context, message was already delivered - skip to avoid duplication
        if getattr(self, "_currently_streaming", False):
            return

        # Not in streaming context - send message normally
        if resolved_target in ["human", "user"]:
            await self.SendMessage(resolved_target, message)
        else:
            target_agent_id = self._extract_agent_id(resolved_target)
            await self.SendMessage(target_agent_id, message)

    def _extract_agent_id(self, target: str) -> str:
        """Extract agent ID from target specification.

        Args:
            target: Target specification (could be "agent 1001" or "1001")

        Returns:
            Plain agent ID string
        """
        if target.startswith("agent "):
            return AgentID.parse(target).id
        return target

    async def SendMessage(self, target_agent_id: str, message: str) -> None:
        """Send a message to another agent.

        Routes message through program runtime and adds communication
        context to the call stack for LLM awareness. Always logs the communication
        (to call stack frame if inside playbook, to top_level_llm_messages if not).

        Args:
            target_agent_id: ID of the target agent (or "human"/"user")
            message: Message content to send
        """
        if not self.program:
            return

        # Create the agent communication message
        target_agent = self.program.agents_by_id.get(target_agent_id)
        target_name = (
            str(target_agent) if target_agent else f"UnknownAgent({target_agent_id})"
        )
        agent_comm_msg = AgentCommunicationLLMMessage(
            f"I {str(self)} sent message to {target_name}: {message}",
            sender_agent=self.klass,
            target_agent=target_name,
        )

        # Add to call stack (always add to the current top frame; if stack is empty, goes to top-level)
        if hasattr(self, "call_stack"):
            self.call_stack.add_llm_message(agent_comm_msg)

        # Route through program runtime
        # target_agent_id is a raw ID, convert to spec format for routing
        receiver_spec = (
            f"agent {target_agent_id}"
            if not target_agent_id.startswith("agent ")
            else target_agent_id
        )
        await self.program.route_message(
            sender_id=self.id,
            sender_klass=self.klass,
            receiver_spec=receiver_spec,
            message=message,
        )

    async def start_streaming_say(self, recipient: Optional[str] = None) -> None:
        """Start displaying a streaming Say() message. Override in subclasses (legacy).

        Args:
            recipient: Optional recipient identifier (legacy parameter)
        """
        pass

    async def stream_say_update(self, content: str) -> None:
        """Add content to the current streaming Say() message. Override in subclasses (legacy).

        Args:
            content: Content chunk to add to the stream
        """
        pass

    async def complete_streaming_say(self) -> None:
        """Complete the current streaming Say() message. Override in subclasses (legacy)."""
        pass

    async def start_streaming_say_via_channel(self, target: str) -> "StreamResult":
        """Start streaming via channel infrastructure.

        Args:
            target: Target specification for the stream

        Returns:
            StreamResult indicating if streaming was started and the stream ID
        """
        import uuid

        from playbooks.core.stream_result import StreamResult

        stream_id = str(uuid.uuid4())
        if self.program:
            result = await self.program.start_stream(
                sender_id=self.id,
                sender_klass=self.klass,
                receiver_spec=target,
                stream_id=stream_id,
            )
            return result
        # No program, skip streaming
        return StreamResult.skip()

    async def stream_say_update_via_channel(
        self, stream_id: str, target: str, content: str
    ) -> None:
        """Stream content chunk via channel infrastructure.

        Args:
            stream_id: ID of the active stream
            target: Target specification
            content: Content chunk to stream
        """
        if self.program:
            await self.program.stream_chunk(
                stream_id=stream_id,
                sender_id=self.id,
                receiver_spec=target,
                content=content,
            )

    async def complete_streaming_say_via_channel(
        self, stream_id: str, target: str, final_content: str
    ) -> None:
        """Complete streaming via channel infrastructure.

        Args:
            stream_id: ID of the active stream
            target: Target specification
            final_content: Final complete message content
        """
        if self.program:
            await self.program.complete_stream(
                stream_id=stream_id,
                sender_id=self.id,
                receiver_spec=target,
                final_content=final_content,
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary representation.

        Returns:
            Dictionary with agent type, ID, and any additional kwargs
        """
        return {**self.kwargs, "type": self.klass, "agent_id": self.id}

    def __getattr__(self, name: str) -> Any:
        """Expose playbooks as callable attributes.

        If a playbook with the given name exists, returns a callable that
        executes the playbook via its execute() method.

        Args:
            name: The attribute name to look up

        Returns:
            A callable that executes the playbook via execute()

        Raises:
            AttributeError: If the attribute is not a playbook and doesn't exist
        """
        # Check if playbooks dictionary exists and contains the requested name
        if hasattr(self, "playbooks") and name in self.playbooks:
            # Return a wrapper that calls the playbook's execute() method
            async def playbook_wrapper(*args, **kwargs):
                success, result = await self.execute_playbook(name, args, kwargs)
                if success:
                    return result
                else:
                    return {"error": result}

            return playbook_wrapper

        # Attribute not found - raise AttributeError
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def get_debug_thread_id(self) -> Optional[int]:
        """Get the debug thread ID for this agent.

        Returns:
            Debug thread ID if set, None otherwise
        """
        return self._debug_thread_id

    def set_debug_thread_id(self, thread_id: Optional[int]) -> None:
        """Set the debug thread ID for this agent.

        Args:
            thread_id: Debug thread ID to set (None to clear)
        """
        self._debug_thread_id = thread_id

    def emit_agent_paused_event(
        self, reason: str = "pause", source_line_number: int = 0
    ) -> None:
        """Emit an agent paused event for debugging.

        Args:
            reason: Reason for pausing (e.g., "pause", "breakpoint")
            source_line_number: Line number where pause occurred
        """
        if (
            self.program
            and hasattr(self.program, "event_bus")
            and self.program.event_bus
        ):
            event = AgentPausedEvent(
                session_id="",
                agent_id=self.id,
                reason=reason,
                source_line_number=source_line_number,
            )
            self.program.event_bus.publish(event)

    def emit_agent_resumed_event(self) -> None:
        """Emit an agent resumed event for debugging.

        Called when execution resumes after a pause.
        """
        if (
            self.program
            and hasattr(self.program, "event_bus")
            and self.program.event_bus
        ):
            event = AgentResumedEvent(
                session_id="",
                agent_id=self.id,
            )
            self.program.event_bus.publish(event)
