"""Tests for LLM helper functions using clean semantic message architecture."""

from unittest.mock import patch

import pytest

from playbooks.core.enums import LLMMessageRole
from playbooks.core.exceptions import VendorAPIOverloadedError, VendorAPIRateLimitError
from playbooks.llm.messages import LLMMessage
from playbooks.utils.llm_helper import (
    _make_completion_request,
    consolidate_messages,
    custom_get_cache_key,
    ensure_upto_N_cached_messages,
    get_messages_for_prompt,
    remove_empty_messages,
    retry_on_overload,
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
        LLMMessage("First message", LLMMessageRole.USER).to_full_message(
            is_cached=False
        ),
        LLMMessage("Second message", LLMMessageRole.USER).to_full_message(
            is_cached=False
        ),
        LLMMessage("Third message", LLMMessageRole.USER).to_full_message(
            is_cached=False
        ),
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
        LLMMessage("First message", LLMMessageRole.USER).to_full_message(
            is_cached=False
        ),
        LLMMessage("Second message", LLMMessageRole.USER).to_full_message(
            is_cached=True
        ),
        LLMMessage("Third message", LLMMessageRole.USER).to_full_message(
            is_cached=False
        ),
    ]

    result = consolidate_messages(messages)

    # Should create 2 groups: [first, second] and [third]
    assert len(result) == 2

    # First group: first + second messages (cached because second was cached)
    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "First message\n\nSecond message"
    assert "cache_control" in result[0]
    assert result[0]["cache_control"] == {"type": "ephemeral"}

    # Second group: third message (not cached)
    assert result[1]["role"] == LLMMessageRole.USER
    assert result[1]["content"] == "Third message"
    assert "cache_control" not in result[1]


def test_ensure_upto_N_cached_messages_empty_list():
    """Test ensure_upto_N_cached_messages with an empty messages list."""
    messages = []

    result = ensure_upto_N_cached_messages(messages)

    assert result == []


def test_ensure_upto_N_cached_messages_user_message_not_cached():
    """Test ensure_upto_N_cached_messages with a user message not cached."""
    messages = [
        LLMMessage("User message", LLMMessageRole.USER).to_full_message(
            is_cached=False
        ),
    ]

    result = ensure_upto_N_cached_messages(messages)

    assert len(result) == 1
    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "User message"
    assert "cache_control" not in result[0]


def test_ensure_upto_N_cached_messages_user_message_cached():
    """Test ensure_upto_N_cached_messages with a user message cached."""
    messages = [
        LLMMessage("User message", LLMMessageRole.USER).to_full_message(is_cached=True),
    ]

    result = ensure_upto_N_cached_messages(messages)

    assert len(result) == 1
    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "User message"
    assert "cache_control" in result[0]
    assert result[0]["cache_control"] == {"type": "ephemeral"}


def test_semantic_message_integration():
    """Test that semantic message types work correctly with helper functions."""
    from playbooks.llm.messages import (
        AssistantResponseLLMMessage,
        SystemPromptLLMMessage,
        UserInputLLMMessage,
    )

    messages = [
        SystemPromptLLMMessage("System prompt").to_full_message(is_cached=True),
        UserInputLLMMessage("User input").to_full_message(is_cached=False),
        AssistantResponseLLMMessage("Assistant response").to_full_message(
            is_cached=False
        ),
    ]

    # Test remove empty messages
    filtered = remove_empty_messages(messages)
    assert len(filtered) == 3

    # Test consolidation
    consolidated = consolidate_messages(messages)
    assert len(consolidated) == 3  # Different roles, so no consolidation

    # Test cache limiting
    limited = ensure_upto_N_cached_messages(messages)
    assert len(limited) == 3

    # System message should remain cached, others should not be cached by default
    system_msg = next(msg for msg in limited if msg["role"] == LLMMessageRole.SYSTEM)
    assert "cache_control" in system_msg

    user_msg = next(msg for msg in limited if msg["role"] == LLMMessageRole.USER)
    assert "cache_control" not in user_msg


def test_get_messages_for_prompt_user_only():
    """Test get_messages_for_prompt with user message only."""
    prompt = "What is the capital of France?"

    result = get_messages_for_prompt(prompt)

    assert len(result) == 1
    assert result[0]["role"] == LLMMessageRole.USER
    assert result[0]["content"] == "What is the capital of France?"
    assert "cache_control" not in result[0]


def test_get_messages_for_prompt_with_system_delimiter():
    """Test get_messages_for_prompt with system prompt delimiter."""
    prompt = "You are a helpful assistant.\n\n====SYSTEM_PROMPT_DELIMITER====\n\nWhat is the capital of France?"

    result = get_messages_for_prompt(prompt)

    assert len(result) == 2

    # System message should be cached
    assert result[0]["role"] == LLMMessageRole.SYSTEM
    assert result[0]["content"] == "You are a helpful assistant."
    assert "cache_control" in result[0]

    # User message should not be cached
    assert result[1]["role"] == LLMMessageRole.USER
    assert result[1]["content"] == "What is the capital of France?"
    assert "cache_control" not in result[1]


def test_remove_empty_messages():
    """Test remove_empty_messages function."""
    messages = [
        {"content": "Valid message", "role": LLMMessageRole.USER},
        {"content": "   ", "role": LLMMessageRole.USER},  # Only whitespace
        {"content": "", "role": LLMMessageRole.USER},  # Empty
        {"content": "Another valid message", "role": LLMMessageRole.ASSISTANT},
    ]

    result = remove_empty_messages(messages)

    assert len(result) == 2
    assert result[0]["content"] == "Valid message"
    assert result[1]["content"] == "Another valid message"


def test_custom_get_cache_key():
    """Test custom_get_cache_key function."""
    kwargs1 = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.0,
    }

    kwargs2 = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.0,
    }

    kwargs3 = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Different message"}],
        "temperature": 0.0,
    }

    key1 = custom_get_cache_key(**kwargs1)
    key2 = custom_get_cache_key(**kwargs2)
    key3 = custom_get_cache_key(**kwargs3)

    # Same parameters should produce same key
    assert key1 == key2

    # Different parameters should produce different key
    assert key1 != key3

    # Keys should be reasonable length hashes
    assert len(key1) == 32
    assert isinstance(key1, str)


@patch("playbooks.utils.llm_helper.completion")
def test_make_completion_request(mock_completion):
    """Test _make_completion_request function."""
    mock_completion.return_value = {
        "choices": [{"message": {"content": "Test response"}}]
    }

    kwargs = {"model": "gpt-4", "messages": []}
    result = _make_completion_request(kwargs)

    assert result == "Test response"
    mock_completion.assert_called_once_with(**kwargs)


def test_retry_on_overload_decorator():
    """Test retry_on_overload decorator."""
    call_count = 0

    @retry_on_overload(max_retries=3, base_delay=0.01)
    def failing_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise VendorAPIRateLimitError("Rate limited")
        return "Success"

    result = failing_function()

    assert result == "Success"
    assert call_count == 3


def test_retry_on_overload_max_retries_exceeded():
    """Test retry_on_overload when max retries exceeded."""
    call_count = 0

    @retry_on_overload(max_retries=2, base_delay=0.01)
    def always_failing_function():
        nonlocal call_count
        call_count += 1
        raise VendorAPIOverloadedError("Always fails")

    with pytest.raises(VendorAPIOverloadedError):
        always_failing_function()

    assert call_count == 2  # Should have tried max_retries times
