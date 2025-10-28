from typing import Any, Dict, List, Optional

from playbooks.llm_messages import LLMMessage

from .event_bus import EventBus
from .events import CallStackPopEvent, CallStackPushEvent, InstructionPointerEvent
from .playbook_step import PlaybookStep


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
        step: PlaybookStep = None,
        source_file_path: str = None,
    ):
        self.playbook = playbook
        self.line_number = line_number
        self.source_line_number = source_line_number
        self.source_file_path = source_file_path
        self.step = step

    def copy(self) -> "InstructionPointer":
        return InstructionPointer(
            self.playbook,
            self.line_number,
            self.source_line_number,
            self.step,
            self.source_file_path,
        )

    def increment_instruction_pointer(self) -> None:
        # TODO: this is a hack to advance the instruction pointer
        self.line_number = str(int(self.line_number) + 1)
        self.source_line_number = self.source_line_number + 1

    def to_compact_str(self) -> str:
        compact_str = (
            self.playbook
            if self.line_number is None
            else f"{self.playbook}:{self.line_number}"
        )
        return compact_str

    def __str__(self) -> str:
        compact_str = self.to_compact_str()
        if self.source_line_number is not None:
            return f"{compact_str} ({self.source_file_path}:{self.source_line_number})"
        return compact_str

    def __repr__(self) -> str:
        return str(self)

    def to_dict(self) -> Dict[str, Any]:
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
        langfuse_span: Optional[Any] = None,
        is_meeting: bool = False,
        meeting_id: Optional[str] = None,
    ):
        self.instruction_pointer = instruction_pointer
        self.llm_messages = llm_messages or []
        self.langfuse_span = langfuse_span
        self.is_meeting = is_meeting
        self.meeting_id = meeting_id
        self.depth = -1

    @property
    def source_line_number(self) -> int:
        return self.instruction_pointer.source_line_number

    @property
    def line_number(self) -> int:
        return self.instruction_pointer.line_number

    @property
    def playbook(self) -> str:
        return self.instruction_pointer.playbook

    @property
    def step(self) -> PlaybookStep:
        return self.instruction_pointer.step

    def to_dict(self) -> Dict[str, Any]:
        """Convert the frame to a dictionary representation.

        Returns:
            A dictionary representation of the frame.
        """
        result = {
            "instruction_pointer": str(self.instruction_pointer),
            "langfuse_span": str(self.langfuse_span) if self.langfuse_span else None,
        }
        if self.is_meeting:
            result["is_meeting"] = self.is_meeting
            result["meeting_id"] = self.meeting_id
        return result

    def add_llm_message(self, message: LLMMessage) -> None:
        """Add an LLMMessage object to the call stack frame."""
        self.llm_messages.append(message)

    def __repr__(self) -> str:
        base_repr = self.instruction_pointer.to_compact_str()
        if self.is_meeting and self.meeting_id:
            return f"{base_repr}[meeting {self.meeting_id}]"
        return base_repr

    def get_llm_messages(self) -> List[Dict[str, str]]:
        """Get the messages for the call stack frame as dictionaries for LLM API."""
        return [msg.to_full_message() for msg in self.llm_messages]


class CallStack:
    """A stack of call frames."""

    def __init__(self, event_bus: EventBus, agent_id: str = "unknown"):
        self.frames: List[CallStackFrame] = []
        self.event_bus = event_bus
        self.agent_id = agent_id

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
        for frame in self.frames:
            messages.extend(frame.get_llm_messages())
        return messages

    def add_llm_message(self, message) -> None:
        """Safely add an LLM message to the top frame if the stack is not empty."""
        current_frame = self.peek()
        if current_frame is not None:
            current_frame.add_llm_message(message)

    def add_llm_message_on_caller(self, message) -> None:
        """Safely add an LLM message to the top frame if the stack is not empty."""
        if len(self.frames) < 2:
            return
        current_frame = self.frames[-2]
        if current_frame is not None:
            current_frame.add_llm_message(message)
