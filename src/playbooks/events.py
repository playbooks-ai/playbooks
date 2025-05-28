from dataclasses import dataclass
from typing import Any, List


class Event:
    session_id: str


@dataclass
class CallStackPushEvent(Event):
    frame: str
    stack: List[str]


@dataclass
class CallStackPopEvent(Event):
    frame: str
    stack: List[str]


@dataclass
class InstructionPointerEvent(Event):
    pointer: str
    stack: List[str]


@dataclass
class VariableUpdateEvent(Event):
    name: str
    value: Any


@dataclass
class PlaybookStartEvent(Event):
    playbook: str


@dataclass
class PlaybookEndEvent(Event):
    playbook: str
    return_value: Any
    call_stack_depth: int = 0


@dataclass
class LineExecutedEvent(Event):
    step: str
    source_line_number: int
    text: str


@dataclass
class BreakpointHitEvent(Event):
    source_line_number: int


@dataclass
class CompiledProgramEvent(Event):
    compiled_file_path: str  # e.g., "hello.pbc"
    content: str  # Full compiled program content
    original_file_paths: List[str]  # Original source files that were compiled


@dataclass
class ExecutionPausedEvent(Event):
    reason: str  # 'step', 'breakpoint', 'entry', 'pause'
    source_line_number: int
    step: str


@dataclass
class StepCompleteEvent(Event):
    source_line_number: int
