"""Test suite for Playbooks-LM preprocessing handler."""

from unittest.mock import MagicMock, patch

import pytest

from playbooks.utils.llm_helper import completion_with_preprocessing
from playbooks.utils.playbooks_lm_handler import PlaybooksLMHandler


class TestPlaybooksLMHandler:
    """Test the PlaybooksLMHandler preprocessing logic."""

    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return PlaybooksLMHandler()

    def test_invalid_system_prompt_raises_error(self, handler):
        """Test that non-interpreter system prompts raise an error."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]

        with pytest.raises(
            ValueError, match="PlaybooksLM is designed to execute playbooks"
        ):
            handler.preprocess_messages(messages)

    def test_valid_system_prompt_accepted(self, handler):
        """Test that the correct interpreter prompt is accepted."""
        # Create a message with the actual interpreter prompt start
        messages = [
            {
                "role": "system",
                "content": "**Context**\nYou execute *playbooks* (markdown H2) and Python...",
            },
            {"role": "user", "content": "Hello"},
        ]

        processed = handler.preprocess_messages(messages)

        assert processed[0]["role"] == "user"
        assert "You are an interpreter" in processed[0]["content"]
        assert "executes markdown playbooks" in processed[0]["content"]

    def test_consecutive_message_merging(self, handler):
        """Test that consecutive messages from same role are NOT merged (merging disabled)."""
        messages = [
            {
                "role": "system",
                "content": "**Context**\nYou execute *playbooks* (markdown H2)...",
            },
            {"role": "user", "content": "First message"},
            {"role": "user", "content": "Second message"},
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "Final user message"},  # End with user
        ]

        processed = handler.preprocess_messages(messages)

        # Without merging: system becomes user, then 2 user msgs, 1 assistant, 1 user = 5 total
        assert len(processed) == 5
        assert processed[0]["role"] == "user"  # converted system
        assert processed[1]["role"] == "user"  # first message
        assert processed[2]["role"] == "user"  # second message
        assert processed[3]["role"] == "assistant"  # first response
        assert processed[4]["role"] == "user"  # final user message

    def test_alternating_pattern_validation(self, handler):
        """Test that consecutive messages are preserved without merging."""
        messages = [
            {
                "role": "system",
                "content": "**Context**\nYou execute *playbooks* (markdown H2)...",
            },
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {
                "role": "assistant",
                "content": "How can I help?",
            },  # NOT merged with previous
            {"role": "user", "content": "Test"},
        ]

        # Without merging, all messages stay separate
        processed = handler.preprocess_messages(messages)
        # System becomes user, then user, assistant, assistant, user = 5 total
        assert len(processed) == 5
        assert processed[0]["role"] == "user"  # converted system
        assert processed[1]["role"] == "user"
        assert processed[2]["role"] == "assistant"
        assert processed[3]["role"] == "assistant"  # NOT merged
        assert processed[4]["role"] == "user"

    def test_last_message_must_be_user(self, handler):
        """Test that messages ending with assistant raise an error."""
        # Test with assistant ending - should raise error
        messages = [
            {
                "role": "system",
                "content": "**Context**\nYou execute *playbooks* (markdown H2)...",
            },
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        with pytest.raises(ValueError, match="Expected last message to be from user"):
            handler.preprocess_messages(messages)

        # Test with user ending - should work
        messages = [
            {
                "role": "system",
                "content": "**Context**\nYou execute *playbooks* (markdown H2)...",
            },
            {"role": "user", "content": "Hello"},
        ]

        processed = handler.preprocess_messages(messages)
        assert processed[-1]["role"] == "user"

    def test_empty_messages(self, handler):
        """Test handling of empty message list."""
        processed = handler.preprocess_messages([])
        assert processed == []

    def test_multiple_system_messages_raises_error(self, handler):
        """Test that multiple system messages raise an error."""
        messages = [
            {
                "role": "system",
                "content": "**Context**\nYou execute *playbooks* (markdown H2)...",
            },
            {"role": "system", "content": "Second system"},  # Not allowed
            {"role": "assistant", "content": "Response"},
        ]

        with pytest.raises(
            ValueError, match="Only the first message should be 'system'"
        ):
            handler.preprocess_messages(messages)

    def test_first_message_not_system_raises_error(self, handler):
        """Test that first message must be system."""
        messages = [
            {"role": "user", "content": "Starting with user"},  # Should be system
            {"role": "assistant", "content": "Response"},
        ]

        with pytest.raises(ValueError, match="First message must be 'system'"):
            handler.preprocess_messages(messages)

    def test_message_content_preservation(self, handler):
        """Test that non-system message content is preserved."""
        original_content = "This is my original message with special chars: !@#$%"
        messages = [
            {
                "role": "system",
                "content": "**Context**\nYou execute *playbooks* (markdown H2)...",
            },
            {"role": "user", "content": original_content},
            {
                "role": "user",
                "content": "Final user message",
            },  # End with user to avoid error
        ]

        processed = handler.preprocess_messages(messages)

        # Find the user message with original content
        found = False
        for msg in processed:
            if original_content in msg["content"]:
                found = True
                break
        assert found, "Original message content was not preserved"

    def test_valid_pattern_after_preprocessing(self, handler):
        """Test that preprocessing creates valid alternating pattern."""
        # System message gets converted to user, so next can be user or assistant
        messages = [
            {
                "role": "system",
                "content": "**Context**\nYou execute *playbooks* (markdown H2)...",
            },
            {"role": "user", "content": "User message"},
            {"role": "user", "content": "Final user message"},  # End with user
        ]

        processed = handler.preprocess_messages(messages)
        # After preprocessing: user (system + user messages merged)
        assert processed[0]["role"] == "user"  # Converted system
        assert "interpreter" in processed[0]["content"]

    def test_invalid_alternating_pattern_raises_error(self, handler):
        """Test that valid single-user message works correctly."""
        messages = [
            {
                "role": "system",
                "content": "**Context**\nYou execute *playbooks* (markdown H2)...",
            },
            {"role": "user", "content": "Valid message"},
        ]

        # Should not raise an error
        processed = handler.preprocess_messages(messages)
        # Without merging: system becomes user, then user message = 2 total
        assert len(processed) == 2
        assert processed[0]["role"] == "user"  # converted system
        assert processed[1]["role"] == "user"  # user message


class TestCompletionWrapper:
    """Test the completion wrapper function."""

    @patch("playbooks.utils.llm_helper._original_completion")
    def test_playbooks_lm_preprocessing_via_get_completion(self, mock_completion):
        """Test that playbooks-lm models get preprocessing through get_completion."""
        from playbooks.utils.llm_config import LLMConfig
        from playbooks.utils.llm_helper import get_completion

        mock_completion.return_value = MagicMock()

        messages = [
            {
                "role": "system",
                "content": "**Context**\nYou execute *playbooks* (markdown H2)...",
            },
            {"role": "user", "content": "User message"},
        ]

        # Test with playbooks-lm model
        llm_config = LLMConfig(model="ollama/playbooks-lm", api_key="test-key")

        # Call get_completion (which does the preprocessing)
        list(
            get_completion(
                llm_config=llm_config,
                messages=messages,
                use_cache=False,  # Disable cache to ensure actual call
            )
        )

        # Check that messages were preprocessed
        call_args = mock_completion.call_args
        processed_messages = call_args[1]["messages"]

        # First message should be user (system converted)
        assert processed_messages[0]["role"] == "user"
        # Should contain the special prompt
        assert "interpreter" in processed_messages[0]["content"]

    @patch("playbooks.utils.llm_helper._original_completion")
    def test_non_playbooks_models_unchanged(self, mock_completion):
        """Test that non-playbooks-lm models are not preprocessed."""
        mock_completion.return_value = MagicMock()

        original_messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User message"},
        ]

        # Test with non-playbooks models
        test_models = [
            "gpt-4",
            "claude-3",
            "ollama/llama2",
            "custom-model",
        ]

        for model in test_models:
            # Make a copy to avoid mutation
            messages = [m.copy() for m in original_messages]

            completion_with_preprocessing(model=model, messages=messages)

            # Check that messages were NOT preprocessed
            call_args = mock_completion.call_args
            processed_messages = call_args[1]["messages"]

            # Should still have system message
            assert processed_messages[0]["role"] == "system"
            assert processed_messages[0]["content"] == "System prompt"

    @patch("playbooks.utils.llm_helper._original_completion")
    def test_kwargs_passthrough(self, mock_completion):
        """Test that all kwargs are passed through correctly."""
        mock_completion.return_value = MagicMock()

        kwargs = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "test"}],
            "temperature": 0.7,
            "max_tokens": 100,
            "stream": True,
            "custom_param": "value",
        }

        completion_with_preprocessing(**kwargs)

        # Check all kwargs were passed
        call_args = mock_completion.call_args[1]
        assert call_args["temperature"] == 0.7
        assert call_args["max_tokens"] == 100
        assert call_args["stream"] is True
        assert call_args["custom_param"] == "value"

    @patch("playbooks.utils.llm_helper._original_completion")
    def test_explicit_api_base_not_overridden(self, mock_completion):
        """Test that explicitly provided api_base is not overridden."""
        mock_completion.return_value = MagicMock()

        completion_with_preprocessing(
            model="any-model",
            messages=[{"role": "user", "content": "test"}],
            api_base="http://custom-api.com",
        )

        call_args = mock_completion.call_args[1]
        assert call_args["api_base"] == "http://custom-api.com"
