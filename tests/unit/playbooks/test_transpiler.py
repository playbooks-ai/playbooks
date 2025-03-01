from unittest.mock import patch

import pytest

from playbooks.exceptions import PlaybookError
from playbooks.transpiler import Transpiler
from playbooks.utils.llm_helper import LLMConfig


@pytest.fixture
def transpiler():
    return Transpiler(LLMConfig(model="test-model"))


def test_empty_content(transpiler):
    with pytest.raises(PlaybookError, match="Empty playbook content"):
        transpiler.process("")

    with pytest.raises(PlaybookError, match="Empty playbook content"):
        transpiler.process("   \n   ")


def test_missing_h1_header(transpiler):
    content = """
## MyPlaybook() -> None

### Trigger
When something happens

### Steps
Do something
"""
    with pytest.raises(PlaybookError, match="Missing H1 header"):
        transpiler.process(content)


def test_missing_h2_header(transpiler):
    content = """
# MyAgent

### Trigger
When something happens

### Steps
Do something
"""
    with pytest.raises(PlaybookError, match="Missing H2 header"):
        transpiler.process(content)


@patch("playbooks.transpiler.get_completion")
@patch("playbooks.transpiler.get_messages_for_prompt")
def test_successful_transpilation(mock_get_messages, mock_get_completion, transpiler):
    content = """
# MyAgent

## MyPlaybook() -> None

### Trigger
When something happens

### Steps
Do something
"""
    mock_response = """
# MyAgent

## MyPlaybook() -> None

### Trigger
01:BGN When something happens

### Steps
01:EXE Do something
"""

    # Mock the get_messages_for_prompt function
    mock_get_messages.return_value = [{"role": "user", "content": "test prompt"}]

    # Mock the get_completion function
    mock_get_completion.return_value = iter([mock_response])

    # Process the content
    result = transpiler.process(content)

    # Verify the result
    assert result == mock_response

    # Verify get_messages_for_prompt was called
    mock_get_messages.assert_called_once()

    # Verify get_completion was called with the correct parameters
    mock_get_completion.assert_called_once()
    call_args = mock_get_completion.call_args[1]
    assert call_args["llm_config"].model == "test-model"
    assert call_args["messages"] == [{"role": "user", "content": "test prompt"}]
    assert call_args["stream"] is False
