import hashlib
import os
import time
from unittest.mock import Mock, patch

import litellm
import pytest

from playbooks.enums import LLMMessageRole
from playbooks.exceptions import VendorAPIOverloadedError, VendorAPIRateLimitError
from playbooks.utils.llm_config import LLMConfig
from playbooks.utils.llm_helper import (
    _make_completion_request,
    _make_completion_request_stream,
    consolidate_messages,
    custom_get_cache_key,
    ensure_upto_N_cached_messages,
    get_completion,
    get_messages_for_prompt,
    make_cached_llm_message,
    make_uncached_llm_message,
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


class TestCustomGetCacheKey:
    """Test the custom_get_cache_key function."""

    def test_cache_key_generation(self):
        """Test that cache key is generated correctly."""
        kwargs = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
            "logit_bias": {"token": 1.0},
        }

        key = custom_get_cache_key(**kwargs)

        # Should be 32 character hex string
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_cache_key_consistency(self):
        """Test that same inputs produce same cache key."""
        kwargs = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
        }

        key1 = custom_get_cache_key(**kwargs)
        key2 = custom_get_cache_key(**kwargs)

        assert key1 == key2

    def test_cache_key_different_for_different_inputs(self):
        """Test that different inputs produce different cache keys."""
        kwargs1 = {"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}
        kwargs2 = {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]}

        key1 = custom_get_cache_key(**kwargs1)
        key2 = custom_get_cache_key(**kwargs2)

        assert key1 != key2

    def test_cache_key_with_missing_params(self):
        """Test cache key generation with missing optional parameters."""
        kwargs = {"model": "gpt-4"}

        key = custom_get_cache_key(**kwargs)

        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_cache_key_deterministic_hash(self):
        """Test that cache key uses deterministic hashing."""
        import json

        kwargs = {"model": "test", "messages": "test", "temperature": 1.0}

        # Calculate expected hash manually using the new JSON-based approach
        cache_components = {
            "model": "test",
            "messages": "test",
            "temperature": 1.0,
            "logit_bias": {},
        }
        key_str = json.dumps(cache_components, sort_keys=True, separators=(",", ":"))
        expected_hash = hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:32]

        actual_key = custom_get_cache_key(**kwargs)
        assert actual_key == expected_hash


class TestRetryOnOverload:
    """Test the retry_on_overload decorator."""

    def test_decorator_success_no_retry(self):
        """Test that successful function calls don't trigger retries."""
        call_count = 0

        @retry_on_overload(max_retries=3, base_delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = test_function()

        assert result == "success"
        assert call_count == 1

    def test_decorator_retry_on_rate_limit_error(self):
        """Test retry logic with VendorAPIRateLimitError."""
        call_count = 0

        @retry_on_overload(max_retries=3, base_delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise VendorAPIRateLimitError("Rate limited")
            return "success"

        result = test_function()

        assert result == "success"
        assert call_count == 3

    def test_decorator_retry_on_overload_error(self):
        """Test retry logic with VendorAPIOverloadedError."""
        call_count = 0

        @retry_on_overload(max_retries=2, base_delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise VendorAPIOverloadedError("Overloaded")
            return "success"

        result = test_function()

        assert result == "success"
        assert call_count == 2

    def test_decorator_retry_on_litellm_errors(self):
        """Test retry logic with various litellm errors."""
        errors_to_test = [
            litellm.RateLimitError("Rate limit", "openai", "gpt-4"),
            litellm.InternalServerError("Internal error", "openai", "gpt-4"),
            litellm.ServiceUnavailableError("Service unavailable", "openai", "gpt-4"),
            litellm.APIConnectionError("Connection error", "openai", "gpt-4"),
            litellm.Timeout("Timeout", "openai", "gpt-4"),
        ]

        for error in errors_to_test:
            call_count = 0

            @retry_on_overload(max_retries=2, base_delay=0.01)
            def test_function():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise error
                return "success"

            result = test_function()
            assert result == "success"
            assert call_count == 2

    def test_decorator_max_retries_exceeded(self):
        """Test that max retries are respected."""
        call_count = 0

        @retry_on_overload(max_retries=2, base_delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            raise VendorAPIRateLimitError("Always fails")

        with pytest.raises(VendorAPIRateLimitError):
            test_function()

        assert call_count == 2

    def test_decorator_exponential_backoff(self):
        """Test that exponential backoff delays are applied."""
        call_count = 0
        start_time = time.time()

        @retry_on_overload(max_retries=3, base_delay=0.1)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise VendorAPIRateLimitError("Rate limited")
            return "success"

        result = test_function()
        end_time = time.time()

        # Should have delays of 0.1 + 0.2 = 0.3 seconds minimum
        assert end_time - start_time >= 0.25  # Account for timing variations
        assert result == "success"
        assert call_count == 3

    def test_decorator_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        call_count = 0

        @retry_on_overload(max_retries=3, base_delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable error")

        with pytest.raises(ValueError):
            test_function()

        assert call_count == 1

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves original function metadata."""

        @retry_on_overload()
        def test_function():
            """Original docstring."""
            return "test"

        assert test_function.__name__ == "test_function"
        assert "Original docstring" in test_function.__doc__


class TestMakeCompletionRequest:
    """Test the _make_completion_request function."""

    @patch("playbooks.utils.llm_helper.completion")
    def test_make_completion_request_success(self, mock_completion):
        """Test successful completion request."""
        mock_response = {"choices": [{"message": {"content": "Test response"}}]}
        mock_completion.return_value = mock_response

        completion_kwargs = {"model": "gpt-4", "messages": []}
        result = _make_completion_request(completion_kwargs)

        assert result == "Test response"
        mock_completion.assert_called_once_with(**completion_kwargs)

    @patch("playbooks.utils.llm_helper.completion")
    def test_make_completion_request_retry_on_error(self, mock_completion):
        """Test that _make_completion_request retries on errors."""
        # First call fails, second succeeds
        mock_completion.side_effect = [
            VendorAPIRateLimitError("Rate limited"),
            {"choices": [{"message": {"content": "Success after retry"}}]},
        ]

        completion_kwargs = {"model": "gpt-4", "messages": []}
        result = _make_completion_request(completion_kwargs)

        assert result == "Success after retry"
        assert mock_completion.call_count == 2


class TestMakeCompletionRequestStream:
    """Test the _make_completion_request_stream function."""

    def test_make_completion_request_stream_success(self):
        """Test successful streaming completion request."""
        # Mock chunks with the expected structure
        mock_chunks = [
            Mock(choices=[Mock(delta=Mock(content="Hello"))]),
            Mock(choices=[Mock(delta=Mock(content=" world"))]),
            Mock(choices=[Mock(delta=Mock(content="!"))]),
        ]

        with patch("playbooks.utils.llm_helper.completion") as mock_completion:
            mock_completion.return_value = iter(mock_chunks)

            completion_kwargs = {"model": "gpt-4", "messages": [], "stream": True}
            result = list(_make_completion_request_stream(completion_kwargs))

            assert result == ["Hello", " world", "!"]
            mock_completion.assert_called_once_with(**completion_kwargs)

    def test_make_completion_request_stream_empty_response(self):
        """Test streaming with empty response."""
        with patch("playbooks.utils.llm_helper.completion") as mock_completion:
            mock_completion.return_value = iter([])  # Empty iterator

            completion_kwargs = {"model": "gpt-4", "messages": [], "stream": True}
            result = list(_make_completion_request_stream(completion_kwargs))

            assert result == []

    def test_make_completion_request_stream_with_none_content(self):
        """Test streaming with some None content chunks."""
        mock_chunks = [
            Mock(choices=[Mock(delta=Mock(content="Hello"))]),
            Mock(
                choices=[Mock(delta=Mock(content=None))]
            ),  # None content should be skipped
            Mock(choices=[Mock(delta=Mock(content=" world"))]),
        ]

        with patch("playbooks.utils.llm_helper.completion") as mock_completion:
            mock_completion.return_value = iter(mock_chunks)

            completion_kwargs = {"model": "gpt-4", "messages": [], "stream": True}
            result = list(_make_completion_request_stream(completion_kwargs))

            assert result == ["Hello", " world"]

    def test_make_completion_request_stream_retry_on_error(self):
        """Test that streaming retries on initial connection errors."""
        call_count = 0

        def mock_completion_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise VendorAPIRateLimitError("Rate limited")

            # Second call succeeds
            mock_chunks = [Mock(choices=[Mock(delta=Mock(content="Success"))])]
            return iter(mock_chunks)

        with patch(
            "playbooks.utils.llm_helper.completion",
            side_effect=mock_completion_side_effect,
        ):
            with patch("time.sleep"):  # Mock sleep to speed up test
                completion_kwargs = {"model": "gpt-4", "messages": [], "stream": True}
                result = list(_make_completion_request_stream(completion_kwargs))

                assert result == ["Success"]
                assert call_count == 2

    def test_make_completion_request_stream_max_retries_exceeded(self):
        """Test that streaming respects max retries."""
        with patch("playbooks.utils.llm_helper.completion") as mock_completion:
            mock_completion.side_effect = VendorAPIRateLimitError("Always fails")

            with patch("time.sleep"):  # Mock sleep to speed up test
                completion_kwargs = {"model": "gpt-4", "messages": [], "stream": True}

                with pytest.raises(VendorAPIRateLimitError):
                    list(_make_completion_request_stream(completion_kwargs))


class TestRemoveEmptyMessages:
    """Test the remove_empty_messages function."""

    def test_remove_empty_messages_basic(self):
        """Test removing messages with empty content."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "user", "content": ""},
            {"role": "user", "content": "   "},  # Whitespace only
            {"role": "user", "content": "World"},
        ]

        result = remove_empty_messages(messages)

        assert len(result) == 2
        assert result[0]["content"] == "Hello"
        assert result[1]["content"] == "World"

    def test_remove_empty_messages_all_empty(self):
        """Test removing all messages when all are empty."""
        messages = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "   "},
            {"role": "user", "content": "\t\n"},
        ]

        result = remove_empty_messages(messages)

        assert len(result) == 0

    def test_remove_empty_messages_none_empty(self):
        """Test when no messages are empty."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]

        result = remove_empty_messages(messages)

        assert len(result) == 3
        assert result == messages

    def test_remove_empty_messages_empty_list(self):
        """Test with empty message list."""
        messages = []

        result = remove_empty_messages(messages)

        assert result == []


class TestGetMessagesForPrompt:
    """Test the get_messages_for_prompt function."""

    def test_get_messages_for_prompt_with_delimiter(self):
        """Test prompt with system/user delimiter."""
        from playbooks.constants import SYSTEM_PROMPT_DELIMITER

        prompt = f"System instructions here{SYSTEM_PROMPT_DELIMITER}User message here"

        result = get_messages_for_prompt(prompt)

        assert len(result) == 2
        assert result[0]["role"] == LLMMessageRole.SYSTEM
        assert result[0]["content"] == "System instructions here"
        assert "cache_control" in result[0]  # System message should be cached

        assert result[1]["role"] == LLMMessageRole.USER
        assert result[1]["content"] == "User message here"
        assert "cache_control" not in result[1]  # User message should not be cached

    def test_get_messages_for_prompt_without_delimiter(self):
        """Test prompt without system/user delimiter."""
        prompt = "Just a user message"

        result = get_messages_for_prompt(prompt)

        assert len(result) == 1
        assert result[0]["role"] == LLMMessageRole.USER
        assert result[0]["content"] == "Just a user message"
        assert "cache_control" not in result[0]

    def test_get_messages_for_prompt_with_whitespace(self):
        """Test prompt with whitespace around delimiter."""
        from playbooks.constants import SYSTEM_PROMPT_DELIMITER

        prompt = f"  System with spaces  {SYSTEM_PROMPT_DELIMITER}  User with spaces  "

        result = get_messages_for_prompt(prompt)

        assert len(result) == 2
        assert result[0]["content"] == "System with spaces"
        assert result[1]["content"] == "User with spaces"


class TestGetCompletionIntegration:
    """Integration tests for get_completion function."""

    def test_get_completion_basic_flow(self):
        """Test basic get_completion flow without caching."""
        llm_config = LLMConfig(model="gpt-4", api_key="test-key")
        messages = [{"role": "user", "content": "Hello"}]

        with patch(
            "playbooks.utils.llm_helper._make_completion_request"
        ) as mock_request:
            mock_request.return_value = "Hello! How can I help you?"

            # Disable caching for this test
            with patch("playbooks.utils.llm_helper.llm_cache_enabled", False):
                result = list(get_completion(llm_config, messages, stream=False))

                assert len(result) == 1
                assert result[0] == "Hello! How can I help you?"

    def test_get_completion_streaming_flow(self):
        """Test streaming get_completion flow."""
        llm_config = LLMConfig(model="gpt-4", api_key="test-key")
        messages = [{"role": "user", "content": "Hello"}]

        def mock_stream():
            yield "Hello"
            yield " there"
            yield "!"

        with patch(
            "playbooks.utils.llm_helper._make_completion_request_stream"
        ) as mock_stream_request:
            mock_stream_request.return_value = mock_stream()

            with patch("playbooks.utils.llm_helper.llm_cache_enabled", False):
                result = list(get_completion(llm_config, messages, stream=True))

                assert result == ["Hello", " there", "!"]

    def test_get_completion_with_json_mode(self):
        """Test get_completion with JSON mode enabled."""
        llm_config = LLMConfig(model="gpt-4", api_key="test-key")
        messages = [{"role": "user", "content": "Return JSON"}]

        with patch(
            "playbooks.utils.llm_helper._make_completion_request"
        ) as mock_request:
            with patch(
                "playbooks.utils.llm_helper.get_supported_openai_params"
            ) as mock_params:
                mock_params.return_value = ["response_format"]
                mock_request.return_value = '{"result": "success"}'

                with patch("playbooks.utils.llm_helper.llm_cache_enabled", False):
                    result = list(get_completion(llm_config, messages, json_mode=True))

                    assert len(result) == 1
                    assert result[0] == '{"result": "success"}'

                    # Verify that response_format was added to completion_kwargs
                    call_args = mock_request.call_args[0][0]
                    assert "response_format" in call_args
                    assert call_args["response_format"] == {"type": "json_object"}

    @patch.dict(os.environ, {"LLM_CACHE_ENABLED": "true", "LLM_CACHE_TYPE": "disk"})
    def test_get_completion_with_caching_hit(self):
        """Test get_completion with cache hit."""
        llm_config = LLMConfig(model="gpt-4", api_key="test-key")
        messages = [{"role": "user", "content": "Hello"}]
        cached_response = "Cached response"

        # Mock the cache
        mock_cache = Mock()
        mock_cache.get.return_value = cached_response

        with patch("playbooks.utils.llm_helper.cache", mock_cache):
            with patch("playbooks.utils.llm_helper.llm_cache_enabled", True):
                result = list(get_completion(llm_config, messages, use_cache=True))

                assert len(result) == 1
                assert result[0] == cached_response
                mock_cache.get.assert_called_once()

    @patch.dict(os.environ, {"LLM_CACHE_ENABLED": "true", "LLM_CACHE_TYPE": "disk"})
    def test_get_completion_with_caching_miss(self):
        """Test get_completion with cache miss."""
        llm_config = LLMConfig(model="gpt-4", api_key="test-key")
        messages = [{"role": "user", "content": "Hello"}]
        llm_response = "LLM response"

        # Mock the cache (miss, then set)
        mock_cache = Mock()
        mock_cache.get.return_value = None

        with patch("playbooks.utils.llm_helper.cache", mock_cache):
            with patch("playbooks.utils.llm_helper.llm_cache_enabled", True):
                with patch(
                    "playbooks.utils.llm_helper._make_completion_request"
                ) as mock_request:
                    mock_request.return_value = llm_response

                    result = list(get_completion(llm_config, messages, use_cache=True))

                    assert len(result) == 1
                    assert result[0] == llm_response
                    mock_cache.get.assert_called_once()
                    mock_cache.set.assert_called_once()

    def test_get_completion_error_handling(self):
        """Test get_completion error handling and propagation."""
        llm_config = LLMConfig(model="gpt-4", api_key="test-key")
        messages = [{"role": "user", "content": "Hello"}]

        with patch(
            "playbooks.utils.llm_helper._make_completion_request"
        ) as mock_request:
            mock_request.side_effect = VendorAPIRateLimitError("Rate limited")

            with patch("playbooks.utils.llm_helper.llm_cache_enabled", False):
                with pytest.raises(VendorAPIRateLimitError):
                    list(get_completion(llm_config, messages))

    def test_get_completion_message_preprocessing(self):
        """Test that get_completion properly preprocesses messages."""
        llm_config = LLMConfig(model="gpt-4", api_key="test-key")
        messages = [
            {"role": "user", "content": ""},  # Empty message should be removed
            {"role": "user", "content": "Hello"},
            {"role": "user", "content": "World"},  # Should be consolidated
        ]

        with patch(
            "playbooks.utils.llm_helper._make_completion_request"
        ) as mock_request:
            mock_request.return_value = "Response"

            with patch("playbooks.utils.llm_helper.llm_cache_enabled", False):
                _ = list(get_completion(llm_config, messages))

                # Check that the messages were preprocessed
                call_args = mock_request.call_args[0][0]
                processed_messages = call_args["messages"]

                # Should have only one message after consolidation and empty removal
                assert len(processed_messages) == 1
                assert processed_messages[0]["content"] == "Hello\n\nWorld"
