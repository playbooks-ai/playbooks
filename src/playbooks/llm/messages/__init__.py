"""Clean semantic LLM message system.

This module provides a minimal, highly maintainable set of semantic message types
that cover all use cases in the playbook execution system.
"""

from .base import LLMMessage
from .types import (
    # Communication types
    AgentCommunicationLLMMessage,
    # Agent information types
    AgentInfoLLMMessage,
    ArtifactLLMMessage,
    AssistantResponseLLMMessage,
    ExecutionResultLLMMessage,
    # Data types
    FileLoadLLMMessage,
    MeetingLLMMessage,
    OtherAgentInfoLLMMessage,
    # Playbook execution types
    PlaybookImplementationLLMMessage,
    SessionLogLLMMessage,
    # Core semantic types
    SystemPromptLLMMessage,
    TriggerInstructionsLLMMessage,
    UserInputLLMMessage,
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
    "ArtifactLLMMessage",
]
