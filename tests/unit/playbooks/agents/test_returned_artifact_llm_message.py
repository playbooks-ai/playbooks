"""Tests for artifacts returned from playbooks having ArtifactLLMMessage preserved."""

from unittest.mock import Mock

import pytest

from playbooks.agents.ai_agent import AIAgent
from playbooks.call_stack import CallStackFrame, InstructionPointer
from playbooks.event_bus import EventBus
from playbooks.execution_state import ExecutionState
from playbooks.llm_messages.types import ArtifactLLMMessage
from playbooks.playbook_call import PlaybookCall
from playbooks.variables import Artifact


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

    # Push a frame onto the call stack so we can add messages to it
    instruction_pointer = InstructionPointer("TestPlaybook", "1", 1)
    frame = CallStackFrame(instruction_pointer)
    agent.state.call_stack.push(frame)

    return agent


@pytest.fixture
def playbook_call():
    """Create a sample playbook call."""
    return PlaybookCall("TestPlaybook", ["arg1"], {"key1": "value1"})


class TestReturnedArtifactLLMMessage:
    """Test that returned artifacts get an ArtifactLLMMessage in the calling frame."""

    @pytest.mark.asyncio
    async def test_returned_artifact_creates_llm_message(self, agent, playbook_call):
        """Test that when a playbook returns an Artifact, an ArtifactLLMMessage is added."""
        # Create an artifact that will be returned
        artifact = Artifact(
            name="test_artifact",
            summary="Test artifact summary",
            value="This is the artifact content.",
        )

        # Store it in variables
        agent.state.variables["$test_artifact"] = artifact

        # Push an extra frame since post_execute will pop one
        instruction_pointer = InstructionPointer("TestPlaybook2", "1", 1)
        frame = CallStackFrame(instruction_pointer)
        agent.state.call_stack.push(frame)

        initial_message_count = len(agent.state.call_stack.peek().llm_messages)

        # The playbook returns an artifact object
        await agent._post_execute(playbook_call, True, artifact, Mock())

        # Get the messages from the call stack (after pop)
        final_messages = agent.state.call_stack.peek().llm_messages

        # Should have added ArtifactLLMMessage and ExecutionResultLLMMessage
        assert len(final_messages) == initial_message_count + 2

        # Check that one of the new messages is an ArtifactLLMMessage
        artifact_messages = [
            msg for msg in final_messages if isinstance(msg, ArtifactLLMMessage)
        ]
        assert len(artifact_messages) == 1

        # Verify it's the correct artifact
        assert artifact_messages[0].artifact == artifact

    @pytest.mark.asyncio
    async def test_returned_artifact_preserves_artifact_details(
        self, agent, playbook_call
    ):
        """Test that the artifact's details are preserved in the LLM message."""
        # Create an artifact with specific content
        artifact = Artifact(
            name="detailed_artifact",
            summary="Detailed summary of the artifact",
            value="Very detailed content\nWith multiple lines\nAnd information.",
        )

        agent.state.variables["$detailed_artifact"] = artifact

        # Push an extra frame
        instruction_pointer = InstructionPointer("TestPlaybook2", "1", 1)
        frame = CallStackFrame(instruction_pointer)
        agent.state.call_stack.push(frame)

        await agent._post_execute(playbook_call, True, artifact, Mock())

        # Get the artifact message
        final_messages = agent.state.call_stack.peek().llm_messages
        artifact_messages = [
            msg for msg in final_messages if isinstance(msg, ArtifactLLMMessage)
        ]

        # Verify the content includes all artifact details
        artifact_msg = artifact_messages[0]
        assert "detailed_artifact" in artifact_msg.content
        assert "Detailed summary of the artifact" in artifact_msg.content
        assert "Very detailed content" in artifact_msg.content
        assert "With multiple lines" in artifact_msg.content

    @pytest.mark.asyncio
    async def test_non_artifact_result_no_extra_message(self, agent, playbook_call):
        """Test that non-artifact results don't add an ArtifactLLMMessage."""
        # Regular string result (short, so no auto-artifact creation)
        result = "short result"

        # Push an extra frame
        instruction_pointer = InstructionPointer("TestPlaybook2", "1", 1)
        frame = CallStackFrame(instruction_pointer)
        agent.state.call_stack.push(frame)

        initial_message_count = len(agent.state.call_stack.peek().llm_messages)

        await agent._post_execute(playbook_call, True, result, Mock())

        # Get the messages from the call stack
        final_messages = agent.state.call_stack.peek().llm_messages

        # Should only have ExecutionResultLLMMessage, not ArtifactLLMMessage
        assert len(final_messages) == initial_message_count + 1

        # Verify no ArtifactLLMMessage was added
        artifact_messages = [
            msg for msg in final_messages if isinstance(msg, ArtifactLLMMessage)
        ]
        assert len(artifact_messages) == 0

    @pytest.mark.asyncio
    async def test_returned_artifact_from_variable_assignment(self, agent):
        """Test artifact return when assigned to a variable."""
        # Create a playbook call with variable assignment
        call = PlaybookCall(
            "GetArtifact",
            [],
            {},
            variable_to_assign="$my_artifact",
            type_annotation=None,
        )

        artifact = Artifact(
            name="my_artifact",
            summary="My artifact summary",
            value="Content of my artifact",
        )

        agent.state.variables["$my_artifact"] = artifact

        # Push an extra frame
        instruction_pointer = InstructionPointer("TestPlaybook2", "1", 1)
        frame = CallStackFrame(instruction_pointer)
        agent.state.call_stack.push(frame)

        await agent._post_execute(call, True, artifact, Mock())

        # Check that ArtifactLLMMessage was added
        final_messages = agent.state.call_stack.peek().llm_messages
        artifact_messages = [
            msg for msg in final_messages if isinstance(msg, ArtifactLLMMessage)
        ]

        assert len(artifact_messages) == 1
        assert artifact_messages[0].artifact == artifact

    @pytest.mark.asyncio
    async def test_auto_created_artifact_still_works(self, agent, playbook_call):
        """Test that auto-created artifacts (from long results) still work correctly."""
        # Long result that should trigger auto-artifact creation
        long_result = "x" * 100

        # Push an extra frame
        instruction_pointer = InstructionPointer("TestPlaybook2", "1", 1)
        frame = CallStackFrame(instruction_pointer)
        agent.state.call_stack.push(frame)

        await agent._post_execute(playbook_call, True, long_result, Mock())

        # Should have ArtifactLLMMessage
        final_messages = agent.state.call_stack.peek().llm_messages
        artifact_messages = [
            msg for msg in final_messages if isinstance(msg, ArtifactLLMMessage)
        ]

        assert len(artifact_messages) == 1

    @pytest.mark.asyncio
    async def test_failed_execution_with_artifact_no_message(
        self, agent, playbook_call
    ):
        """Test that failed executions don't add ArtifactLLMMessage even if result is an artifact."""
        artifact = Artifact(
            name="failed_artifact",
            summary="Should not be added",
            value="This shouldn't create a message",
        )

        # Push an extra frame
        instruction_pointer = InstructionPointer("TestPlaybook2", "1", 1)
        frame = CallStackFrame(instruction_pointer)
        agent.state.call_stack.push(frame)

        initial_message_count = len(agent.state.call_stack.peek().llm_messages)

        # Failed execution
        await agent._post_execute(playbook_call, False, artifact, Mock())

        # Should only have ExecutionResultLLMMessage, not ArtifactLLMMessage
        final_messages = agent.state.call_stack.peek().llm_messages
        assert len(final_messages) == initial_message_count + 1

        artifact_messages = [
            msg for msg in final_messages if isinstance(msg, ArtifactLLMMessage)
        ]
        assert len(artifact_messages) == 0
