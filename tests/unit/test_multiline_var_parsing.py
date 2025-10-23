"""Tests for multi-line Var statement parsing in LLMResponse."""

import pytest

from playbooks.event_bus import EventBus
from playbooks.llm_response import LLMResponse


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self.id = "test_agent"
        self.state = MockState()

    def parse_instruction_pointer(self, step):
        """Mock instruction pointer parsing."""
        return None


class MockState:
    """Mock state for testing."""

    def __init__(self):
        self.last_llm_response = None


@pytest.mark.asyncio
class TestMultilineVarParsing:
    """Test parsing of multi-line Var statements."""

    async def test_parse_multiline_json_array(self):
        """Test parsing multi-line JSON array - the user's original example."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        response = """`Var[$relevant_sections, [
  {"file": "/Users/amolk/work/workspace/playbooks-docs/docs/reference/context-engineering.md", "start_line": 17, "end_line": 20, "title": "Stack-based Context Management"},
  {"file": "/Users/amolk/work/workspace/playbooks-docs/docs/reference/context-engineering.md", "start_line": 21, "end_line": 41, "title": "How It Works"},
  {"file": "/Users/amolk/work/workspace/playbooks-docs/docs/reference/context-engineering.md", "start_line": 5, "end_line": 16, "title": "Key Innovations"},
  {"file": "/Users/amolk/work/workspace/playbooks-docs/docs/programming-guide/index.md", "start_line": 28, "end_line": 35, "title": "Philosophy: Software 3.0"},
  {"file": "/Users/amolk/work/workspace/playbooks-docs/docs/reference/playbooks-assembly-language.md", "start_line": 7, "end_line": 34, "title": "Traditional CPU vs LLM Execution Engine"}
]]`"""

        llm_response = await LLMResponse.create(response, event_bus, agent)

        # Should create a single line (multi-line content preserved as one line)
        assert len(llm_response.lines) == 1
        line = llm_response.lines[0]

        # Should parse the variable
        assert "$relevant_sections" in line.vars
        var_value = line.vars["$relevant_sections"].value

        # Should be a list with 5 items
        assert isinstance(var_value, list)
        assert len(var_value) == 5

        # Verify first item structure
        assert (
            var_value[0]["file"]
            == "/Users/amolk/work/workspace/playbooks-docs/docs/reference/context-engineering.md"
        )
        assert var_value[0]["start_line"] == 17
        assert var_value[0]["end_line"] == 20
        assert var_value[0]["title"] == "Stack-based Context Management"

    async def test_parse_multiline_json_object(self):
        """Test parsing multi-line JSON object."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        response = """`Var[$config, {
  "name": "test",
  "enabled": true,
  "options": {
    "timeout": 30,
    "retries": 3
  }
}]`"""

        llm_response = await LLMResponse.create(response, event_bus, agent)

        assert len(llm_response.lines) == 1
        line = llm_response.lines[0]

        assert "$config" in line.vars
        var_value = line.vars["$config"].value

        assert isinstance(var_value, dict)
        assert var_value["name"] == "test"
        assert var_value["enabled"] is True
        assert var_value["options"]["timeout"] == 30
        assert var_value["options"]["retries"] == 3

    async def test_parse_triple_quoted_string_backward_compatibility(self):
        """Test that triple-quoted strings still work (backward compatibility)."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        response = '`Var[$text, """This is a\nmulti-line\nstring"""]`'

        llm_response = await LLMResponse.create(response, event_bus, agent)

        assert len(llm_response.lines) == 1
        line = llm_response.lines[0]

        assert "$text" in line.vars
        assert line.vars["$text"].value == "This is a\nmulti-line\nstring"

    async def test_parse_simple_string_value(self):
        """Test parsing simple string value on single line."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        response = '`Var[$name, "John Doe"]`'

        llm_response = await LLMResponse.create(response, event_bus, agent)

        assert len(llm_response.lines) == 1
        line = llm_response.lines[0]

        assert "$name" in line.vars
        assert line.vars["$name"].value == "John Doe"

    async def test_parse_numeric_values(self):
        """Test parsing numeric values."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        response = "`Var[$count, 42]` `Var[$price, 19.99]`"

        llm_response = await LLMResponse.create(response, event_bus, agent)

        assert len(llm_response.lines) == 1
        line = llm_response.lines[0]

        assert "$count" in line.vars
        assert line.vars["$count"].value == 42
        assert "$price" in line.vars
        assert line.vars["$price"].value == 19.99

    async def test_parse_nested_array(self):
        """Test parsing nested arrays."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        response = """`Var[$matrix, [
  [1, 2, 3],
  [4, 5, 6],
  [7, 8, 9]
]]`"""

        llm_response = await LLMResponse.create(response, event_bus, agent)

        assert len(llm_response.lines) == 1
        line = llm_response.lines[0]

        assert "$matrix" in line.vars
        var_value = line.vars["$matrix"].value

        assert isinstance(var_value, list)
        assert len(var_value) == 3
        assert var_value[0] == [1, 2, 3]
        assert var_value[1] == [4, 5, 6]
        assert var_value[2] == [7, 8, 9]

    async def test_parse_mixed_content_with_text(self):
        """Test parsing Var statements mixed with regular text."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        response = """Here are the results:

`Var[$items, [
  "item1",
  "item2",
  "item3"
]]`

Processing complete."""

        llm_response = await LLMResponse.create(response, event_bus, agent)

        # Should have 5 lines: text, blank, var (preserved as one), blank, text
        assert len(llm_response.lines) == 5

        # Find the line with the variable
        var_line = None
        for line in llm_response.lines:
            if "$items" in line.vars:
                var_line = line
                break

        assert var_line is not None
        assert var_line.vars["$items"].value == ["item1", "item2", "item3"]

    async def test_parse_multiple_vars_multiline(self):
        """Test parsing multiple Var statements on separate lines."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        response = """`Var[$first, [
  1,
  2
]]`
`Var[$second, {
  "key": "value"
}]`"""

        llm_response = await LLMResponse.create(response, event_bus, agent)

        # Should have 2 lines, each with its own Var
        assert len(llm_response.lines) == 2

        # Check first variable
        line1 = llm_response.lines[0]
        assert "$first" in line1.vars
        assert line1.vars["$first"].value == [1, 2]

        # Check second variable
        line2 = llm_response.lines[1]
        assert "$second" in line2.vars
        assert line2.vars["$second"].value == {"key": "value"}

    async def test_parse_empty_array(self):
        """Test parsing empty array."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        response = "`Var[$empty, []]`"

        llm_response = await LLMResponse.create(response, event_bus, agent)

        assert len(llm_response.lines) == 1
        line = llm_response.lines[0]

        assert "$empty" in line.vars
        assert line.vars["$empty"].value == []

    async def test_parse_empty_object(self):
        """Test parsing empty object."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        response = "`Var[$empty, {}]`"

        llm_response = await LLMResponse.create(response, event_bus, agent)

        assert len(llm_response.lines) == 1
        line = llm_response.lines[0]

        assert "$empty" in line.vars
        assert line.vars["$empty"].value == {}

    async def test_parse_boolean_and_null_values(self):
        """Test parsing boolean and null values."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        response = "`Var[$active, true]` `Var[$inactive, false]` `Var[$nothing, null]`"

        llm_response = await LLMResponse.create(response, event_bus, agent)

        assert len(llm_response.lines) == 1
        line = llm_response.lines[0]

        assert line.vars["$active"].value is True
        assert line.vars["$inactive"].value is False
        assert line.vars["$nothing"].value is None

    async def test_parse_complex_nested_structure(self):
        """Test parsing complex nested JSON structure."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        response = """`Var[$data, {
  "users": [
    {
      "name": "Alice",
      "roles": ["admin", "user"]
    },
    {
      "name": "Bob",
      "roles": ["user"]
    }
  ],
  "settings": {
    "theme": "dark",
    "notifications": true
  }
}]`"""

        llm_response = await LLMResponse.create(response, event_bus, agent)

        assert len(llm_response.lines) == 1
        line = llm_response.lines[0]

        assert "$data" in line.vars
        data = line.vars["$data"].value

        assert len(data["users"]) == 2
        assert data["users"][0]["name"] == "Alice"
        assert data["users"][0]["roles"] == ["admin", "user"]
        assert data["settings"]["theme"] == "dark"
        assert data["settings"]["notifications"] is True
