from typing import Any, Dict, List, Optional, Union

from playbooks.interpreter.output_item import OutputItem, StringTrace
from playbooks.trace_mixin import TraceMixin


class InstructionPointer:
    """Represents a position in a playbook.

    Attributes:
        playbook: The name of the playbook.
        line_number: The line number within the playbook.
    """

    def __init__(self, playbook: str, line_number: str):
        self.playbook = playbook
        self.line_number = line_number

    def __str__(self) -> str:
        return (
            self.playbook
            if self.line_number is None
            else f"{self.playbook}:{self.line_number}"
        )


class CallStackFrame:
    """Represents a frame in the call stack.

    Attributes:
        instruction_pointer: Points to the current instruction.
        llm_chat_session_id: ID of the associated LLM chat session, if any.
    """

    def __init__(
        self,
        instruction_pointer: InstructionPointer,
        llm_chat_session_id: Optional[str] = None,
    ):
        self.instruction_pointer = instruction_pointer
        self.llm_chat_session_id = llm_chat_session_id

    def to_dict(self) -> Dict[str, Any]:
        """Convert the frame to a dictionary representation.

        Returns:
            A dictionary representation of the frame.
        """
        return {
            "instruction_pointer": str(self.instruction_pointer),
            "llm_chat_session_id": self.llm_chat_session_id,
        }


class CallStack(TraceMixin):
    """Represents a call stack for playbook execution.

    Tracks the execution path through playbooks with a stack of frames.
    Implements tracing functionality through TraceMixin.

    Attributes:
        frames: The list of CallStackFrame objects in the stack.
    """

    def __init__(self, playbook_lines: Optional[List[str]] = None):
        super().__init__()
        self.frames: List[CallStackFrame] = []

        if playbook_lines:
            for playbook_line in playbook_lines:
                self.push_playbook_line(playbook_line)

    def trace(
        self,
        message: Union[str, OutputItem],
        metadata: Optional[Dict[str, Any]] = None,
        level: str = "INFO",
    ) -> None:
        """Trace a message with call stack information.

        Args:
            message: The message to trace.
            metadata: Additional metadata for the trace.
            level: The level of the trace.
        """
        if isinstance(message, str):
            message = StringTrace(message)

        # Update the trace metadata
        trace_metadata = metadata or {}
        trace_metadata.update(
            {
                "frames": self.to_dict(),
                "level": level,
            }
        )

        # Set the metadata and delegate to parent class for actual tracing
        message.metadata = trace_metadata
        super().trace(message, trace_metadata, level)

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

    def push_playbook_line(self, playbook_line: str) -> None:
        """Push a frame created from a playbook line onto the call stack.

        Args:
            playbook_line: A string in the format "Playbook:LineNumber[:Extra]".
                Example: "Playbook10:04.02:QUE"
        """
        parts = playbook_line.split(":")
        playbook = parts[0]
        line_number = parts[1] if len(parts) > 1 else None
        instruction_pointer = InstructionPointer(playbook, line_number)
        self.push(CallStackFrame(instruction_pointer))

    def pop(self) -> Optional[CallStackFrame]:
        """Remove and return the top frame from the call stack.

        Returns:
            The top frame, or None if the stack is empty.
        """
        return self.frames.pop() if self.frames else None

    def peek(self) -> Optional[CallStackFrame]:
        """Return the top frame without removing it.

        Returns:
            The top frame, or None if the stack is empty.
        """
        return self.frames[-1] if self.frames else None

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
        return [str(frame.instruction_pointer) for frame in self.frames]

    def to_trace(self) -> List[str]:
        """Convert to a trace representation.

        Returns:
            A list of string representations of instruction pointers.
        """
        return self.to_dict()

    def get_trace_metadata(self) -> Dict[str, Any]:
        """Get metadata for tracing.

        Returns:
            A dictionary with frame information.
        """
        return {
            "frames": [frame.to_dict() for frame in self.frames],
        }
