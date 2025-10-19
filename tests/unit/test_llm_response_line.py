"""Tests for LLMResponseLine class."""

import pytest

from playbooks.event_bus import EventBus
from playbooks.llm_response_line import LLMResponseLine


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self.id = "test_agent"
        self.state = MockState()

    def parse_instruction_pointer(self, step: str):
        """Mock parse_instruction_pointer method."""
        parts = step.split(":")
        return {
            "playbook": parts[0] if len(parts) > 0 else "",
            "line": parts[1] if len(parts) > 1 else "",
            "step": parts[2] if len(parts) > 2 else "",
            "type": parts[3] if len(parts) > 3 else "",
        }


class MockState:
    """Mock state for testing."""

    def __init__(self):
        pass


@pytest.fixture
def event_bus():
    """Fixture to create an EventBus instance."""
    return EventBus("test-session")


@pytest.fixture
def mock_agent():
    """Fixture to create a mock agent."""
    return MockAgent()


@pytest.mark.asyncio
class TestLLMResponseLine:
    """Test suite for LLMResponseLine."""

    async def test_simple_text(self, event_bus, mock_agent):
        """Test parsing simple text without any special markers."""
        line = await LLMResponseLine.create(
            "This is a simple text line", event_bus, mock_agent
        )
        assert line.text == "This is a simple text line"
        assert len(line.steps) == 0
        assert len(line.playbook_calls) == 0
        assert not line.playbook_finished
        assert not line.wait_for_user_input

    async def test_step_metadata(self, event_bus, mock_agent):
        """Test parsing Step metadata."""
        line = await LLMResponseLine.create(
            '`Step["auth_step"]` Authenticating user', event_bus, mock_agent
        )
        assert len(line.steps) == 1
        assert line.steps[0]["playbook"] == "auth_step"

        # Test multiple steps
        line = await LLMResponseLine.create(
            '`Step["step1"]` and `Step["step2"]` Multiple steps', event_bus, mock_agent
        )
        assert len(line.steps) == 2

    async def test_thinking_step(self, event_bus, mock_agent):
        """Test parsing thinking step (TNK suffix)."""
        line = await LLMResponseLine.create(
            '`Step["analysis:01:01:TNK"]` Thinking about the problem',
            event_bus,
            mock_agent,
        )
        assert line.is_thinking is True
        assert len(line.steps) == 1

    async def test_var_metadata_string(self, event_bus, mock_agent):
        """Test parsing Var metadata with string values."""
        line = await LLMResponseLine.create(
            '`Var[$user_email, "test@example.com"]` Setting email',
            event_bus,
            mock_agent,
        )
        assert line.vars["$user_email"].value == "test@example.com"

    async def test_var_metadata_number(self, event_bus, mock_agent):
        """Test parsing Var metadata with numeric values."""
        line = await LLMResponseLine.create(
            "`Var[$pin, 1234]` Setting PIN", event_bus, mock_agent
        )
        assert line.vars["$pin"].value == 1234

    async def test_var_metadata_boolean(self, event_bus, mock_agent):
        """Test parsing Var metadata with boolean values."""
        line = await LLMResponseLine.create(
            "`Var[$is_active, True]` Setting active flag", event_bus, mock_agent
        )
        assert line.vars["$is_active"].value is True

    async def test_var_metadata_null(self, event_bus, mock_agent):
        """Test parsing Var metadata with null values."""
        line = await LLMResponseLine.create(
            "`Var[$result, null]` Setting to null", event_bus, mock_agent
        )
        assert line.vars["$result"].value is None

    async def test_trigger_metadata(self, event_bus, mock_agent):
        """Test parsing Trigger metadata."""
        line = await LLMResponseLine.create(
            '`Trigger["user_auth_failed"]` Authentication failed', event_bus, mock_agent
        )
        assert len(line.triggers) == 1
        assert line.triggers[0] == "user_auth_failed"

    async def test_return_empty(self, event_bus, mock_agent):
        """Test parsing Return with empty value."""
        line = await LLMResponseLine.create(
            "`Return[]` Returning from playbook", event_bus, mock_agent
        )
        assert line.playbook_finished is True
        assert line.return_value is None

    async def test_return_string(self, event_bus, mock_agent):
        """Test parsing Return with string value."""
        line = await LLMResponseLine.create(
            '`Return["success"]` Returning success', event_bus, mock_agent
        )
        assert line.playbook_finished is True
        assert line.return_value == "success"

    async def test_return_true(self, event_bus, mock_agent):
        """Test parsing Return with true value."""
        line = await LLMResponseLine.create(
            "`Return[true]` Returning true", event_bus, mock_agent
        )
        assert line.playbook_finished is True
        assert line.return_value is True

    async def test_return_false(self, event_bus, mock_agent):
        """Test parsing Return with false value."""
        line = await LLMResponseLine.create(
            "`Return[false]` Returning false", event_bus, mock_agent
        )
        assert line.playbook_finished is True
        assert line.return_value is False

    async def test_return_null(self, event_bus, mock_agent):
        """Test parsing Return with null value."""
        line = await LLMResponseLine.create(
            "`Return[null]` Returning null", event_bus, mock_agent
        )
        assert line.playbook_finished is True
        assert line.return_value is None

    async def test_return_variable(self, event_bus, mock_agent):
        """Test parsing Return with variable reference."""
        line = await LLMResponseLine.create(
            "`Return[$result]` Returning variable", event_bus, mock_agent
        )
        assert line.playbook_finished is True
        assert line.return_value == "$result"

    async def test_simple_playbook_call(self, event_bus, mock_agent):
        """Test parsing simple playbook call."""
        line = await LLMResponseLine.create(
            "`GetOrder()` Calling GetOrder playbook", event_bus, mock_agent
        )
        assert len(line.playbook_calls) == 1
        assert line.playbook_calls[0].playbook_klass == "GetOrder"
        assert line.playbook_calls[0].args == []
        assert line.playbook_calls[0].kwargs == {}

    async def test_playbook_call_with_args(self, event_bus, mock_agent):
        """Test parsing playbook call with positional arguments."""
        line = await LLMResponseLine.create(
            "`GetOrder($order_id)` Fetching order", event_bus, mock_agent
        )
        assert len(line.playbook_calls) == 1
        assert line.playbook_calls[0].playbook_klass == "GetOrder"
        assert line.playbook_calls[0].args == ["$order_id"]

    async def test_playbook_call_with_string_arg(self, event_bus, mock_agent):
        """Test parsing playbook call with string argument."""
        line = await LLMResponseLine.create(
            '`ProcessOrder("pending")` Processing order', event_bus, mock_agent
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.playbook_klass == "ProcessOrder"
        assert call.args == ["pending"]

    async def test_playbook_call_with_kwargs(self, event_bus, mock_agent):
        """Test parsing playbook call with keyword arguments."""
        line = await LLMResponseLine.create(
            "`GetOrder(order_id=$id)` Fetching order", event_bus, mock_agent
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.playbook_klass == "GetOrder"
        assert call.kwargs == {"order_id": "$id"}

    async def test_playbook_call_with_boolean_kwargs(self, event_bus, mock_agent):
        """Test parsing playbook call with boolean keyword arguments."""
        line = await LLMResponseLine.create(
            "`FileSystemAgent.list_directory(path=$folder_path, recursive=true)` Listing files",
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.playbook_klass == "FileSystemAgent.list_directory"
        assert call.kwargs == {"path": "$folder_path", "recursive": True}
        # Ensure it's a boolean, not the string "$true"
        assert isinstance(call.kwargs["recursive"], bool)
        assert call.kwargs["recursive"] is True

    async def test_playbook_call_with_false_kwarg(self, event_bus, mock_agent):
        """Test parsing playbook call with false keyword argument."""
        line = await LLMResponseLine.create(
            "`FileSystemAgent.list_directory(path=$folder_path, recursive=false)` Listing files",
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.kwargs["recursive"] is False
        assert isinstance(call.kwargs["recursive"], bool)

    async def test_playbook_call_with_multiple_kwargs(self, event_bus, mock_agent):
        """Test parsing playbook call with multiple keyword arguments."""
        line = await LLMResponseLine.create(
            '`ProcessOrder($order, status="pending", notify=true)` Processing order',
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.playbook_klass == "ProcessOrder"
        assert call.args == ["$order"]
        assert call.kwargs == {"status": "pending", "notify": True}

    async def test_playbook_call_with_numeric_arg(self, event_bus, mock_agent):
        """Test parsing playbook call with numeric arguments."""
        line = await LLMResponseLine.create(
            "`ProcessBatch(100)` Processing batch", event_bus, mock_agent
        )
        assert len(line.playbook_calls) == 1
        call = line.playbook_calls[0]
        assert call.args == [100]

    async def test_module_qualified_playbook_call(self, event_bus, mock_agent):
        """Test parsing module-qualified playbook calls."""
        line = await LLMResponseLine.create(
            "`FileSystemAgent.list_directory()` Listing files", event_bus, mock_agent
        )
        assert len(line.playbook_calls) == 1
        assert line.playbook_calls[0].playbook_klass == "FileSystemAgent.list_directory"

    async def test_multiple_playbook_calls(self, event_bus, mock_agent):
        """Test parsing multiple playbook calls in one line."""
        line = await LLMResponseLine.create(
            "`GetOrder($id)` then `ProcessOrder($order)` Processing",
            event_bus,
            mock_agent,
        )
        assert len(line.playbook_calls) == 2
        assert line.playbook_calls[0].playbook_klass == "GetOrder"
        assert line.playbook_calls[1].playbook_klass == "ProcessOrder"

    async def test_yld_for_user(self, event_bus, mock_agent):
        """Test parsing YLD for user."""
        line = await LLMResponseLine.create(
            "YLD for user - waiting for user input", event_bus, mock_agent
        )
        assert line.wait_for_user_input is True
        assert line.wait_for_agent_input is False

    async def test_yld_for_human(self, event_bus, mock_agent):
        """Test parsing YLD for human."""
        line = await LLMResponseLine.create(
            "YLD for human - waiting for human input", event_bus, mock_agent
        )
        assert line.wait_for_user_input is True
        assert line.wait_for_agent_input is False

    async def test_yld_for_agent_id(self, event_bus, mock_agent):
        """Test parsing YLD for specific agent."""
        line = await LLMResponseLine.create(
            "YLD for agent researcher - waiting for researcher",
            event_bus,
            mock_agent,
        )
        assert line.wait_for_agent_input is True
        assert line.wait_for_agent_target == "researcher"

    async def test_yld_for_meeting(self, event_bus, mock_agent):
        """Test parsing YLD for meeting."""
        line = await LLMResponseLine.create(
            "YLD for meeting - waiting for meeting", event_bus, mock_agent
        )
        assert line.wait_for_agent_input is True
        assert line.wait_for_agent_target == "meeting current"

    async def test_yld_for_meeting_with_id(self, event_bus, mock_agent):
        """Test parsing YLD for meeting with specific ID."""
        line = await LLMResponseLine.create(
            "YLD for meeting 123 - waiting for meeting 123", event_bus, mock_agent
        )
        assert line.wait_for_agent_input is True
        assert line.wait_for_agent_target == "meeting 123"

    async def test_yld_for_agent_type(self, event_bus, mock_agent):
        """Test parsing YLD for agent type."""
        line = await LLMResponseLine.create(
            "YLD for ResearchAgent - waiting for research agent",
            event_bus,
            mock_agent,
        )
        assert line.wait_for_agent_input is True
        # Agent type is extracted from lowercased text
        assert line.wait_for_agent_target == "researchagent"

    async def test_yld_for_return(self, event_bus, mock_agent):
        """Test parsing YLD for return."""
        line = await LLMResponseLine.create(
            "YLD for return - returning from playbook", event_bus, mock_agent
        )
        assert line.playbook_finished is True

    async def test_yld_for_exit(self, event_bus, mock_agent):
        """Test parsing YLD for exit."""
        line = await LLMResponseLine.create(
            "yld for exit - exiting program", event_bus, mock_agent
        )
        assert line.exit_program is True

    async def test_yld_question_pattern(self, event_bus, mock_agent):
        """Test that YLD? pattern doesn't trigger yield."""
        line = await LLMResponseLine.create(
            "YLD? Thinking whether to yield", event_bus, mock_agent
        )
        assert line.wait_for_user_input is False
        assert line.wait_for_agent_input is False

    async def test_complex_line_with_multiple_metadata(self, event_bus, mock_agent):
        """Test parsing line with multiple types of metadata."""
        line = await LLMResponseLine.create(
            '`Step["process:01:01:ACT"]` `Var[$status, "pending"]` `GetOrder($id)` Processing order',
            event_bus,
            mock_agent,
        )
        assert len(line.steps) == 1
        assert line.vars["$status"].value == "pending"
        assert len(line.playbook_calls) == 1
        assert line.playbook_calls[0].playbook_klass == "GetOrder"

    async def test_playbook_call_with_assignment_prefix(self, event_bus, mock_agent):
        """Test parsing playbook call with assignment prefix like $result = GetOrder()."""
        line = await LLMResponseLine.create(
            "`$result = GetOrder($id)` Fetching order", event_bus, mock_agent
        )
        assert len(line.playbook_calls) == 1
        assert line.playbook_calls[0].playbook_klass == "GetOrder"
        assert line.playbook_calls[0].args == ["$id"]
