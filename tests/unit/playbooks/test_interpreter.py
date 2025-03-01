from unittest.mock import MagicMock, mock_open, patch

import pytest

from playbooks.interpreter import Interpreter


@pytest.fixture
def interpreter():
    return Interpreter()


@pytest.fixture
def mock_playbook():
    """Create a mock playbook for testing."""
    playbook = MagicMock()
    playbook.execution_type = "function"
    playbook.klass = "TestClass"
    playbook.signature = "test_function()"
    playbook.description = "Test function description"
    playbook.trigger = {
        "children": [
            {"markdown": "When the user asks for help"},
            {"markdown": "When the user mentions test"},
        ]
    }
    return playbook


def test_interpreter_initialization(interpreter):
    """Test that the interpreter initializes correctly."""
    assert isinstance(interpreter, Interpreter)
    assert hasattr(interpreter, "_trace_items")
    assert hasattr(interpreter, "call_stack")


@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="{{PLAYBOOKS_SIGNATURES}}\n{{CURRENT_PLAYBOOK_MARKDOWN}}\n{{INSTRUCTION}}\n{{INITIAL_STATE}}\n{{SESSION_CONTEXT}}",
)
def test_interpreter_get_prompt(mock_file, interpreter, mock_playbook):
    """Test that the get_prompt method returns the expected prompt."""
    # Create a dictionary of playbooks with the key matching the playbook's klass
    playbooks = {mock_playbook.klass: mock_playbook}

    # Add markdown attribute to the mock playbook
    mock_playbook.markdown = "Test playbook markdown"

    # Get the prompt
    prompt = interpreter.get_prompt(playbooks, mock_playbook, "test instruction")

    # Check that the prompt contains the expected content
    assert "test instruction" in prompt
    assert mock_playbook.signature in prompt
    assert mock_playbook.description in prompt
    assert "When the user asks for help" in prompt
    assert "When the user mentions test" in prompt
    assert "Test playbook markdown" in prompt
