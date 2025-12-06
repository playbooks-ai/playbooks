"""Tests for automatic artifact loading when accessed but not in context."""

from unittest.mock import Mock

import pytest

from playbooks.agents.ai_agent import AIAgent
from playbooks.compilation.expression_engine import ExpressionContext
from playbooks.infrastructure.event_bus import EventBus
from playbooks.llm.messages.types import ArtifactLLMMessage
from playbooks.state.call_stack import CallStackFrame, InstructionPointer
from playbooks.state.execution_state import ExecutionState
from playbooks.state.variables import Artifact


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus("test-session")


@pytest.fixture
def agent(event_bus):
    """Create a mock agent for testing."""
    agent = Mock(spec=AIAgent)
    agent.id = "test_agent"
    agent.state = ExecutionState(event_bus, "MockAgent", "test_agent")

    # Mock the program with _debug_server
    agent.program = Mock()
    agent.program._debug_server = None

    # Initialize call stack with a frame
    instruction_pointer = InstructionPointer("TestPlaybook", "1", 1)
    frame = CallStackFrame(instruction_pointer)
    agent.state.call_stack.push(frame)

    return agent


@pytest.fixture
def artifact():
    """Create a test artifact."""
    return Artifact(
        name="test_artifact",
        summary="Test artifact summary",
        value="This is the artifact content.",
    )


class TestArtifactAutoLoadingExpressionContext:
    """Test auto-loading from ExpressionContext."""

    def test_artifact_auto_loads_when_not_in_context(self, agent, artifact):
        """Test that accessing artifact automatically loads it when not in context."""
        # Store artifact in variables
        agent.state.variables.test_artifact = artifact

        # Verify artifact is not loaded
        assert not agent.state.call_stack.is_artifact_loaded("test_artifact")
        assert len(agent.state.call_stack.peek().llm_messages) == 0

        # Access the artifact via ExpressionContext
        context = ExpressionContext(agent, agent.state, None)
        result = context.resolve_variable("test_artifact")

        # Verify artifact was returned
        assert isinstance(result, Artifact)
        assert result.name == "test_artifact"

        # Verify artifact was auto-loaded
        assert agent.state.call_stack.is_artifact_loaded("test_artifact")
        assert len(agent.state.call_stack.peek().llm_messages) == 1
        assert isinstance(
            agent.state.call_stack.peek().llm_messages[0], ArtifactLLMMessage
        )
        assert agent.state.call_stack.peek().llm_messages[0].artifact == artifact

    def test_artifact_not_duplicated_when_already_loaded(self, agent, artifact):
        """Test that accessing artifact doesn't duplicate when already loaded."""
        # Store artifact in variables
        agent.state.variables.test_artifact = artifact

        # Manually load artifact first
        artifact_msg = ArtifactLLMMessage(artifact)
        agent.state.call_stack.add_llm_message(artifact_msg)

        # Verify artifact is loaded
        assert agent.state.call_stack.is_artifact_loaded("test_artifact")
        initial_message_count = len(agent.state.call_stack.peek().llm_messages)
        assert initial_message_count == 1

        # Access the artifact via ExpressionContext
        context = ExpressionContext(agent, agent.state, None)
        result = context.resolve_variable("test_artifact")

        # Verify artifact was returned
        assert isinstance(result, Artifact)
        assert result.name == "test_artifact"

        # Verify artifact was NOT duplicated
        assert len(agent.state.call_stack.peek().llm_messages) == initial_message_count

    def test_artifact_loaded_in_parent_frame_not_duplicated(self, agent, artifact):
        """Test that artifact loaded in parent frame is not duplicated."""
        # Store artifact in variables
        agent.state.variables.test_artifact = artifact

        # Load artifact in current (parent) frame
        artifact_msg = ArtifactLLMMessage(artifact)
        agent.state.call_stack.add_llm_message(artifact_msg)

        # Push a new child frame
        instruction_pointer = InstructionPointer("ChildPlaybook", "1", 1)
        child_frame = CallStackFrame(instruction_pointer)
        agent.state.call_stack.push(child_frame)

        # Verify artifact is loaded (in parent frame)
        assert agent.state.call_stack.is_artifact_loaded("test_artifact")
        child_message_count = len(agent.state.call_stack.peek().llm_messages)
        assert child_message_count == 0

        # Access the artifact from child frame
        context = ExpressionContext(agent, agent.state, None)
        result = context.resolve_variable("test_artifact")

        # Verify artifact was returned
        assert isinstance(result, Artifact)

        # Verify artifact was NOT added to child frame (already in parent)
        assert len(agent.state.call_stack.peek().llm_messages) == child_message_count

    def test_non_artifact_variable_not_auto_loaded(self, agent):
        """Test that non-artifact variables are not auto-loaded."""
        # Store regular variable
        agent.state.variables.regular_var = "regular value"

        # Access the variable via ExpressionContext
        context = ExpressionContext(agent, agent.state, None)
        result = context.resolve_variable("regular_var")

        # Verify variable was returned
        assert result == "regular value"

        # Verify no messages were added
        assert len(agent.state.call_stack.peek().llm_messages) == 0


class TestArtifactAutoLoadingStateAccess:
    """Test auto-loading via state.x access (Python execution)."""

    def test_artifact_auto_loads_from_state_access(self, agent, artifact):
        """Test that accessing artifact from state auto-loads it."""
        # Store artifact in variables
        agent.state.variables.test_artifact = artifact

        # Verify artifact is not loaded
        assert not agent.state.call_stack.is_artifact_loaded("test_artifact")
        assert len(agent.state.call_stack.peek().llm_messages) == 0

        # Access the artifact via state.x (simulates LLM code)
        result = agent.state.variables.test_artifact

        # Verify artifact was returned
        assert isinstance(result, Artifact)
        assert result.name == "test_artifact"

    def test_artifact_accessible_via_dict_and_attr(self, agent, artifact):
        """Test that artifacts work with both state.x and state['x'] access."""
        # Store artifact in variables
        agent.state.variables.test_artifact = artifact

        # Both access patterns should work
        result1 = agent.state.variables.test_artifact
        result2 = agent.state.variables["test_artifact"]

        assert result1 == result2
        assert isinstance(result1, Artifact)
        assert result1.name == "test_artifact"


class TestCallStackIsArtifactLoaded:
    """Test the is_artifact_loaded helper method."""

    def test_artifact_not_loaded_returns_false(self, agent):
        """Test that checking unloaded artifact returns False."""
        assert not agent.state.call_stack.is_artifact_loaded("test_artifact")

    def test_artifact_loaded_in_current_frame_returns_true(self, agent, artifact):
        """Test that artifact loaded in current frame is detected."""
        artifact_msg = ArtifactLLMMessage(artifact)
        agent.state.call_stack.add_llm_message(artifact_msg)

        assert agent.state.call_stack.is_artifact_loaded("test_artifact")

    def test_artifact_loaded_in_parent_frame_returns_true(self, agent, artifact):
        """Test that artifact loaded in parent frame is detected."""
        # Load artifact in current frame
        artifact_msg = ArtifactLLMMessage(artifact)
        agent.state.call_stack.add_llm_message(artifact_msg)

        # Push a new frame
        instruction_pointer = InstructionPointer("ChildPlaybook", "1", 1)
        child_frame = CallStackFrame(instruction_pointer)
        agent.state.call_stack.push(child_frame)

        # Verify artifact is detected (in parent frame)
        assert agent.state.call_stack.is_artifact_loaded("test_artifact")

    def test_different_artifact_returns_false(self, agent, artifact):
        """Test that checking for different artifact returns False."""
        artifact_msg = ArtifactLLMMessage(artifact)
        agent.state.call_stack.add_llm_message(artifact_msg)

        assert agent.state.call_stack.is_artifact_loaded("test_artifact")
        assert not agent.state.call_stack.is_artifact_loaded("other_artifact")


class TestMultipleArtifacts:
    """Test auto-loading with multiple artifacts."""

    def test_multiple_artifacts_auto_load_independently(self, agent):
        """Test that multiple artifacts auto-load independently."""
        # Create multiple artifacts
        artifact1 = Artifact("artifact1", "First artifact", "Content 1")
        artifact2 = Artifact("artifact2", "Second artifact", "Content 2")

        agent.state.variables.artifact1 = artifact1
        agent.state.variables.artifact2 = artifact2

        # Verify neither is loaded
        assert not agent.state.call_stack.is_artifact_loaded("artifact1")
        assert not agent.state.call_stack.is_artifact_loaded("artifact2")

        # Access first artifact
        context = ExpressionContext(agent, agent.state, None)
        context.resolve_variable("artifact1")

        # Verify first is loaded, second is not
        assert agent.state.call_stack.is_artifact_loaded("artifact1")
        assert not agent.state.call_stack.is_artifact_loaded("artifact2")
        assert len(agent.state.call_stack.peek().llm_messages) == 1

        # Access second artifact
        context.resolve_variable("artifact2")

        # Verify both are loaded
        assert agent.state.call_stack.is_artifact_loaded("artifact1")
        assert agent.state.call_stack.is_artifact_loaded("artifact2")
        assert len(agent.state.call_stack.peek().llm_messages) == 2

    def test_accessing_same_artifact_multiple_times(self, agent, artifact):
        """Test that accessing same artifact multiple times doesn't duplicate."""
        agent.state.variables.test_artifact = artifact

        context = ExpressionContext(agent, agent.state, None)

        # Access artifact multiple times
        result1 = context.resolve_variable("test_artifact")
        result2 = context.resolve_variable("test_artifact")
        result3 = context.resolve_variable("test_artifact")

        # Verify all returned the artifact
        assert all(isinstance(r, Artifact) for r in [result1, result2, result3])

        # Verify artifact was only loaded once
        assert len(agent.state.call_stack.peek().llm_messages) == 1
        assert isinstance(
            agent.state.call_stack.peek().llm_messages[0], ArtifactLLMMessage
        )
