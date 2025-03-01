"""Tests for the PlaybookExecution class."""

from unittest.mock import MagicMock, patch

import pytest

from playbooks.call_stack import InstructionPointer
from playbooks.interpreter import PlaybookExecution


@pytest.fixture
def mock_interpreter():
    """Create a mock interpreter for testing."""
    interpreter = MagicMock()
    # Set up call stack peek to return a frame with an instruction pointer
    frame = MagicMock()
    frame.instruction_pointer = InstructionPointer(
        playbook="TestPlaybook", line_number="01"
    )
    interpreter.call_stack.peek.return_value = frame
    return interpreter


@pytest.fixture
def mock_playbooks():
    """Create mock playbooks for testing."""
    playbook = MagicMock()
    playbook.klass = "TestPlaybook"
    return {"TestPlaybook": playbook}


@pytest.fixture
def mock_current_playbook():
    """Create a mock current playbook for testing."""
    playbook = MagicMock()
    playbook.klass = "TestPlaybook"
    return playbook


class TestPlaybookExecution:
    """Tests for the PlaybookExecution class."""

    def test_initialization(
        self, mock_interpreter, mock_playbooks, mock_current_playbook
    ):
        """Test that the PlaybookExecution class initializes correctly."""
        instruction = "Test instruction"
        llm_config = {"model": "test-model"}
        stream = True

        playbook_execution = PlaybookExecution(
            interpreter=mock_interpreter,
            playbooks=mock_playbooks,
            current_playbook=mock_current_playbook,
            instruction=instruction,
            llm_config=llm_config,
            stream=stream,
        )

        assert playbook_execution.interpreter == mock_interpreter
        assert playbook_execution.playbooks == mock_playbooks
        assert playbook_execution.current_playbook == mock_current_playbook
        assert playbook_execution.instruction == instruction
        assert playbook_execution.llm_config == llm_config
        assert playbook_execution.stream == stream
        assert playbook_execution.wait_for_external_event is False
        assert hasattr(playbook_execution, "_trace_items")

    @patch("playbooks.interpreter.interpreter_execution.InterpreterExecution")
    def test_execute(
        self,
        mock_interpreter_execution_class,
        mock_interpreter,
        mock_playbooks,
        mock_current_playbook,
    ):
        """Test that the execute method works correctly."""
        # Set up the mock interpreter execution
        mock_interpreter_execution = MagicMock()
        mock_interpreter_execution.execute.return_value = []
        mock_interpreter_execution.wait_for_external_event = True
        mock_interpreter_execution_class.return_value = mock_interpreter_execution

        # Create the playbook execution
        playbook_execution = PlaybookExecution(
            interpreter=mock_interpreter,
            playbooks=mock_playbooks,
            current_playbook=mock_current_playbook,
            instruction="Test instruction",
        )

        # Execute the playbook
        list(playbook_execution.execute())

        # Check that the interpreter execution was created with the correct arguments
        mock_interpreter_execution_class.assert_called_once_with(
            interpreter=mock_interpreter,
            playbooks=mock_playbooks,
            current_playbook=mock_current_playbook,
            instruction="Test instruction",
            llm_config=None,
            stream=False,
        )

        # Check that the interpreter execution's execute method was called
        mock_interpreter_execution.execute.assert_called_once()

        # Check that the wait_for_external_event flag was set correctly
        assert playbook_execution.wait_for_external_event is True

    def test_repr(self, mock_interpreter, mock_playbooks, mock_current_playbook):
        """Test that the __repr__ method returns the expected string."""
        playbook_execution = PlaybookExecution(
            interpreter=mock_interpreter,
            playbooks=mock_playbooks,
            current_playbook=mock_current_playbook,
            instruction="Test instruction",
        )

        assert repr(playbook_execution) == "TestPlaybook()"
