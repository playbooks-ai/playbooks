"""Tests for the InterpreterExecution class."""

from unittest.mock import MagicMock, patch

import pytest

from playbooks.interpreter import InterpreterExecution
from playbooks.types import ToolCall


@pytest.fixture
def mock_interpreter():
    """Create a mock interpreter for testing."""
    interpreter = MagicMock()
    interpreter.session_context.return_value = "Session context"
    interpreter.get_prompt.return_value = "Test prompt"
    return interpreter


@pytest.fixture
def mock_playbooks():
    """Create mock playbooks for testing."""
    playbook = MagicMock()
    playbook.klass = "TestPlaybook"
    return {"TestPlaybook": playbook, "Say": playbook}


@pytest.fixture
def mock_current_playbook():
    """Create a mock current playbook for testing."""
    playbook = MagicMock()
    playbook.klass = "TestPlaybook"
    return playbook


class TestInterpreterExecution:
    """Tests for the InterpreterExecution class."""

    def test_initialization(
        self, mock_interpreter, mock_playbooks, mock_current_playbook
    ):
        """Test that the InterpreterExecution class initializes correctly."""
        instruction = "Test instruction"
        llm_config = {"model": "test-model"}
        stream = True

        interpreter_execution = InterpreterExecution(
            interpreter=mock_interpreter,
            playbooks=mock_playbooks,
            current_playbook=mock_current_playbook,
            instruction=instruction,
            llm_config=llm_config,
            stream=stream,
        )

        assert interpreter_execution.interpreter == mock_interpreter
        assert interpreter_execution.playbooks == mock_playbooks
        assert interpreter_execution.current_playbook == mock_current_playbook
        assert interpreter_execution.instruction == instruction
        assert interpreter_execution.llm_config == llm_config
        assert interpreter_execution.stream == stream
        assert interpreter_execution.wait_for_external_event is False
        assert hasattr(interpreter_execution, "_trace_items")

    def test_parse_response_yaml_block(self):
        """Test parsing a response with a YAML block."""
        interpreter_execution = InterpreterExecution(
            interpreter=MagicMock(),
            playbooks={"Say": MagicMock()},
            current_playbook=MagicMock(),
            instruction="Test instruction",
        )

        response = """
Here's the execution:

```yaml
- TestPlaybook:01:CMD:
    - call:
        fn: Say
        args: []
        kwargs:
          message: Hello, world!
    - updated_vars:
        $greeting: Hello, world!
```
"""

        (
            tool_calls,
            last_executed_step,
            updated_variables,
        ) = interpreter_execution.parse_response(response)

        assert len(tool_calls) == 1
        assert tool_calls[0].fn == "Say"
        assert tool_calls[0].args == []
        assert tool_calls[0].kwargs == {"message": "Hello, world!"}
        assert last_executed_step == "TestPlaybook:01:CMD"
        assert updated_variables == {"$greeting": "Hello, world!"}

    def test_parse_response_direct_yaml(self):
        """Test parsing a response with direct YAML content."""
        interpreter_execution = InterpreterExecution(
            interpreter=MagicMock(),
            playbooks={"Say": MagicMock()},
            current_playbook=MagicMock(),
            instruction="Test instruction",
        )

        response = """
- TestPlaybook:01:CMD:
    - call:
        fn: Say
        args: []
        kwargs:
          message: Hello, world!
    - updated_vars:
        $greeting: Hello, world!
"""

        (
            tool_calls,
            last_executed_step,
            updated_variables,
        ) = interpreter_execution.parse_response(response)

        assert len(tool_calls) == 1
        assert tool_calls[0].fn == "Say"
        assert tool_calls[0].args == []
        assert tool_calls[0].kwargs == {"message": "Hello, world!"}
        assert last_executed_step == "TestPlaybook:01:CMD"
        assert updated_variables == {"$greeting": "Hello, world!"}

    def test_parse_response_invalid_yaml(self):
        """Test parsing a response with invalid YAML content."""
        interpreter_execution = InterpreterExecution(
            interpreter=MagicMock(),
            playbooks={},
            current_playbook=MagicMock(),
            instruction="Test instruction",
        )

        response = "This is not valid YAML content."

        with pytest.raises(ValueError) as excinfo:
            interpreter_execution.parse_response(response)

        # The error message could be either "Empty YAML content" or "Invalid YAML content"
        assert "YAML content" in str(excinfo.value)

    @patch("playbooks.interpreter.interpreter_execution.get_messages_for_prompt")
    @patch("playbooks.interpreter.interpreter_execution.LLMCall")
    def test_execute(
        self,
        mock_llm_call_class,
        mock_get_messages,
        mock_interpreter,
        mock_playbooks,
        mock_current_playbook,
    ):
        """Test that the execute method works correctly."""
        # Set up the mocks
        mock_get_messages.return_value = ["Test message"]

        mock_llm_call = MagicMock()
        mock_llm_call.execute.return_value = ["Test response"]
        mock_llm_call_class.return_value = mock_llm_call

        # Mock the parse_response method
        with patch.object(
            InterpreterExecution, "parse_response"
        ) as mock_parse_response:
            mock_parse_response.return_value = (
                [
                    ToolCall(
                        fn="Say",
                        args=[],
                        kwargs={"message": "Hello", "waitForUserInput": True},
                    )
                ],
                "TestPlaybook:01:CMD",
                {"$greeting": "Hello"},
            )

            # Create the interpreter execution
            interpreter_execution = InterpreterExecution(
                interpreter=mock_interpreter,
                playbooks=mock_playbooks,
                current_playbook=mock_current_playbook,
                instruction="Test instruction",
                llm_config={"model": "test-model"},
                stream=True,
            )

            # Execute the interpreter
            result = list(interpreter_execution.execute())

            # Check that the methods were called with the correct arguments
            mock_interpreter.get_prompt.assert_called_once()
            mock_get_messages.assert_called_once_with("Test prompt")
            mock_llm_call_class.assert_called_once_with(
                llm_config={"model": "test-model"},
                messages=["Test message"],
                stream=True,
            )
            mock_llm_call.execute.assert_called_once()
            mock_parse_response.assert_called_once_with("Test response\n")

            # Check that the wait_for_external_event flag was set correctly
            assert interpreter_execution.wait_for_external_event is True

            # Check that the result contains the expected chunks
            assert len(result) == 3  # raw chunk, newline, tool call
            assert result[0].raw == "Test response"
            assert result[1].raw == "\n"
            assert result[2].tool_call.fn == "Say"
            assert result[2].tool_call.kwargs == {
                "message": "Hello",
                "waitForUserInput": True,
            }

    def test_repr(self):
        """Test that the __repr__ method returns the expected string."""
        interpreter_execution = InterpreterExecution(
            interpreter=MagicMock(),
            playbooks={},
            current_playbook=MagicMock(),
            instruction="Test instruction",
        )

        # Add some trace items
        interpreter_execution.trace(
            "Start iteration",
            metadata={
                "playbook": "TestPlaybook",
                "line_number": "01",
                "instruction": "Test",
            },
        )
        interpreter_execution.trace(
            "Start iteration",
            metadata={
                "playbook": "TestPlaybook",
                "line_number": "02",
                "instruction": "Test",
            },
        )

        assert repr(interpreter_execution) == "01, 02"
