from typing import List, Union

from playbooks.trace_mixin import TraceMixin


class InstructionPointer:
    def __init__(self, playbook: str, line_number: str):
        self.playbook = playbook
        self.line_number = line_number

    def __str__(self):
        return (
            self.playbook
            if self.line_number is None
            else f"{self.playbook}:{self.line_number}"
        )


class CallStackFrame:
    def __init__(
        self, instruction_pointer: InstructionPointer, llm_chat_session_id: str
    ):
        self.instruction_pointer = instruction_pointer
        self.llm_chat_session_id = llm_chat_session_id


class CallStack(TraceMixin):
    def __init__(self):
        super().__init__()
        self._trace_metadata["frames"] = []
        self.frames: List[CallStackFrame] = []

    def is_empty(self) -> bool:
        return not self.frames

    def push(self, frame: CallStackFrame):
        self.frames.append(frame)

    def pop(self) -> CallStackFrame:
        return self.frames.pop() if self.frames else None

    def peek(self) -> CallStackFrame:
        return self.frames[-1] if self.frames else None

    def __repr__(self):
        frames = ", ".join(self.to_dict())
        return f"CallStack(frames=[{frames}])"

    def __str__(self):
        return self.__repr__()

    def to_dict(self):
        return [str(frame.instruction_pointer) for frame in self.frames]

    def to_trace(self) -> Union[str, List]:
        self._trace_metadata["frames"] = self.to_dict()
        return "CallStack"
