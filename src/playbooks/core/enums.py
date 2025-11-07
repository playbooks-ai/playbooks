"""Enumeration types used throughout the playbooks framework.

This module defines various enum types for agent types, routing modes,
LLM message roles and types, execution modes, and other categorical values
used in the system.
"""

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
    # Core execution types
    SYSTEM_PROMPT = "system_prompt"
    USER_INPUT = "user_input"
    ASSISTANT_RESPONSE = "assistant_response"

    # Playbook execution types
    PLAYBOOK_IMPLEMENTATION = "playbook_implementation"
    EXECUTION_RESULT = "execution_result"
    TRIGGER_INSTRUCTIONS = "trigger_instructions"

    # Communication types
    AGENT_COMMUNICATION = "agent_communication"
    MEETING_MESSAGE = "meeting_message"

    # Agent information types
    AGENT_INFO = "agent_info"
    OTHER_AGENT_INFO = "other_agent_info"

    # Data types
    FILE_LOAD = "file_load"
    SESSION_LOG = "session_log"
    ARTIFACT = "artifact"


class StartupMode(str, Enum):
    DEFAULT = "default"
    STANDBY = "standby"


class LLMExecutionMode(str, Enum):
    """Execution modes for LLM playbooks."""

    PLAYBOOK = "playbook"  # Traditional structured steps (default)
    REACT = "react"  # Loops with tool calls until exit conditions
    RAW = "raw"  # One LLM call, no loops or structure
