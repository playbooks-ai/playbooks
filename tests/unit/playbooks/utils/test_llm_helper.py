import pytest

from playbooks.enums import LLMMessageRole
from playbooks.utils.llm_helper import (
    consolidate_messages,
    ensure_upto_N_cached_messages,
    make_cached_llm_message,
    make_uncached_llm_message,
)


def test_consolidate_messages_empty_list():
    """Test consolidate_messages with an empty messages list."""
    messages = []

    # Should handle empty list gracefully
    with pytest.raises(IndexError):
        consolidate_messages(messages)


def test_consolidate_messages_three_user_messages_no_cache():
    """Test consolidate_messages with 3 user messages and no cache_control."""
    messages = [
        make_uncached_llm_message("First message", LLMMessageRole.USER),
        make_uncached_llm_message("Second message", LLMMessageRole.USER),
        make_uncached_llm_message("Third message", LLMMessageRole.USER),
    ]

    result = consolidate_messages(messages)

    # Should consolidate all 3 messages into 1
    assert len(result) == 1
    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "First message\n\nSecond message\n\nThird message"
    assert "cache_control" not in result[0]


def test_consolidate_messages_three_user_messages_second_cached():
    """Test consolidate_messages with 3 user messages where second has cache_control."""
    messages = [
        make_uncached_llm_message("First message", LLMMessageRole.USER),
        make_cached_llm_message("Second message", LLMMessageRole.USER),
        make_uncached_llm_message("Third message", LLMMessageRole.USER),
    ]

    result = consolidate_messages(messages)

    # Should create 2 groups: [first, second] and [third]
    assert len(result) == 2

    # First group: first + second messages (cached because second was cached)
    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "First message\n\nSecond message"
    assert "cache_control" in result[0]
    assert result[0]["cache_control"] == {"type": "ephemeral"}

    # Second group: third message (uncached)
    assert result[1]["role"] == LLMMessageRole.USER
    assert result[1]["content"] == "Third message"
    assert "cache_control" not in result[1]


def test_consolidate_messages_three_user_messages_second_and_third_cached():
    """Test consolidate_messages with 3 user messages where second and third have cache_control."""
    messages = [
        make_uncached_llm_message("First message", LLMMessageRole.USER),
        make_cached_llm_message("Second message", LLMMessageRole.USER),
        make_cached_llm_message("Third message", LLMMessageRole.USER),
    ]

    result = consolidate_messages(messages)

    # Should create 2 groups: [first, second] and [third]
    assert len(result) == 2

    # First group: first + second messages (cached because second was cached)
    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "First message\n\nSecond message"
    assert "cache_control" in result[0]
    assert result[0]["cache_control"] == {"type": "ephemeral"}

    # Second group: third message (cached)
    assert result[1]["role"] == LLMMessageRole.USER
    assert result[1]["content"] == "Third message"
    assert "cache_control" in result[1]
    assert result[1]["cache_control"] == {"type": "ephemeral"}


def test_consolidate_messages_mixed_roles_with_cache():
    """Test consolidate_messages with user (no cache), user (cache), assistant (cache), assistant (cache)."""
    messages = [
        make_uncached_llm_message("First user message", LLMMessageRole.USER),
        make_cached_llm_message("Second user message", LLMMessageRole.USER),
        make_cached_llm_message("First assistant message", LLMMessageRole.ASSISTANT),
        make_cached_llm_message("Second assistant message", LLMMessageRole.ASSISTANT),
    ]

    result = consolidate_messages(messages)

    # Should create 2 groups: [user1, user2], [assistant1, assistant2]
    # The second assistant message continues the assistant group until it hits cache_control
    assert len(result) == 2

    # First group: user messages (cached because second was cached)
    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "First user message\n\nSecond user message"
    assert "cache_control" in result[0]
    assert result[0]["cache_control"] == {"type": "ephemeral"}

    # Second group: both assistant messages (cached because both were cached)
    assert result[1]["role"] == LLMMessageRole.ASSISTANT
    assert result[1]["content"] == "First assistant message\n\nSecond assistant message"
    assert "cache_control" in result[1]
    assert result[1]["cache_control"] == {"type": "ephemeral"}


def test_consolidate_messages_role_changes():
    """Test consolidate_messages with alternating roles."""
    messages = [
        make_uncached_llm_message("User message 1", LLMMessageRole.USER),
        make_uncached_llm_message("Assistant message 1", LLMMessageRole.ASSISTANT),
        make_uncached_llm_message("User message 2", LLMMessageRole.USER),
        make_uncached_llm_message("Assistant message 2", LLMMessageRole.ASSISTANT),
    ]

    result = consolidate_messages(messages)

    # Should create 4 groups (one for each message due to alternating roles)
    assert len(result) == 4

    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "User message 1"
    assert "cache_control" not in result[0]

    assert result[1]["role"] == LLMMessageRole.ASSISTANT
    assert result[1]["content"] == "Assistant message 1"
    assert "cache_control" not in result[1]

    assert result[2]["role"] == LLMMessageRole.USER
    assert result[2]["content"] == "User message 2"
    assert "cache_control" not in result[2]

    assert result[3]["role"] == LLMMessageRole.ASSISTANT
    assert result[3]["content"] == "Assistant message 2"
    assert "cache_control" not in result[3]


def test_consolidate_messages_single_message():
    """Test consolidate_messages with a single message."""
    messages = [
        make_uncached_llm_message("Single message", LLMMessageRole.USER),
    ]

    result = consolidate_messages(messages)

    assert len(result) == 1
    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "Single message"
    assert "cache_control" not in result[0]


def test_consolidate_messages_single_cached_message():
    """Test consolidate_messages with a single cached message."""
    messages = [
        make_cached_llm_message("Single cached message", LLMMessageRole.USER),
    ]

    result = consolidate_messages(messages)

    assert len(result) == 1
    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "Single cached message"
    assert "cache_control" in result[0]
    assert result[0]["cache_control"] == {"type": "ephemeral"}


def test_consolidate_messages_system_role():
    """Test consolidate_messages with system role messages."""
    messages = [
        make_uncached_llm_message("System prompt", LLMMessageRole.SYSTEM),
        make_uncached_llm_message("User message", LLMMessageRole.USER),
        make_uncached_llm_message("Assistant response", LLMMessageRole.ASSISTANT),
    ]

    result = consolidate_messages(messages)

    # Should create 3 groups (one for each different role)
    assert len(result) == 3

    assert result[0]["role"] == LLMMessageRole.SYSTEM
    assert result[0]["content"] == "System prompt"
    assert "cache_control" not in result[0]

    assert result[1]["role"] == LLMMessageRole.USER
    assert result[1]["content"] == "User message"
    assert "cache_control" not in result[1]

    assert result[2]["role"] == LLMMessageRole.ASSISTANT
    assert result[2]["content"] == "Assistant response"
    assert "cache_control" not in result[2]


# Tests for ensure_upto_N_cached_messages()


def test_ensure_upto_N_cached_messages_empty_list():
    """Test ensure_upto_N_cached_messages with an empty messages list."""
    messages = []

    result = ensure_upto_N_cached_messages(messages)

    assert result == []


def test_ensure_upto_N_cached_messages_user_message_not_cached():
    """Test ensure_upto_N_cached_messages with a user message not cached."""
    messages = [
        make_uncached_llm_message("User message", LLMMessageRole.USER),
    ]

    result = ensure_upto_N_cached_messages(messages)

    assert len(result) == 1
    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "User message"
    assert "cache_control" not in result[0]


def test_ensure_upto_N_cached_messages_user_message_cached():
    """Test ensure_upto_N_cached_messages with a user message cached."""
    messages = [
        make_cached_llm_message("User message", LLMMessageRole.USER),
    ]

    result = ensure_upto_N_cached_messages(messages)

    assert len(result) == 1
    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "User message"
    assert "cache_control" in result[0]
    assert result[0]["cache_control"] == {"type": "ephemeral"}


def test_ensure_upto_N_cached_messages_system_message_cached():
    """Test ensure_upto_N_cached_messages with a system message cached."""
    messages = [
        make_cached_llm_message("System message", LLMMessageRole.SYSTEM),
    ]

    result = ensure_upto_N_cached_messages(messages)

    assert len(result) == 1
    assert result[0]["role"] == LLMMessageRole.SYSTEM
    assert result[0]["content"] == "System message"
    assert "cache_control" in result[0]
    assert result[0]["cache_control"] == {"type": "ephemeral"}


def test_ensure_upto_N_cached_messages_system_and_user_cached():
    """Test ensure_upto_N_cached_messages with system message cached and user message cached."""
    messages = [
        make_cached_llm_message("System message", LLMMessageRole.SYSTEM),
        make_cached_llm_message("User message", LLMMessageRole.USER),
    ]

    result = ensure_upto_N_cached_messages(messages)

    # Both should remain cached (system is always kept, user is within limit)
    assert len(result) == 2

    assert result[0]["role"] == LLMMessageRole.SYSTEM
    assert result[0]["content"] == "System message"
    assert "cache_control" in result[0]

    assert result[1]["role"] == LLMMessageRole.USER
    assert result[1]["content"] == "User message"
    assert "cache_control" in result[1]


def test_ensure_upto_N_cached_messages_system_plus_five_others():
    """Test ensure_upto_N_cached_messages with system message cached and 5 user/assistant messages cached.
    Should keep system message cached and last 3 user/assistant messages."""
    messages = [
        make_cached_llm_message("System message", LLMMessageRole.SYSTEM),
        make_cached_llm_message("User message 1", LLMMessageRole.USER),
        make_cached_llm_message("Assistant message 1", LLMMessageRole.ASSISTANT),
        make_cached_llm_message("User message 2", LLMMessageRole.USER),
        make_cached_llm_message("Assistant message 2", LLMMessageRole.ASSISTANT),
        make_cached_llm_message("User message 3", LLMMessageRole.USER),
    ]

    result = ensure_upto_N_cached_messages(messages)

    assert len(result) == 6

    # System message should always remain cached
    assert result[0]["role"] == LLMMessageRole.SYSTEM
    assert result[0]["content"] == "System message"
    assert "cache_control" in result[0]

    # First two user/assistant messages should have cache_control removed (earliest ones)
    assert result[1]["role"] == LLMMessageRole.USER
    assert result[1]["content"] == "User message 1"
    assert "cache_control" not in result[1]

    assert result[2]["role"] == LLMMessageRole.ASSISTANT
    assert result[2]["content"] == "Assistant message 1"
    assert "cache_control" not in result[2]

    # Last 3 user/assistant messages should remain cached
    assert result[3]["role"] == LLMMessageRole.USER
    assert result[3]["content"] == "User message 2"
    assert "cache_control" in result[3]

    assert result[4]["role"] == LLMMessageRole.ASSISTANT
    assert result[4]["content"] == "Assistant message 2"
    assert "cache_control" in result[4]

    assert result[5]["role"] == LLMMessageRole.USER
    assert result[5]["content"] == "User message 3"
    assert "cache_control" in result[5]


def test_ensure_upto_N_cached_messages_within_limit():
    """Test ensure_upto_N_cached_messages with 3 cached messages (within limit)."""
    messages = [
        make_cached_llm_message("User message 1", LLMMessageRole.USER),
        make_cached_llm_message("Assistant message 1", LLMMessageRole.ASSISTANT),
        make_cached_llm_message("User message 2", LLMMessageRole.USER),
    ]

    result = ensure_upto_N_cached_messages(messages)

    # All should remain cached since within limit
    assert len(result) == 3

    for i, expected_content in enumerate(
        ["User message 1", "Assistant message 1", "User message 2"]
    ):
        assert result[i]["content"] == expected_content
        assert "cache_control" in result[i]


def test_ensure_upto_N_cached_messages_mixed_cached_uncached():
    """Test ensure_upto_N_cached_messages with mixed cached and uncached messages."""
    messages = [
        make_uncached_llm_message("User message 1", LLMMessageRole.USER),
        make_cached_llm_message("User message 2", LLMMessageRole.USER),
        make_uncached_llm_message("Assistant message 1", LLMMessageRole.ASSISTANT),
        make_cached_llm_message("Assistant message 2", LLMMessageRole.ASSISTANT),
        make_cached_llm_message("User message 3", LLMMessageRole.USER),
    ]

    result = ensure_upto_N_cached_messages(messages)

    assert len(result) == 5

    # Uncached messages should remain uncached
    assert result[0]["content"] == "User message 1"
    assert "cache_control" not in result[0]

    assert result[2]["content"] == "Assistant message 1"
    assert "cache_control" not in result[2]

    # All cached messages should remain cached (only 3 total, within limit)
    assert result[1]["content"] == "User message 2"
    assert "cache_control" in result[1]

    assert result[3]["content"] == "Assistant message 2"
    assert "cache_control" in result[3]

    assert result[4]["content"] == "User message 3"
    assert "cache_control" in result[4]


def test_ensure_upto_N_cached_messages_only_system_messages():
    """Test ensure_upto_N_cached_messages with multiple system messages (should all remain cached)."""
    messages = [
        make_cached_llm_message("System message 1", LLMMessageRole.SYSTEM),
        make_cached_llm_message("System message 2", LLMMessageRole.SYSTEM),
        make_cached_llm_message("System message 3", LLMMessageRole.SYSTEM),
        make_cached_llm_message("System message 4", LLMMessageRole.SYSTEM),
        make_cached_llm_message("System message 5", LLMMessageRole.SYSTEM),
    ]

    result = ensure_upto_N_cached_messages(messages)

    # All system messages should remain cached regardless of limit
    assert len(result) == 5

    for i, expected_content in enumerate(
        [
            "System message 1",
            "System message 2",
            "System message 3",
            "System message 4",
            "System message 5",
        ]
    ):
        assert result[i]["role"] == LLMMessageRole.SYSTEM
        assert result[i]["content"] == expected_content
        assert "cache_control" in result[i]
