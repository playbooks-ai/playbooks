"""Tests for LLMResponse class."""

import pytest

from playbooks.event_bus import EventBus
from playbooks.llm_response import LLMResponse, _strip_code_block_markers


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self.id = "test_agent"
        self.state = MockState()
        self.execution_counter = 0

    def parse_instruction_pointer(self, step: str):
        """Mock parse_instruction_pointer method."""
        parts = step.split(":")
        return {
            "playbook": parts[0] if len(parts) > 0 else "",
            "line": parts[1] if len(parts) > 1 else "",
            "step": parts[2] if len(parts) > 2 else "",
        }


class MockState:
    """Mock execution state for testing."""

    def __init__(self):
        self.last_llm_response = None


class TestStripCodeBlockMarkers:
    """Test suite for _strip_code_block_markers function."""

    def test_strip_triple_backticks(self):
        """Test stripping basic ``` markers."""
        code = '```\nStep("Test:01:QUE")\n```'
        result = _strip_code_block_markers(code)
        assert result == 'Step("Test:01:QUE")'
        assert "```" not in result

    def test_strip_python_language_marker(self):
        """Test stripping ```python markers."""
        code = '```python\nStep("Test:01:QUE")\n```'
        result = _strip_code_block_markers(code)
        assert result == 'Step("Test:01:QUE")'

    def test_strip_python3_language_marker(self):
        """Test stripping ```python3 markers."""
        code = "```python3\nVarSet = 5\n```"
        result = _strip_code_block_markers(code)
        assert result == "VarSet = 5"

    def test_no_markers(self):
        """Test code without markers."""
        code = 'Step("Test:01:QUE")'
        result = _strip_code_block_markers(code)
        assert result == 'Step("Test:01:QUE")'

    def test_only_opening_marker(self):
        """Test code with only opening marker."""
        code = '```python\nStep("Test:01:QUE")'
        result = _strip_code_block_markers(code)
        assert result == 'Step("Test:01:QUE")'
        assert "```" not in result

    def test_only_closing_marker(self):
        """Test code with only closing marker."""
        code = 'Step("Test:01:QUE")\n```'
        result = _strip_code_block_markers(code)
        assert result == 'Step("Test:01:QUE")'

    def test_multiline_code(self):
        """Test multiline code with markers."""
        code = """```python
# execution_id: 1
# recap: multiline test
# plan: execute multiple steps
Step("Test:01:QUE")
Say("user", "Hello")
$count = 5
```"""
        result = _strip_code_block_markers(code)
        assert "```" not in result
        assert "# execution_id: 1" in result
        assert "# recap: multiline test" in result
        assert "# plan: execute multiple steps" in result
        assert 'Step("Test:01:QUE")' in result
        assert 'Say("user", "Hello")' in result

    def test_whitespace_handling(self):
        """Test stripping with extra whitespace."""
        code = """  ```python
  Step("test")
  ```  """
        result = _strip_code_block_markers(code)
        assert result == 'Step("test")'
        assert "```" not in result


@pytest.mark.asyncio
class TestLLMResponse:
    """Test suite for LLMResponse."""

    @pytest.fixture
    def event_bus(self):
        """Fixture for event bus."""
        return EventBus("test-session")

    @pytest.fixture
    def mock_agent(self):
        """Fixture for mock agent."""
        return MockAgent()

    async def test_parse_response_with_markers(self, event_bus, mock_agent):
        """Test parsing response with code block markers."""
        response = """```python
# execution_id: 1
# recap: testing response parsing
# plan: execute test steps
Step("Test:01:QUE")
Say("user", "Hello")
```"""
        llm_response = await LLMResponse.create(response, event_bus, mock_agent)
        assert llm_response.execution_id == 1
        assert llm_response.recap == "testing response parsing"
        assert llm_response.plan == "execute test steps"

    async def test_parse_response_without_markers(self, event_bus, mock_agent):
        """Test parsing response without code block markers."""
        response = """# execution_id: 2
# recap: parsing without markers
# plan: execute world greeting
Step("Test:02:QUE")
Say("user", "World")"""
        llm_response = await LLMResponse.create(response, event_bus, mock_agent)
        assert llm_response.execution_id == 2
        assert llm_response.recap == "parsing without markers"
        assert llm_response.plan == "execute world greeting"

    async def test_extract_execution_id(self, event_bus, mock_agent):
        """Test execution_id extraction."""
        response = """# execution_id: 42
# recap: extraction test
# plan: verify parsing
Step("Test:01:QUE")"""
        llm_response = await LLMResponse.create(response, event_bus, mock_agent)
        assert llm_response.execution_id == 42
        assert llm_response.recap == "extraction test"
        assert llm_response.plan == "verify parsing"
