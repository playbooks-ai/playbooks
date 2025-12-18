"""Call stack management for playbook execution.

This module provides the call stack infrastructure that tracks execution
state, instruction pointers, and function call nesting during playbook
execution and debugging.
"""

from typing import Any, Dict, List, Optional

from playbooks.core.events import (
    CallStackPopEvent,
    CallStackPushEvent,
    InstructionPointerEvent,
)
from playbooks.execution.step import PlaybookStep
from playbooks.infrastructure.event_bus import EventBus
from playbooks.llm.messages import LLMMessage


class InstructionPointer:
    """Represents a position in a playbook.

    Attributes:
        playbook: The name of the playbook.
        line_number: The line number within the playbook.
        source_line_number: The source line number in the markdown.
        source_file_path: The file path of the source markdown.
    """

    def __init__(
        self,
        playbook: str,
        line_number: str,
        source_line_number: int,
        step: Optional[PlaybookStep] = None,
        source_file_path: Optional[str] = None,
    ) -> None:
        """Initialize an instruction pointer.

        Args:
            playbook: Name of the playbook
            line_number: Line number within the playbook (e.g., "01", "01.02")
            source_line_number: Original line number in source markdown
            step: Associated PlaybookStep object (optional)
            source_file_path: Path to source file (optional)
        """
        self.playbook = playbook
        self.line_number = line_number
        self.source_line_number = source_line_number
        self.source_file_path = source_file_path
        self.step = step

    def copy(self) -> "InstructionPointer":
        """Create a copy of this instruction pointer.

        Returns:
            New InstructionPointer with same values
        """
        return InstructionPointer(
            self.playbook,
            self.line_number,
            self.source_line_number,
            self.step,
            self.source_file_path,
        )

    def increment_instruction_pointer(self) -> None:
        """Increment the instruction pointer to the next line.

        Note: This is a temporary implementation that assumes simple numeric
        line numbers. May need revision for complex nested line numbers.
        """
        self.line_number = str(int(self.line_number) + 1)
        self.source_line_number = self.source_line_number + 1

    def to_compact_str(self) -> str:
        """Get compact string representation (playbook:line_number).

        Returns:
            String like "PlaybookName:01" or just "PlaybookName" if no line number
        """
        compact_str = (
            self.playbook
            if self.line_number is None
            else f"{self.playbook}:{self.line_number}"
        )
        return compact_str

    def __str__(self) -> str:
        """Get full string representation with source location."""
        compact_str = self.to_compact_str()
        if self.source_line_number is not None:
            return f"{compact_str} ({self.source_file_path}:{self.source_line_number})"
        return compact_str

    def __repr__(self) -> str:
        """Return string representation."""
        return str(self)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with playbook, line_number, and source_line_number
        """
        return {
            "playbook": self.playbook,
            "line_number": self.line_number,
            "source_line_number": self.source_line_number,
        }


class CallStackFrame:
    """Represents a frame in the call stack.

    Attributes:
        instruction_pointer: Points to the current instruction.
        llm_chat_session_id: ID of the associated LLM chat session, if any.
    """

    def __init__(
        self,
        instruction_pointer: InstructionPointer,
        llm_messages: Optional[List[LLMMessage]] = None,
        is_meeting: bool = False,
        meeting_id: Optional[str] = None,
    ) -> None:
        """Initialize a call stack frame.

        Args:
            instruction_pointer: Current execution position
            llm_messages: LLM messages associated with this frame
            is_meeting: Whether this frame is part of a meeting
            meeting_id: Meeting ID if is_meeting is True
        """
        self.instruction_pointer = instruction_pointer
        self.llm_messages = llm_messages or []
        self.is_meeting = is_meeting
        self.meeting_id = meeting_id
        self.depth = -1
        self.executor = None  # Executor context for this frame (handles nested calls)
        self.locals: Dict[str, Any] = {}  # Frame-specific local variables

    @property
    def source_line_number(self) -> int:
        """Get source line number from instruction pointer."""
        return self.instruction_pointer.source_line_number

    @property
    def line_number(self) -> str:
        """Get line number from instruction pointer."""
        return self.instruction_pointer.line_number

    @property
    def playbook(self) -> str:
        """Get playbook name from instruction pointer."""
        return self.instruction_pointer.playbook

    @property
    def step(self) -> Optional[PlaybookStep]:
        """Get PlaybookStep from instruction pointer."""
        return self.instruction_pointer.step

    def to_dict(self) -> Dict[str, Any]:
        """Convert the frame to a dictionary representation.

        Returns:
            A dictionary representation of the frame.
        """
        result = {
            "instruction_pointer": str(self.instruction_pointer),
        }
        if self.is_meeting:
            result["is_meeting"] = self.is_meeting
            result["meeting_id"] = self.meeting_id
        return result

    def add_llm_message(self, message: LLMMessage) -> None:
        """Add an LLMMessage object to the call stack frame.

        Args:
            message: LLM message to add to this frame
        """
        self.llm_messages.append(message)

    def __repr__(self) -> str:
        """Return string representation of the frame."""
        base_repr = self.instruction_pointer.to_compact_str()
        if self.is_meeting and self.meeting_id:
            return f"{base_repr}[meeting {self.meeting_id}]"
        return base_repr

    def get_llm_messages(self) -> List[Dict[str, str]]:
        """Get the messages for the call stack frame as dictionaries for LLM API.

        Returns:
            List of message dictionaries (caching applied later by InterpreterPrompt)
        """
        return [msg.to_full_message() for msg in self.llm_messages]


class CallStack:
    """A stack of call frames."""

    def __init__(self, event_bus: EventBus, agent_id: str = "unknown") -> None:
        """Initialize a call stack.

        Args:
            event_bus: Event bus for publishing call stack events
            agent_id: ID of the agent owning this call stack
        """
        self.frames: List[CallStackFrame] = []
        self.event_bus = event_bus
        self.agent_id = agent_id
        # Messages that occur outside of playbook execution (top-level)
        # These are included in LLM context when call stack is empty
        self.top_level_llm_messages: List[LLMMessage] = []

    def is_empty(self) -> bool:
        """Check if the call stack is empty.

        Returns:
            True if the call stack has no frames, False otherwise.
        """
        return not self.frames

    def push(self, frame: CallStackFrame) -> None:
        """Push a frame onto the call stack.

        Args:
            frame: The frame to push.
        """
        self.frames.append(frame)
        frame.depth = len(self.frames)
        event = CallStackPushEvent(
            session_id=self.agent_id, frame=str(frame), stack=self.to_dict()
        )
        self.event_bus.publish(event)

    def pop(self) -> Optional[CallStackFrame]:
        """Remove and return the top frame from the call stack.

        Returns:
            The top frame, or None if the stack is empty.
        """
        frame = self.frames.pop() if self.frames else None
        if frame:
            event = CallStackPopEvent(
                session_id=self.agent_id, frame=str(frame), stack=self.to_dict()
            )
            self.event_bus.publish(event)
        return frame

    def peek(self) -> Optional[CallStackFrame]:
        """Return the top frame without removing it.

        Returns:
            The top frame, or None if the stack is empty.
        """
        return self.frames[-1] if self.frames else None

    def advance_instruction_pointer(
        self, instruction_pointer: InstructionPointer
    ) -> None:
        """Advance the instruction pointer to the next instruction.

        Args:
            instruction_pointer: The new instruction pointer.
        """
        self.frames[-1].instruction_pointer = instruction_pointer
        event = InstructionPointerEvent(
            session_id=self.agent_id,
            pointer=str(instruction_pointer),
            stack=self.to_dict(),
        )
        self.event_bus.publish(event)

    def __repr__(self) -> str:
        frames = ", ".join(str(frame.instruction_pointer) for frame in self.frames)
        return f"CallStack[{frames}]"

    def __str__(self) -> str:
        return self.__repr__()

    def to_dict(self) -> List[str]:
        """Convert the call stack to a dictionary representation.

        Returns:
            A list of string representations of instruction pointers.
        """
        return [frame.instruction_pointer.to_dict() for frame in self.frames]

    def get_llm_messages(self) -> List[Dict[str, str]]:
        """Get the messages for the call stack for the LLM."""
        messages = []

        # Add top-level messages first (system messages, etc.)
        for msg in self.top_level_llm_messages:
            messages.append(msg.to_full_message())

        # Then add frame messages (execution context)
        for frame in self.frames:
            messages.extend(frame.get_llm_messages())

        return messages

    def get_llm_message_objects(self) -> List[LLMMessage]:
        """Get the raw LLM message objects for context compaction."""
        messages = []

        # Add top-level messages first (system messages, etc.)
        messages.extend(self.top_level_llm_messages)

        # Then add frame messages (execution context)
        for frame in self.frames:
            messages.extend(frame.llm_messages)

        return messages

    def add_llm_message(self, message: LLMMessage) -> None:
        """Add an LLM message to the top frame, or to top_level_llm_messages if stack is empty.

        Args:
            message: LLM message to add
        """
        current_frame = self.peek()
        if current_frame is not None:
            current_frame.add_llm_message(message)
        else:
            # Stack is empty - add to top-level messages
            self.top_level_llm_messages.append(message)

    def add_llm_message_with_fallback(self, message: LLMMessage) -> bool:
        """Deprecated: Use add_llm_message instead (now handles fallback automatically).

        Add an LLM message to the top frame, returning success status.

        Args:
            message: LLM message to add

        Returns:
            True if message was added to a frame, False if stack is empty (fallback handled)
        """
        current_frame = self.peek()
        if current_frame is not None:
            current_frame.add_llm_message(message)
            return True
        else:
            # Fallback to top-level messages (same as add_llm_message now does)
            self.top_level_llm_messages.append(message)
            return False

    def add_llm_message_on_parent(self, message: LLMMessage) -> None:
        """Add an LLM message to the parent context.

        If there's a caller frame (second from top), adds to that frame.
        If there's no caller frame, falls back to top_level_llm_messages.

        Used when a called playbook wants to add a message to its parent's context.

        Args:
            message: LLM message to add
        """
        if len(self.frames) >= 2:
            # Add to caller frame (second from top)
            caller_frame = self.frames[-2]
            if caller_frame is not None:
                caller_frame.add_llm_message(message)
        else:
            # No caller frame - fall back to top_level_llm_messages
            self.top_level_llm_messages.append(message)

    def add_llm_message_on_caller(self, message: LLMMessage) -> None:
        """Deprecated: Use add_llm_message_on_parent instead.

        Add an LLM message to the caller frame (second from top).
        """
        self.add_llm_message_on_parent(message)

    def is_artifact_loaded(self, artifact_name: str) -> bool:
        """Check if an artifact is loaded in any frame.

        Args:
            artifact_name: The name of the artifact

        Returns:
            True if the artifact is loaded in any frame, False otherwise.
        """
        from playbooks.llm.messages.types import ArtifactLLMMessage

        for frame in self.frames:
            for msg in frame.llm_messages:
                if isinstance(msg, ArtifactLLMMessage):
                    if msg.artifact.name == artifact_name:
                        return True
        return False
