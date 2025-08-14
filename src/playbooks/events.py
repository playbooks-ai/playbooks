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
    thread_id: int = None


@dataclass
class CompiledProgramEvent(Event):
    compiled_file_path: str  # e.g., "hello.pbasm"
    content: str  # Full compiled program content
    original_file_paths: List[str]  # Original source files that were compiled


@dataclass
class ExecutionPausedEvent(Event):
    reason: str  # 'step', 'breakpoint', 'entry', 'pause'
    source_line_number: int
    step: str
    thread_id: int = None


@dataclass
class StepCompleteEvent(Event):
    source_line_number: int
    thread_id: int = None


@dataclass
class ProgramTerminatedEvent(Event):
    reason: str  # 'normal', 'error', 'cancelled'
    exit_code: int = 0


@dataclass
class AgentStartedEvent(Event):
    agent_id: str
    agent_name: str
    thread_id: int
    agent_type: str


@dataclass
class AgentStoppedEvent(Event):
    agent_id: str
    agent_name: str
    thread_id: int
    reason: str  # 'normal', 'error', 'cancelled'


@dataclass
class AgentPausedEvent(Event):
    agent_id: str
    agent_name: str
    thread_id: int
    reason: str  # 'step', 'breakpoint', 'pause'
    source_line_number: int = 0


@dataclass
class AgentResumedEvent(Event):
    agent_id: str
    agent_name: str
    thread_id: int


@dataclass
class AgentVariableUpdateEvent(Event):
    agent_id: str
    thread_id: int
    variable_name: str
    variable_value: Any
