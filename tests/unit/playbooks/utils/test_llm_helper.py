"""Tests for the llm_helper module."""

from unittest.mock import patch

import pytest

from playbooks.config import LLMConfig
from playbooks.utils.llm_helper import get_completion


class TestLLMHelper:
    """Tests for the llm_helper module."""

    @pytest.fixture
    def llm_config(self):
        """Create a test LLM config."""
        return LLMConfig(model="test-model")

    @pytest.fixture
    def messages(self):
        """Create test messages."""
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ]

    @patch("playbooks.utils.llm_helper._make_completion_request")
    def test_get_completion_json_mode_openai(
        self, mock_make_request, llm_config, messages
    ):
        """Test that json_mode is correctly handled for OpenAI models."""
        # Set up the OpenAI model
        llm_config.model = "gpt-4o"

        # Set up the mock to return a string directly
        mock_make_request.return_value = '{"result": "JSON response"}'

        # Call get_completion with json_mode=True and use_cache=False to avoid pickling issues
        result = list(
            get_completion(
                llm_config, messages, json_mode=True, use_cache=False, stream=False
            )
        )

        # Verify the result
        assert result == ['{"result": "JSON response"}']

        # Verify request was made with response_format
        mock_make_request.assert_called_once()
        call_args = mock_make_request.call_args[0][0]
        assert call_args["response_format"] == {"type": "json_object"}

    @patch("playbooks.utils.llm_helper._make_completion_request")
    def test_get_completion_json_mode_other_models(
        self, mock_make_request, llm_config, messages
    ):
        """Test that json_mode is correctly handled for other models."""
        # Set up a non-OpenAI, non-Claude model
        llm_config.model = "gemini-pro"

        # Set up the mock to return a string directly
        mock_make_request.return_value = '{"result": "JSON response"}'

        # Call get_completion with json_mode=True and use_cache=False to avoid pickling issues
        result = list(
            get_completion(
                llm_config, messages, json_mode=True, use_cache=False, stream=False
            )
        )

        # Verify the result
        assert result == ['{"result": "JSON response"}']

        # Verify completion was called with the correct parameters
        mock_make_request.assert_called_once()
        call_args = mock_make_request.call_args[0][0]

        # For non-OpenAI models, we don't expect any special handling
        # Just verify that the model and messages are correct
        assert call_args["model"] == "gemini-pro"
        assert len(call_args["messages"]) == 2
