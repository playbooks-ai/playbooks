from enum import Enum


class AgentType(str, Enum):
    HUMAN = "human"
    AI = "ai"


class RoutingType(str, Enum):
    DIRECT = "direct"
    BROADCAST = "broadcast"


class LLMMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class LLMMessageType(str, Enum):
    DEFAULT = "DEFAULT"
    LOAD_FILE = "LoadFile"


class StartupMode(str, Enum):
    DEFAULT = "default"
    STANDBY = "standby"


class LLMExecutionMode(str, Enum):
    """Execution modes for LLM playbooks."""

    PLAYBOOK = "playbook"  # Traditional structured steps (default)
    REACT = "react"  # Loops with tool calls until exit conditions
    RAW = "raw"  # One LLM call, no loops or structure
