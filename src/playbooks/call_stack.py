from typing import Any, Dict, List, Optional

from .event_bus import EventBus
from .events import CallStackPopEvent, CallStackPushEvent, InstructionPointerEvent


class InstructionPointer:
    """Represents a position in a playbook.

    Attributes:
        playbook: The name of the playbook.
        line_number: The line number within the playbook.
        source_line_number: The source line number in the markdown.
    """

    def __init__(self, playbook: str, line_number: str, source_line_number: int):
        self.playbook = playbook
        self.line_number = line_number
        self.source_line_number = source_line_number

    def __str__(self) -> str:
        base = (
            self.playbook
            if self.line_number is None
            else f"{self.playbook}:{self.line_number}"
        )
        if self.source_line_number is not None:
            return f"{base} (src:{self.source_line_number})"
        return base

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
        langfuse_span: Optional[Any] = None,
    ):
        self.instruction_pointer = instruction_pointer
        self.langfuse_span = langfuse_span

    @property
    def source_line_number(self) -> int:
        return self.instruction_pointer.source_line_number

    def to_dict(self) -> Dict[str, Any]:
        """Convert the frame to a dictionary representation.

        Returns:
            A dictionary representation of the frame.
        """
        return {
            "instruction_pointer": str(self.instruction_pointer),
            "langfuse_span": str(self.langfuse_span) if self.langfuse_span else None,
        }

    def __repr__(self) -> str:
        return str(self.instruction_pointer)


class CallStack:
    """A stack of call frames."""

    def __init__(self, event_bus: EventBus):
        self.frames: List[CallStackFrame] = []
        self.event_bus = event_bus

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
        event = CallStackPushEvent(frame=str(frame), stack=self.to_dict())
        self.event_bus.publish(event)

    def pop(self) -> Optional[CallStackFrame]:
        """Remove and return the top frame from the call stack.

        Returns:
            The top frame, or None if the stack is empty.
        """
        frame = self.frames.pop() if self.frames else None
        if frame:
            event = CallStackPopEvent(frame=str(frame), stack=self.to_dict())
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
            pointer=str(instruction_pointer), stack=self.to_dict()
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
