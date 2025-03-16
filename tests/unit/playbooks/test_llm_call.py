from unittest.mock import patch

import pytest

from playbooks.config import LLMConfig
from playbooks.llm_call import LLMCall


class TestLLMCall:
    @pytest.fixture
    def llm_config(self):
        return LLMConfig(model="test-model")

    @pytest.fixture
    def messages(self):
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ]

    def test_initialization(self, llm_config, messages):
        llm_call = LLMCall(llm_config, messages, stream=True, json_mode=True)

        assert llm_call.llm_config == llm_config
        assert llm_call.messages == messages
        assert llm_call.stream is True
        assert llm_call.json_mode is True

    def test_repr(self, llm_config, messages):
        llm_call = LLMCall(llm_config, messages, stream=True, json_mode=False)

        assert repr(llm_call) == "LLMCall(test-model)"

    @patch("playbooks.llm_call.get_completion")
    @patch("playbooks.llm_call.time.time")
    @patch("playbooks.llm_call.token_counter")
    def test_execute_streaming(
        self, mock_token_counter, mock_time, mock_get_completion, llm_config, messages
    ):
        # Setup mocks
        mock_time.side_effect = [100.0, 100.5, 101.0]  # start, first token, end times
        mock_get_completion.return_value = ["Hello", " world"]
        mock_token_counter.side_effect = [10, 2]  # input tokens, output tokens

        # Create LLMCall
        llm_call = LLMCall(llm_config, messages, stream=True, json_mode=True)

        # Execute and collect results
        result = list(llm_call.execute())

        # Verify results
        assert result == ["Hello", " world"]

        # Verify get_completion was called correctly
        mock_get_completion.assert_called_once_with(
            llm_config=llm_config, messages=messages, stream=True, json_mode=True
        )

        # Verify token_counter was called correctly
        assert mock_token_counter.call_count == 2
        mock_token_counter.assert_any_call(model="test-model", messages=messages)
        mock_token_counter.assert_any_call(
            model="test-model", messages=[{"content": "Hello world"}]
        )

        # Verify trace was called with correct metadata
        assert len(llm_call._trace_items) == 1
        assert llm_call._trace_items[0].message == "Success"
        metadata = llm_call._trace_items[0]._trace_metadata
        assert metadata["llm_config"] == llm_config.to_dict()
        assert metadata["messages"] == messages
        assert metadata["stream"] is True
        assert metadata["time_to_first_token_ms"] == 500.0  # (100.5 - 100.0) * 1000
        assert metadata["response"] == "Hello world"
        assert metadata["total_time_ms"] == 1000.0  # (101.0 - 100.0) * 1000
        assert metadata["input_tokens"] == 10
        assert metadata["output_tokens"] == 2

    @patch("playbooks.llm_call.get_completion")
    @patch("playbooks.llm_call.time.time")
    @patch("playbooks.llm_call.token_counter")
    def test_execute_non_streaming(
        self, mock_token_counter, mock_time, mock_get_completion, llm_config, messages
    ):
        # Setup mocks
        mock_time.side_effect = [100.0, 100.5, 101.0]  # start, first token, end times
        mock_get_completion.return_value = ["Complete response"]
        mock_token_counter.side_effect = [10, 2]  # input tokens, output tokens

        # Create LLMCall
        llm_call = LLMCall(llm_config, messages, stream=False, json_mode=False)

        # Execute and collect results
        result = list(llm_call.execute())

        # Verify results
        assert result == ["Complete response"]

        # Verify get_completion was called correctly
        mock_get_completion.assert_called_once_with(
            llm_config=llm_config, messages=messages, stream=False, json_mode=False
        )

    @patch("playbooks.llm_call.get_completion")
    @patch("playbooks.llm_call.time.time")
    @patch("playbooks.llm_call.token_counter")
    def test_execute_no_response(
        self, mock_token_counter, mock_time, mock_get_completion, llm_config, messages
    ):
        # Setup mocks
        mock_time.side_effect = [100.0, 101.0]  # start, end times (no first token time)
        mock_get_completion.return_value = []
        mock_token_counter.side_effect = [10, 0]  # input tokens, output tokens

        # Create LLMCall
        llm_call = LLMCall(llm_config, messages, stream=True, json_mode=True)

        # Execute and collect results
        result = list(llm_call.execute())

        # Verify results
        assert result == []

        # Verify trace was called with correct metadata
        assert len(llm_call._trace_items) == 1
        metadata = llm_call._trace_items[0]._trace_metadata
        assert metadata["time_to_first_token_ms"] is None  # No first token
        assert metadata["response"] == ""
        assert metadata["total_time_ms"] == 1000.0  # (101.0 - 100.0) * 1000

    @patch("playbooks.llm_call.get_completion")
    @patch("playbooks.llm_call.time.time")
    @patch("playbooks.llm_call.token_counter")
    def test_execute_with_json_mode(
        self, mock_token_counter, mock_time, mock_get_completion, llm_config, messages
    ):
        """Test that json_mode is correctly passed to get_completion."""
        # Setup mocks
        mock_time.side_effect = [100.0, 100.5, 101.0]
        mock_get_completion.return_value = ['{"result": "JSON response"}']
        mock_token_counter.side_effect = [10, 2]

        # Create LLMCall with json_mode=True
        llm_call = LLMCall(llm_config, messages, stream=False, json_mode=True)

        # Execute and collect results
        result = list(llm_call.execute())

        # Verify results
        assert result == ['{"result": "JSON response"}']

        # Verify get_completion was called with json_mode=True
        mock_get_completion.assert_called_once_with(
            llm_config=llm_config, messages=messages, stream=False, json_mode=True
        )
