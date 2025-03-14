"""Tests for the ToolExecution and ToolExecutionResult classes."""

from unittest.mock import MagicMock

import pytest

from playbooks.enums import PlaybookExecutionType
from playbooks.interpreter import ToolExecution, ToolExecutionResult
from playbooks.types import ToolCall


@pytest.fixture
def tool_call():
    """Create a mock tool call for testing."""
    return ToolCall(fn="TestTool", args=["arg1", "arg2"], kwargs={"key": "value"})


@pytest.fixture
def mock_interpreter():
    """Create a mock interpreter for testing."""
    return MagicMock()


@pytest.fixture
def mock_playbooks():
    """Create mock playbooks for testing."""
    ext_playbook = MagicMock()
    ext_playbook.execution_type = PlaybookExecutionType.EXT
    ext_playbook.klass = "TestTool"
    ext_playbook.func = MagicMock(return_value="Tool result")

    return {"TestTool": ext_playbook}


class TestToolExecutionResult:
    """Tests for the ToolExecutionResult class."""

    def test_initialization(self, tool_call):
        """Test that the ToolExecutionResult class initializes correctly."""
        message = "Tool execution result"
        result = ToolExecutionResult(message, tool_call)

        assert result.message == message
        assert result.tool_call == tool_call
        assert "tool_call" in result._trace_metadata
        assert result._trace_metadata["tool_call"] == tool_call

    def test_repr(self, tool_call):
        """Test that the __repr__ method returns the expected string."""
        message = "Tool execution result"
        result = ToolExecutionResult(message, tool_call)

        expected_repr = f"{tool_call}: {message}"
        assert repr(result) == expected_repr


class TestToolExecution:
    """Tests for the ToolExecution class."""

    def test_initialization(self, mock_interpreter, mock_playbooks, tool_call):
        """Test that the ToolExecution class initializes correctly."""
        tool_execution = ToolExecution(mock_interpreter, mock_playbooks, tool_call)

        assert tool_execution.interpreter == mock_interpreter
        assert tool_execution.playbooks == mock_playbooks
        assert tool_execution.tool_call == tool_call
        assert hasattr(tool_execution, "_trace_items")

    def test_execute_success(self, mock_interpreter, mock_playbooks, tool_call):
        """Test that the execute method works correctly when the tool is found."""
        tool_execution = ToolExecution(mock_interpreter, mock_playbooks, tool_call)

        # Execute the tool
        result = list(tool_execution.execute())

        # Check that the tool was called with the correct arguments
        mock_playbooks["TestTool"].func.assert_called_once_with(
            "arg1", "arg2", key="value"
        )

        # Check that the result is correct
        assert len(result) == 1
        assert result[0].tool_call == tool_call
        assert tool_call.retval == "Tool result"

    def test_execute_tool_not_found(self, mock_interpreter, tool_call):
        """Test that the execute method raises an exception when the tool is not found."""
        # Create empty playbooks dictionary
        empty_playbooks = {}
        tool_execution = ToolExecution(mock_interpreter, empty_playbooks, tool_call)

        # Execute the tool and expect an exception
        with pytest.raises(Exception) as excinfo:
            list(tool_execution.execute())

        assert "EXT playbook TestTool not found" in str(excinfo.value)

    def test_repr(self, mock_interpreter, mock_playbooks, tool_call):
        """Test that the __repr__ method returns the expected string."""
        tool_execution = ToolExecution(mock_interpreter, mock_playbooks, tool_call)

        assert repr(tool_execution) == repr(tool_call)
