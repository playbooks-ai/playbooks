from unittest.mock import MagicMock, mock_open, patch

import pytest

from playbooks.interpreter import Interpreter
from playbooks.types import AgentResponseChunk, ToolCall


@pytest.fixture
def interpreter():
    return Interpreter()


def test_interpreter_initialization(interpreter):
    assert interpreter.trace == []
    assert interpreter.variables == {}
    assert interpreter.call_stack == []
    assert interpreter.available_external_functions == []
    assert interpreter.yield_requested_on_say is False


def test_parse_response_valid_yaml(interpreter):
    response = """Some text before
```yaml
trace:
  - say: "Hello"
    ext:
      fn: "Say"
      args: ["Hello"]
      kwargs: {}
stack: ["MainPlaybook:01"]
vars:
  greeting: "Hello"
```
Some text after"""

    tool_calls = interpreter.parse_response(response)

    assert len(tool_calls) == 1
    assert isinstance(tool_calls[0], ToolCall)
    assert tool_calls[0].fn == "Say"
    assert tool_calls[0].args == ["Hello"]
    assert tool_calls[0].kwargs == {}
    assert interpreter.call_stack == ["MainPlaybook:01"]
    assert interpreter.variables == {"greeting": "Hello"}


def test_parse_response_invalid_yaml(interpreter):
    response = """Some text without any YAML block
Just some random text that doesn't contain ```yaml
or any valid YAML content"""

    with pytest.raises(ValueError, match="Empty YAML content"):
        interpreter.parse_response(response)


@patch("playbooks.interpreter.get_completion")
def test_run_with_external_functions(mock_get_completion, interpreter):
    # Mock playbooks
    playbook = MagicMock()
    playbook.execution_type = "EXT"
    playbook.signature = "TestFunc"
    playbook.description = "Test function"
    playbook.markdown = "Test playbook markdown"

    # Mock LLM response
    mock_get_completion.return_value = [
        """```yaml
trace:
  - say: "Test"
    ext:
      fn: "TestFunc"
      args: []
      kwargs: {}
stack: []
```"""
    ]

    # Run interpreter
    chunks = list(
        interpreter.run(
            included_playbooks=[playbook],
            instruction="test instruction",
            session_context="test context",
            stream=True,
        )
    )

    # Verify external functions were collected
    assert len(interpreter.available_external_functions) == 1
    assert interpreter.available_external_functions[0] == "TestFunc: Test function"

    # Verify chunks were yielded
    assert len(chunks) > 0
    assert any(isinstance(chunk, AgentResponseChunk) for chunk in chunks)


@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="{{PLAYBOOKS_CONTENT}}\n{{SESSION_CONTEXT}}\n{{INITIAL_STATE}}",
)
def test_get_system_prompt(mock_file, interpreter):
    playbook = MagicMock()
    playbook.markdown = "# Test Playbook"

    prompt = interpreter.get_system_prompt([playbook], "test context")

    assert "# Test Playbook" in prompt
    assert "test context" in prompt
    assert '"thread_id": "main"' in prompt


def test_yield_requested_on_say_flag(interpreter):
    response = """```yaml
trace:
  - say: "Hello"
    ext:
      fn: "Say"
      args: ["Hello"]
      kwargs: {}
    yield: true
stack: []
```"""

    interpreter.parse_response(response)
    assert interpreter.yield_requested_on_say is True
