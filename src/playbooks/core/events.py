"""Event classes for the playbooks framework.

This module defines various event types used throughout the system for
communication between components, including agent lifecycle events,
playbook execution events, and messaging events.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional


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


@dataclass(frozen=True)
class AgentCreatedEvent(Event):
    """Agent instance created and registered in the Program."""

    agent_id: str = ""
    agent_klass: str = ""


@dataclass(frozen=True)
class AgentTerminatedEvent(Event):
    """Agent instance terminated."""

    agent_id: str = ""
    agent_klass: str = ""


@dataclass(frozen=True)
class MessageSentEvent(Event):
    """Message sent across a channel."""

    message_id: str = ""
    sender_id: str = ""
    sender_klass: str = ""
    recipients: str = ""  # e.g., "user", "agent 1002", "meeting 100, agent 1002"
    content_preview: str = ""  # First 100 chars of message
    channel_id: str = ""


@dataclass(frozen=True)
class MessageReceivedEvent(Event):
    """Message added to an agent's message queue."""

    message_id: str = ""
    recipient_id: str = ""
    recipient_klass: str = ""
    sender_id: str = ""
    sender_klass: str = ""


@dataclass(frozen=True)
class MessageRoutedEvent(Event):
    """A message was routed via Program/Channel."""

    channel_id: str = ""
    message: Any = None


@dataclass(frozen=True)
class WaitForMessageEvent(Event):
    """An agent waited for messages and either received some or timed out."""

    wait_for_message_from: str = ""
    timeout: Optional[float] = None
    received_count: int = 0


@dataclass(frozen=True)
class LLMCallStartedEvent(Event):
    """LLM call initiated."""

    model: str = ""
    input_tokens: int = 0
    input: Any = None
    stream: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class LLMCallEndedEvent(Event):
    """LLM call completed."""

    model: str = ""
    output_tokens: int = 0
    output: Any = None
    error: Optional[str] = None
    cache_hit: bool = False


@dataclass(frozen=True)
class MethodCallStartedEvent(Event):
    """Agent method call started."""

    method_name: str = ""
    args: Any = None
    kwargs: Any = None


@dataclass(frozen=True)
class MethodCallEndedEvent(Event):
    """Agent method call completed."""

    method_name: str = ""
    result: Any = None
    error: Optional[str] = None


@dataclass(frozen=True)
class CompilationStartedEvent(Event):
    """Playbook compilation started."""

    file_path: str = ""
    content_length: int = 0


@dataclass(frozen=True)
class CompilationEndedEvent(Event):
    """Playbook compilation completed."""

    file_path: str = ""
    compiled_content_length: int = 0
    error: Optional[str] = None
