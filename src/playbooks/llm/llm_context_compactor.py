"""LLM context compaction for managing conversation history size."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from playbooks.llm.messages import (
    AssistantResponseLLMMessage,
    LLMMessage,
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

        Keeps the last N assistant message cycles in full format while compacting
        older messages to summaries.

        Args:
            messages: List of LLMMessage objects to potentially compact

        Returns:
            List of message dictionaries in LLM API format (with compacted older messages)
        """
        if not self.config.enabled or len(messages) == 0:
            return [msg.to_full_message() for msg in messages]

        # Walk backwards to find last safe (uncompacted) assistant message
        assistant_count = 0
        safe_assistant_index = -1
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], AssistantResponseLLMMessage):
                assistant_count += 1
                if assistant_count >= self.config.keep_last_n_assistant_messages:
                    safe_assistant_index = i
                    break

        # If no safe assistant message found, return all messages as full
        if safe_assistant_index == -1:
            return [msg.to_full_message() for msg in messages]

        # The safe_assistant_index is the first assistant message we want to keep full.
        # We compact ALL messages before this index (including user messages).
        # We keep ALL messages at or after this index full.
        # This ensures only user messages that are part of the last N assistant cycles are kept full.
        safe_index = safe_assistant_index

        # All messages before safe_index are compacted
        # Messages at or after safe_index are kept full
        result = []
        for i, msg in enumerate(messages):
            if i < safe_index:
                compact_message = msg.to_compact_message()
                if compact_message:
                    result.append(compact_message)
            else:
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
