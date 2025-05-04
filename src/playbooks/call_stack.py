from typing import Any, Dict, List, Optional


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

    def __repr__(self) -> str:
        return str(self)

    @classmethod
    def from_step(cls, step: str) -> "InstructionPointer":
        return cls(step.split(":")[0], step.split(":")[1])


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

    def to_dict(self) -> Dict[str, Any]:
        """Convert the frame to a dictionary representation.

        Returns:
            A dictionary representation of the frame.
        """
        return {
            "instruction_pointer": str(self.instruction_pointer),
            "llm_chat_session_id": self.llm_chat_session_id,
        }

    def __repr__(self) -> str:
        return str(self.instruction_pointer)


class CallStack:
    """Represents a call stack for playbook execution.

    Tracks the execution path through playbooks with a stack of frames.
    Implements tracing functionality through TraceMixin.

    Attributes:
        frames: The list of CallStackFrame objects in the stack.
    """

    def __init__(self, playbook_lines: Optional[List[str]] = None):
        self.frames: List[CallStackFrame] = []

        if playbook_lines:
            for playbook_line in playbook_lines:
                self.push_playbook_line(playbook_line)

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

    def advance_instruction_pointer(
        self, instruction_pointer: InstructionPointer
    ) -> None:
        """Advance the instruction pointer to the next instruction.

        Args:
            instruction_pointer: The new instruction pointer.
        """
        self.frames[-1].instruction_pointer = instruction_pointer

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
