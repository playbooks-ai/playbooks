"""Tests for artifact content being properly displayed in Say() and interpolated in strings."""

from unittest.mock import AsyncMock, Mock

import pytest

from playbooks.agents.ai_agent import AIAgent
from playbooks.core.argument_types import LiteralValue, VariableReference
from playbooks.state.call_stack import CallStackFrame, InstructionPointer
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.execution_state import ExecutionState
from playbooks.playbook_call import PlaybookCall
from playbooks.state.variables import Artifact


class MockAIAgent(AIAgent):
    """Mock AIAgent for testing."""

    klass = "MockAIAgent"
    description = "Mock AIAgent for testing"
    metadata = {}
    playbooks = {}
    namespace_manager = None

    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus)

    def discover_playbooks(self):
        pass


@pytest.fixture
def event_bus():
    """Create a mock event bus."""
    return Mock(spec=EventBus)


@pytest.fixture
def agent(event_bus):
    """Create a mock agent with execution state."""
    agent = MockAIAgent(event_bus)
    agent.state = ExecutionState(event_bus, "MockAIAgent", "test-agent-id")

    # Mock the execution summary variable
    mock_execution_summary = Mock()
    mock_execution_summary.value = "Test execution summary"
    agent.state.variables.variables["$__"] = mock_execution_summary

    # Push a frame onto the call stack
    instruction_pointer = InstructionPointer("TestPlaybook", "1", 1)
    frame = CallStackFrame(instruction_pointer)
    agent.state.call_stack.push(frame)

    # Mock program
    agent.program = Mock()
    agent.program.execution_finished = False

    return agent


@pytest.mark.asyncio
async def test_artifact_content_in_say_direct_argument(agent):
    """Test that Say("user", $artifact) displays artifact content, not just summary."""
    # Create an artifact
    artifact = Artifact(
        name="report",
        summary="Monthly Report",
        value="Detailed report content\nWith multiple lines\nAnd important data",
    )

    # Store it in variables - Artifact IS a Variable, so store it directly
    agent.state.variables.variables["$report"] = artifact

    # Mock the Say playbook with execute method
    mock_playbook = Mock(name="Say", meeting=False)
    mock_playbook.execute = AsyncMock(return_value=None)
    agent.playbooks_by_name = {"Say": mock_playbook}

    # Mock _pre_execute to return the mock playbook
    agent._pre_execute = AsyncMock(
        return_value=(
            mock_playbook,
            PlaybookCall(
                "Say", [LiteralValue("user"), VariableReference("$report")], {}
            ),
            None,
        )
    )

    # Mock _post_execute
    agent._post_execute = AsyncMock(return_value=(True, None))

    # Execute Say with artifact argument
    await agent.execute_playbook("Say", ["user", "$report"])

    # Verify execute was called with artifact that behaves like its content
    mock_playbook.execute.assert_called_once()
    call_args = mock_playbook.execute.call_args[0]
    assert call_args[0] == "user"
    # Artifact should behave like its content (compares equal to content string)
    assert (
        call_args[1]
        == "Detailed report content\nWith multiple lines\nAnd important data"
    )
    # Artifact now behaves like a string while preserving metadata
    assert (
        str(call_args[1])
        == "Detailed report content\nWith multiple lines\nAnd important data"
    )


@pytest.mark.asyncio
async def test_artifact_interpolation_in_string(agent):
    """Test that Say("user", "Here is your answer: {$artifact}") interpolates the artifact content."""
    # Create an artifact
    artifact = Artifact(
        name="answer",
        summary="Answer Summary",
        value="The answer is 42",
    )

    # Store it in variables - Artifact IS a Variable, so store it directly
    agent.state.variables.variables["$answer"] = artifact

    # Mock the Say playbook with execute method
    mock_playbook = Mock(name="Say", meeting=False)
    mock_playbook.execute = AsyncMock(return_value=None)
    agent.playbooks_by_name = {"Say": mock_playbook}

    # Mock _pre_execute
    agent._pre_execute = AsyncMock(
        return_value=(
            mock_playbook,
            PlaybookCall(
                "Say",
                [LiteralValue("user"), LiteralValue("Here is your answer: {$answer}")],
                {},
            ),
            None,
        )
    )

    # Mock _post_execute
    agent._post_execute = AsyncMock(return_value=(True, None))

    # Execute Say with interpolated string
    await agent.execute_playbook("Say", ["user", "Here is your answer: {$answer}"])

    # Verify execute was called with interpolated content
    mock_playbook.execute.assert_called_once()
    call_args = mock_playbook.execute.call_args[0]
    assert call_args[0] == "user"
    # The {$answer} should be replaced with artifact content
    assert call_args[1] == "Here is your answer: The answer is 42"


@pytest.mark.asyncio
async def test_multiple_artifact_interpolations(agent):
    """Test multiple artifacts in a single interpolated string."""
    # Create artifacts
    artifact1 = Artifact(name="name", summary="Name", value="John Doe")
    artifact2 = Artifact(name="age", summary="Age", value="30")

    # Store in variables - Artifacts ARE Variables, so store them directly
    agent.state.variables.variables["$name"] = artifact1
    agent.state.variables.variables["$age"] = artifact2

    # Mock the Say playbook with execute method
    mock_playbook = Mock(name="Say", meeting=False)
    mock_playbook.execute = AsyncMock(return_value=None)
    agent.playbooks_by_name = {"Say": mock_playbook}

    # Mock _pre_execute
    agent._pre_execute = AsyncMock(
        return_value=(
            mock_playbook,
            PlaybookCall(
                "Say",
                [LiteralValue("user"), LiteralValue("User: {$name}, Age: {$age}")],
                {},
            ),
            None,
        )
    )

    # Mock _post_execute
    agent._post_execute = AsyncMock(return_value=(True, None))

    # Execute Say with multiple interpolations
    await agent.execute_playbook("Say", ["user", "User: {$name}, Age: {$age}"])

    # Verify interpolation
    mock_playbook.execute.assert_called_once()
    call_args = mock_playbook.execute.call_args[0]
    assert call_args[1] == "User: John Doe, Age: 30"


@pytest.mark.asyncio
async def test_artifact_in_kwargs(agent):
    """Test that artifacts in kwargs are also converted to content."""
    # Create an artifact
    artifact = Artifact(name="data", summary="Data Summary", value="Important data")

    # Store it in variables - Artifact IS a Variable, so store it directly
    agent.state.variables.variables["$data"] = artifact

    # Mock a custom playbook with execute method
    mock_playbook = Mock(name="CustomPlaybook", meeting=False)
    mock_playbook.execute = AsyncMock(return_value=None)
    agent.playbooks_by_name = {"CustomPlaybook": mock_playbook}

    # Mock _pre_execute
    agent._pre_execute = AsyncMock(
        return_value=(
            mock_playbook,
            PlaybookCall("CustomPlaybook", [], {"content": VariableReference("$data")}),
            None,
        )
    )

    # Mock _post_execute
    agent._post_execute = AsyncMock(return_value=(True, None))

    # Execute with artifact in kwargs
    await agent.execute_playbook("CustomPlaybook", [], {"content": "$data"})

    # Verify the kwarg received artifact that behaves like content
    mock_playbook.execute.assert_called_once()
    call_kwargs = mock_playbook.execute.call_args[1]
    # Artifact should behave like its content (compares equal to content string)
    assert call_kwargs["content"] == "Important data"
    # Artifact now behaves like a string while preserving metadata
    assert str(call_kwargs["content"]) == "Important data"


@pytest.mark.asyncio
async def test_string_interpolation_in_kwargs(agent):
    """Test that string interpolation works in kwargs too."""
    # Create an artifact
    artifact = Artifact(name="title", summary="Title", value="Report Title")

    # Store it in variables - Artifact IS a Variable, so store it directly
    agent.state.variables.variables["$title"] = artifact

    # Mock a custom playbook with execute method
    mock_playbook = Mock(name="CustomPlaybook", meeting=False)
    mock_playbook.execute = AsyncMock(return_value=None)
    agent.playbooks_by_name = {"CustomPlaybook": mock_playbook}

    # Mock _pre_execute
    agent._pre_execute = AsyncMock(
        return_value=(
            mock_playbook,
            PlaybookCall(
                "CustomPlaybook", [], {"message": LiteralValue("Title: {$title}")}
            ),
            None,
        )
    )

    # Mock _post_execute
    agent._post_execute = AsyncMock(return_value=(True, None))

    # Execute with interpolated kwarg
    await agent.execute_playbook("CustomPlaybook", [], {"message": "Title: {$title}"})

    # Verify interpolation in kwargs
    mock_playbook.execute.assert_called_once()
    call_kwargs = mock_playbook.execute.call_args[1]
    assert call_kwargs["message"] == "Title: Report Title"


@pytest.mark.asyncio
async def test_non_artifact_values_unchanged(agent):
    """Test that non-artifact values are not affected by the changes."""
    # Store regular values in variables
    agent.state.variables["$name"] = "Alice"
    agent.state.variables["$count"] = 42

    # Mock the Say playbook with execute method
    mock_playbook = Mock(name="Say", meeting=False)
    mock_playbook.execute = AsyncMock(return_value=None)
    agent.playbooks_by_name = {"Say": mock_playbook}

    # Mock _pre_execute
    agent._pre_execute = AsyncMock(
        return_value=(
            mock_playbook,
            PlaybookCall(
                "Say",
                [LiteralValue("user"), LiteralValue("Name: {$name}, Count: {$count}")],
                {},
            ),
            None,
        )
    )

    # Mock _post_execute
    agent._post_execute = AsyncMock(return_value=(True, None))

    # Execute Say with interpolated string
    await agent.execute_playbook("Say", ["user", "Name: {$name}, Count: {$count}"])

    # Verify regular interpolation still works
    mock_playbook.execute.assert_called_once()
    call_args = mock_playbook.execute.call_args[0]
    assert call_args[1] == "Name: Alice, Count: 42"


@pytest.mark.asyncio
async def test_interpolation_with_expressions(agent):
    """Test that complex expressions work in interpolation."""
    # Store values in variables
    agent.state.variables["$price"] = 99.99
    agent.state.variables["$quantity"] = 3

    # Mock the Say playbook with execute method
    mock_playbook = Mock(name="Say", meeting=False)
    mock_playbook.execute = AsyncMock(return_value=None)
    agent.playbooks_by_name = {"Say": mock_playbook}

    # Mock _pre_execute
    agent._pre_execute = AsyncMock(
        return_value=(
            mock_playbook,
            PlaybookCall(
                "Say",
                [
                    LiteralValue("user"),
                    LiteralValue("Total: ${round($price * $quantity, 2)}"),
                ],
                {},
            ),
            None,
        )
    )

    # Mock _post_execute
    agent._post_execute = AsyncMock(return_value=(True, None))

    # Execute Say with expression interpolation
    await agent.execute_playbook(
        "Say", ["user", "Total: ${round($price * $quantity, 2)}"]
    )

    # Verify expression evaluation
    mock_playbook.execute.assert_called_once()
    call_args = mock_playbook.execute.call_args[0]
    assert call_args[1] == "Total: $299.97"


@pytest.mark.asyncio
async def test_format_value_with_artifact():
    """Test that format_value handles Artifact objects correctly."""
    from playbooks.utils.expression_engine import format_value

    artifact = Artifact(
        name="test",
        summary="Test Summary",
        value="Test Content",
    )

    result = format_value(artifact)
    assert result == "Test Content"
    assert result != "Test Summary"
