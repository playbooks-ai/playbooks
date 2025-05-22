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
