"""Tests for variable assignment parsing in LLMResponseLine."""

import pytest

from playbooks.argument_types import VariableReference
from playbooks.event_bus import EventBus
from playbooks.llm_response_line import LLMResponseLine


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self.id = "test_agent"
        self.state = None

    def parse_instruction_pointer(self, step):
        """Mock instruction pointer parsing."""
        return None


@pytest.mark.asyncio
class TestVariableAssignmentParsing:
    """Test parsing of variable assignment syntax in playbook calls."""

    async def test_parse_simple_assignment_without_type(self):
        """Test parsing `$result = MyPlaybook(arg1)` without type annotation."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        text = "`$result = MyPlaybook(arg1)`"

        line = await LLMResponseLine.create(text, event_bus, agent)

        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.variable_to_assign == "$result"
        assert call.type_annotation is None
        assert call.playbook_klass == "MyPlaybook"

    async def test_parse_assignment_with_type(self):
        """Test parsing `$result:bool = MyPlaybook(arg1)` with type annotation."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        text = "`$result:bool = MyPlaybook(arg1)`"

        line = await LLMResponseLine.create(text, event_bus, agent)

        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.variable_to_assign == "$result"
        assert call.type_annotation == "bool"
        assert call.playbook_klass == "MyPlaybook"

    async def test_parse_different_type_annotations(self):
        """Test parsing with different type annotations (str, int, list, dict)."""
        event_bus = EventBus("test_session")
        agent = MockAgent()

        test_cases = [
            ("`$data:str = GetData()`", "str"),
            ("`$count:int = Count()`", "int"),
            ("`$items:list = GetList()`", "list"),
            ("`$config:dict = GetConfig()`", "dict"),
        ]

        for text, expected_type in test_cases:
            line = await LLMResponseLine.create(text, event_bus, agent)
            assert len(line.playbook_calls) == 1
            assert line.playbook_calls[0].type_annotation == expected_type

    async def test_parse_without_assignment(self):
        """Test parsing `MyPlaybook()` without assignment - should have None values."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        text = "`MyPlaybook(arg1)`"

        line = await LLMResponseLine.create(text, event_bus, agent)

        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.variable_to_assign is None
        assert call.type_annotation is None
        assert call.playbook_klass == "MyPlaybook"

    async def test_parse_assignment_with_variable_arguments(self):
        """Test parsing `$value:Any = Calculate($x, $y)` with variable arguments."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        text = "`$value:Any = Calculate($x, $y)`"

        line = await LLMResponseLine.create(text, event_bus, agent)

        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.variable_to_assign == "$value"
        assert call.type_annotation == "Any"
        assert call.playbook_klass == "Calculate"
        assert len(call.args) == 2
        assert isinstance(call.args[0], VariableReference)
        assert call.args[0].reference == "$x"
        assert isinstance(call.args[1], VariableReference)
        assert call.args[1].reference == "$y"

    async def test_parse_multiple_calls_on_same_line(self):
        """Test parsing multiple calls on same line with and without assignments."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        text = "`$a = PB1()` and then `PB2()`"

        line = await LLMResponseLine.create(text, event_bus, agent)

        assert len(line.playbook_calls) == 2
        assert line.playbook_calls[0].variable_to_assign == "$a"
        assert line.playbook_calls[1].variable_to_assign is None

    async def test_parse_whitespace_variations(self):
        """Test parsing with different whitespace patterns."""
        event_bus = EventBus("test_session")
        agent = MockAgent()

        test_cases = [
            "`$result = PB()`",  # Normal spacing
            "`$result=PB()`",  # No spacing
            "`$result  =  PB()`",  # Extra spacing
            "`$result:bool = PB()`",  # With type
            "`$result:bool=PB()`",  # With type, no spacing
        ]

        for text in test_cases:
            line = await LLMResponseLine.create(text, event_bus, agent)
            assert len(line.playbook_calls) == 1
            assert line.playbook_calls[0].variable_to_assign == "$result"

    async def test_parse_complex_variable_names(self):
        """Test parsing complex variable names like $user_data_2024."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        text = "`$user_data_2024:dict = GetUserData()`"

        line = await LLMResponseLine.create(text, event_bus, agent)

        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.variable_to_assign == "$user_data_2024"
        assert call.type_annotation == "dict"

    async def test_parse_playbook_with_kwargs(self):
        """Test parsing assignment with playbook calls that have kwargs."""
        event_bus = EventBus("test_session")
        agent = MockAgent()
        text = "`$result:bool = PB2(age=$age, name='John')`"

        line = await LLMResponseLine.create(text, event_bus, agent)

        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.variable_to_assign == "$result"
        assert call.type_annotation == "bool"
        assert call.playbook_klass == "PB2"
