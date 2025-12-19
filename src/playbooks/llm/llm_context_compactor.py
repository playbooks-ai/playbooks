"""LLM context compaction for managing conversation history size."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from playbooks.llm.messages import (
    AssistantResponseLLMMessage,
    LLMMessage,
    UserInputLLMMessage,
)


@dataclass
class CompactionConfig:
    """Configuration for LLM context compaction.

    Attributes:
        enabled: Whether compaction is enabled
        keep_last_n_assistant_messages: Number of most recent assistant messages to keep in full
    """

    enabled: bool = True
    min_preserved_assistant_messages: int = (
        2  # Alias for keep_last_n_assistant_messages
    )

    @property
    def keep_last_n_assistant_messages(self) -> int:
        """Alias for min_preserved_assistant_messages for backward compatibility."""
        return self.min_preserved_assistant_messages


class LLMContextCompactor:
    """Manages compaction of LLM conversation history to reduce token usage.

    The compactor preserves the most recent N assistant message cycles in full
    while compacting older messages to summaries. This maintains context while
    reducing token consumption for long conversations.
    """

    def __init__(self, config: Optional[CompactionConfig] = None):
        """Initialize the compactor with configuration.

        Args:
            config: Compaction configuration, uses defaults if None
        """
        self.config = config or CompactionConfig()

    def compact_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """Compact a list of LLM messages based on configuration.

        Keeps the last N assistant messages and the last user message in full format.
        All other assistant and user messages are compacted. Other message types
        (System, AgentInfo, etc.) are always kept full.

        Args:
            messages: List of LLMMessage objects to potentially compact

        Returns:
            List of message dictionaries in LLM API format (with compacted older messages)
        """
        if not self.config.enabled or not messages:
            return [msg.to_full_message() for msg in messages]

        # Identify indices of assistant and user messages
        assistant_indices = [
            i
            for i, msg in enumerate(messages)
            if isinstance(msg, AssistantResponseLLMMessage)
        ]
        user_indices = [
            i for i, msg in enumerate(messages) if isinstance(msg, UserInputLLMMessage)
        ]

        # Determine which indices to keep full
        keep_full = set(
            assistant_indices[-self.config.keep_last_n_assistant_messages :]
        )
        if user_indices:
            keep_full.add(user_indices[-1])

        result = []
        for i, msg in enumerate(messages):
            # If it's a message type that supports compaction and not in keep_full, compact it
            if isinstance(msg, (AssistantResponseLLMMessage, UserInputLLMMessage)):
                if i in keep_full:
                    result.append(msg.to_full_message())
                else:
                    result.append(msg.to_compact_message())
            else:
                # Other messages (System, AgentInfo, etc.) are always full
                result.append(msg.to_full_message())

        return result


# Convenience function for easy integration
def compact_llm_messages(
    messages: List[LLMMessage], config: Optional[CompactionConfig] = None
) -> List[Dict[str, Any]]:
    """Compact a list of LLM messages using the default compactor.

    Args:
        messages: List of LLM messages to compact
        config: Optional compaction configuration

    Returns:
        List of compacted messages in LLM API format
    """
    compactor = LLMContextCompactor(config)
    return compactor.compact_messages(messages)
