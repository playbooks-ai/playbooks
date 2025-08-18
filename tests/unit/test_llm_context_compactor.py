"""Tests for LLM context compaction functionality."""

from unittest.mock import patch

import pytest

from playbooks.llm_context_compactor import CompactionConfig, LLMContextCompactor
from playbooks.llm_messages import (
    AssistantResponseLLMMessage,
    SystemPromptLLMMessage,
    UserInputLLMMessage,
)


class TestCompactionConfig:
    """Test CompactionConfig functionality."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CompactionConfig()
        assert config.min_preserved_assistant_messages == 1
        assert config.batch_size == 3
        assert config.enabled is True

    def test_config_from_env(self):
        """Test configuration from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "LLM_COMPACTION_ENABLED": "false",
                "LLM_COMPACTION_MIN_PRESERVED_ASSISTANT_MESSAGES": "5",
                "LLM_COMPACTION_BATCH_SIZE": "2",
            },
        ):
            config = CompactionConfig()
            assert config.enabled is False
            assert config.min_preserved_assistant_messages == 5
            assert config.batch_size == 2


def get_assistant_contents_compacted(index):
    return f"""This is step {index}"""


def get_assistant_contents(index):
    return f"""recap - This is step {index}
    plan - This is the plan {index}
    some execution logs
"""


def get_user_contents(index):
    return f"""User input {index}"""


def get_message_pairs(pair_count):
    messages = []
    for i in range(pair_count):
        messages.append(UserInputLLMMessage(get_user_contents(i * 2)))
        messages.append(AssistantResponseLLMMessage(get_assistant_contents(i * 2 + 1)))
    return messages


class TestLLMContextCompactor:
    """Test LLMContextCompactor functionality."""

    def test_disabled_compactor(self):
        """Test that disabled compactor returns original messages."""
        config = CompactionConfig(enabled=False)
        compactor = LLMContextCompactor(config)

        messages = get_message_pairs(1)

        result = compactor.compact_messages(messages)

        # Should return original messages as full messages
        assert len(result) == 2
        assert result[0]["content"] == get_user_contents(0)
        assert result[1]["content"] == get_assistant_contents(1)

    def test_insufficient_messages_no_compaction(self):
        """Test that insufficient messages don't trigger compaction."""
        compactor = LLMContextCompactor(
            CompactionConfig(min_preserved_assistant_messages=2, batch_size=2)
        )

        # Only 2 assistant responses (need 7 for compaction with default config)
        messages = get_message_pairs(2)

        result = compactor.compact_messages(messages)

        # Should return original messages
        assert len(result) == 4
        assert result[0]["content"] == get_user_contents(0)
        assert result[1]["content"] == get_assistant_contents(1)
        assert result[2]["content"] == get_user_contents(2)
        assert result[3]["content"] == get_assistant_contents(3)

    def test_basic_compaction_scenario(self):
        """Test basic compaction with sufficient messages."""
        config = CompactionConfig(min_preserved_assistant_messages=2, batch_size=2)
        compactor = LLMContextCompactor(config)

        messages = get_message_pairs(4)  # u0, a1, u2, a3, u4, a5, u6, a7

        result = compactor.compact_messages(messages)

        # expected:  # u0_compacted_deleted, a1_compacted, u2_compacted_deleted, a3_compacted, u4, a5, u6, a7
        # so, expected result: a1_compacted, a3_compacted, u4, a5, u6, a7
        assert len(result) == 6
        assert result[0]["content"] == get_assistant_contents_compacted(1)
        assert result[1]["content"] == get_assistant_contents_compacted(3)
        assert result[2]["content"] == get_user_contents(4)
        assert result[3]["content"] == get_assistant_contents(5)
        assert result[4]["content"] == get_user_contents(6)
        assert result[5]["content"] == get_assistant_contents(7)

    def compacted_assistant_message_user_role(self):
        """Test that compacted assistant message is user role."""
        response = AssistantResponseLLMMessage(get_assistant_contents(1))
        compacted = response.to_compact_message()
        assert compacted["role"] == "user"
        assert compacted["content"] == get_assistant_contents_compacted(1)

    def test_empty_messages_list(self):
        """Test handling of empty messages list."""
        compactor = LLMContextCompactor()
        result = compactor.compact_messages([])
        assert result == []

    def test_non_user_assistant_messages_preserved(self):
        """Test that non-user/assistant messages are always preserved."""
        compactor = LLMContextCompactor()

        messages = [
            SystemPromptLLMMessage("System prompt"),
            UserInputLLMMessage("User input"),
            AssistantResponseLLMMessage("Assistant response"),
        ]

        result = compactor.compact_messages(messages)

        # System message should always be preserved
        system_messages = [msg for msg in result if msg.get("role") == "system"]
        assert len(system_messages) == 1
        assert system_messages[0]["content"] == "System prompt"


if __name__ == "__main__":
    pytest.main([__file__])
