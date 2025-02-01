import pytest
from unittest.mock import patch, mock_open

from playbooks.transpiler import Transpiler
from playbooks.config import LLMConfig
from playbooks.exceptions import PlaybookError


@pytest.fixture
def transpiler():
    config = LLMConfig(model="test-model")
    return Transpiler(config)


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


def test_successful_transpilation(transpiler):
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
    
    with patch('playbooks.transpiler.get_completion') as mock_get_completion:
        mock_get_completion.return_value = iter([mock_response])
        result = transpiler.process(content)
        assert result == mock_response
        
        # Verify prompt was loaded and used correctly
        mock_get_completion.assert_called_once()
        call_args = mock_get_completion.call_args[1]
        assert call_args['llm_config'].model == "test-model"
        assert len(call_args['messages']) == 1
        assert call_args['messages'][0]['role'] == "user"
        assert content in call_args['messages'][0]['content']
