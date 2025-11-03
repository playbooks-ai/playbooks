"""Event classes for the playbooks framework.

This module defines various event types used throughout the system for
communication between components, including agent lifecycle events,
playbook execution events, and messaging events.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List


@dataclass(frozen=True)
class Event:
    """Base class for all events."""

    session_id: str
    agent_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class CallStackPushEvent(Event):
    """Call stack frame pushed."""

    frame: str = ""
    stack: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CallStackPopEvent(Event):
    """Call stack frame popped."""

    frame: str = ""
    stack: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class InstructionPointerEvent(Event):
    """Instruction pointer moved."""

    pointer: str = ""
    stack: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompiledProgramEvent(Event):
    """Program compiled successfully."""

    compiled_file_path: str = ""
    content: str = ""
    original_file_paths: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProgramTerminatedEvent(Event):
    """Program terminated."""

    reason: str = ""
    exit_code: int = 0


@dataclass(frozen=True)
class AgentStartedEvent(Event):
    """Agent started."""

    agent_name: str = ""
    agent_type: str = ""


@dataclass(frozen=True)
class AgentStoppedEvent(Event):
    """Agent stopped."""

    agent_name: str = ""
    reason: str = ""


@dataclass(frozen=True)
class AgentPausedEvent(Event):
    """Agent paused execution."""

    reason: str = ""
    source_line_number: int = 0
    step: str = ""


@dataclass(frozen=True)
class AgentResumedEvent(Event):
    """Agent resumed execution."""

    pass


@dataclass(frozen=True)
class AgentStepEvent(Event):
    """Agent performed step operation."""

    step_mode: Any = None


@dataclass(frozen=True)
class BreakpointHitEvent(Event):
    """Breakpoint was hit."""

    file_path: str = ""
    line_number: int = 0
    source_line_number: int = 0


@dataclass(frozen=True)
class StepCompleteEvent(Event):
    """Step operation completed."""

    source_line_number: int = 0


@dataclass(frozen=True)
class VariableUpdateEvent(Event):
    """Agent variables updated."""

    variable_name: str = ""
    variable_value: Any = None


@dataclass(frozen=True)
class ExecutionPausedEvent(Event):
    """Execution paused."""

    reason: str = ""
    source_line_number: int = 0
    step: str = ""


@dataclass(frozen=True)
class LineExecutedEvent(Event):
    """Line of code executed."""

    step: str = ""
    source_line_number: int = 0
    text: str = ""
    file_path: str = ""
    line_number: int = 0


@dataclass(frozen=True)
class PlaybookStartEvent(Event):
    """Playbook started."""

    playbook: str = ""


@dataclass(frozen=True)
class PlaybookEndEvent(Event):
    """Playbook ended."""

    playbook: str = ""
    return_value: Any = None
    call_stack_depth: int = 0


@dataclass(frozen=True)
class ChannelCreatedEvent(Event):
    """Channel created."""

    channel_id: str = ""
    is_meeting: bool = False
    participant_ids: List[str] = field(default_factory=list)
