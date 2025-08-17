"""Clean semantic LLM message system.

This module provides a minimal, highly maintainable set of semantic message types
that cover all use cases in the playbook execution system.
"""

from .base import LLMMessage
from .types import (
    # Core semantic types
    SystemPromptLLMMessage,
    UserInputLLMMessage,
    AssistantResponseLLMMessage,
    # Playbook execution types
    PlaybookImplementationLLMMessage,
    ExecutionResultLLMMessage,
    TriggerInstructionsLLMMessage,
    # Communication types
    AgentCommunicationLLMMessage,
    MeetingLLMMessage,
    # Agent information types
    AgentInfoLLMMessage,
    OtherAgentInfoLLMMessage,
    # Data types
    FileLoadLLMMessage,
    SessionLogLLMMessage,
)

__all__ = [
    "LLMMessage",
    # Core semantic types
    "SystemPromptLLMMessage",
    "UserInputLLMMessage",
    "AssistantResponseLLMMessage",
    # Playbook execution types
    "PlaybookImplementationLLMMessage",
    "ExecutionResultLLMMessage",
    "TriggerInstructionsLLMMessage",
    # Communication types
    "AgentCommunicationLLMMessage",
    "MeetingLLMMessage",
    # Agent information types
    "AgentInfoLLMMessage",
    "OtherAgentInfoLLMMessage",
    # Data types
    "FileLoadLLMMessage",
    "SessionLogLLMMessage",
]
