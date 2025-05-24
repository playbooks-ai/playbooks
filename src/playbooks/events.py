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


@dataclass
class LineExecutedEvent(Event):
    step: str
    text: str


@dataclass
class BreakpointHitEvent(Event):
    file_path: str
    line_number: int
    step: str


@dataclass
class CompiledProgramEvent(Event):
    compiled_file_path: str  # e.g., "hello.pbc"
    content: str  # Full compiled program content
    original_file_paths: List[str]  # Original source files that were compiled
