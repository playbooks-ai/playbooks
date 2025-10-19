"""Tests for automatic artifact creation when playbook results exceed 80 characters."""

from unittest.mock import Mock, patch

import pytest

from playbooks.agents.ai_agent import AIAgent
from playbooks.call_stack import CallStackFrame, InstructionPointer
from playbooks.event_bus import EventBus
from playbooks.execution_state import ExecutionState
from playbooks.llm_messages.types import ArtifactLLMMessage
from playbooks.playbook_call import PlaybookCall, PlaybookCallResult


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


class TestPlaybookResultArtifacts:
    """Test automatic artifact creation for large playbook results."""

    @pytest.mark.asyncio
    async def test_result_over_80_chars_creates_artifact(self, agent, playbook_call):
        """Test that results over 80 characters automatically create an artifact."""
        long_result = "x" * 81  # 81 characters

        with patch("playbooks.agents.ai_agent.uuid.uuid4") as mock_uuid:
            mock_uuid.return_value = "test-uuid-1234"

            await agent._post_execute(playbook_call, True, long_result, Mock())

            # Verify artifact was created
            expected_artifact_name = "$TestPlaybook_test-uuid-1234_result_artifact"
            assert expected_artifact_name in agent.state.artifacts

        # Verify artifact content
        artifact = agent.state.artifacts[expected_artifact_name]
        assert artifact.content == long_result
        assert artifact.summary.startswith("Result of TestPlaybook")

    @pytest.mark.asyncio
    async def test_result_exactly_80_chars_no_artifact(self, agent, playbook_call):
        """Test that results of exactly 80 characters do NOT create an artifact."""
        exact_result = "x" * 80  # Exactly 80 characters

        await agent._post_execute(playbook_call, True, exact_result, Mock())

        # Verify no artifact was created
        assert len(agent.state.artifacts) == 0

    @pytest.mark.asyncio
    async def test_result_under_80_chars_no_artifact(self, agent, playbook_call):
        """Test that results under 80 characters do NOT create an artifact."""
        short_result = "short result"

        await agent._post_execute(playbook_call, True, short_result, Mock())

        # Verify no artifact was created
        assert len(agent.state.artifacts) == 0

    @pytest.mark.asyncio
    async def test_failure_with_long_result_no_artifact(self, agent, playbook_call):
        """Test that failed executions don't create artifacts even with long results."""
        long_result = "x" * 200  # Very long result

        await agent._post_execute(playbook_call, False, long_result, Mock())

        # Verify no artifact was created
        assert len(agent.state.artifacts) == 0

    @pytest.mark.asyncio
    async def test_artifact_name_format(self, agent, playbook_call):
        """Test that artifact names follow the correct format."""
        long_result = "x" * 100

        with patch("playbooks.agents.ai_agent.uuid.uuid4") as mock_uuid:
            mock_uuid.return_value = "custom-uuid-5678"

            await agent._post_execute(playbook_call, True, long_result, Mock())

            # Verify artifact name format
            expected_name = "$TestPlaybook_custom-uuid-5678_result_artifact"
            assert expected_name in agent.state.artifacts

    @pytest.mark.asyncio
    async def test_artifact_summary_format(self, agent):
        """Test that artifact summaries contain the correct information."""
        # Create a playbook call with specific args and kwargs
        call = PlaybookCall("MyPlaybook", ["arg1", "arg2"], {"key": "value"})
        long_result = "x" * 100

        await agent._post_execute(call, True, long_result, Mock())

        # Get the created artifact
        artifacts_list = list(agent.state.artifacts.artifacts.values())
        assert len(artifacts_list) == 1

        artifact = artifacts_list[0]
        assert artifact.summary.startswith("Result of MyPlaybook")

    @pytest.mark.asyncio
    async def test_artifact_llm_message_added_to_call_stack(self, agent, playbook_call):
        """Test that an ArtifactLLMMessage is added to the call stack."""
        long_result = "x" * 100

        # Push an extra frame since post_execute will pop one
        instruction_pointer = InstructionPointer("TestPlaybook2", "1", 1)
        frame = CallStackFrame(instruction_pointer)
        agent.state.call_stack.push(frame)

        initial_message_count = len(agent.state.call_stack.peek().llm_messages)

        await agent._post_execute(playbook_call, True, long_result, Mock())

        # Get the messages from the call stack (after pop)
        final_messages = agent.state.call_stack.peek().llm_messages

        # Should have added ArtifactLLMMessage and ExecutionResultLLMMessage
        assert len(final_messages) == initial_message_count + 2

        # Check that one of the new messages is an ArtifactLLMMessage
        artifact_messages = [
            msg for msg in final_messages if isinstance(msg, ArtifactLLMMessage)
        ]
        assert len(artifact_messages) == 1

    @pytest.mark.asyncio
    async def test_playbook_call_result_contains_artifact_name(
        self, agent, playbook_call
    ):
        """Test that PlaybookCallResult contains the artifact name instead of the result."""
        long_result = "x" * 100

        with patch("playbooks.agents.ai_agent.uuid.uuid4") as mock_uuid:
            mock_uuid.return_value = "uuid-for-result"

            await agent._post_execute(playbook_call, True, long_result, Mock())

            # Get the last session log item (should be PlaybookCallResult)
            session_log_items = agent.state.session_log.log
            assert len(session_log_items) > 0

            call_result = session_log_items[-1]["item"]
            assert isinstance(call_result, PlaybookCallResult)

            # Verify result is the artifact name, not the actual result
            expected_artifact_name = "$TestPlaybook_uuid-for-result_result_artifact"
            assert call_result.result == expected_artifact_name
            assert call_result.result != long_result

    @pytest.mark.asyncio
    async def test_no_artifact_llm_message_for_short_result(self, agent, playbook_call):
        """Test that no ArtifactLLMMessage is added for short results."""
        short_result = "short"

        # Push an extra frame since post_execute will pop one
        instruction_pointer = InstructionPointer("TestPlaybook2", "1", 1)
        frame = CallStackFrame(instruction_pointer)
        agent.state.call_stack.push(frame)

        initial_message_count = len(agent.state.call_stack.peek().llm_messages)

        await agent._post_execute(playbook_call, True, short_result, Mock())

        # Get the messages from the call stack (after pop)
        final_messages = agent.state.call_stack.peek().llm_messages

        # Should have added only ExecutionResultLLMMessage (not ArtifactLLMMessage)
        assert len(final_messages) == initial_message_count + 1

        # Verify no ArtifactLLMMessage was added
        artifact_messages = [
            msg for msg in final_messages if isinstance(msg, ArtifactLLMMessage)
        ]
        assert len(artifact_messages) == 0

    @pytest.mark.asyncio
    async def test_multiple_long_results_create_unique_artifacts(self, agent):
        """Test that multiple long results create separate artifacts with unique names."""
        call1 = PlaybookCall("Playbook1", [], {})
        call2 = PlaybookCall("Playbook2", [], {})

        result1 = "x" * 100
        result2 = "y" * 100

        # Push another frame for the second call
        instruction_pointer = InstructionPointer("Playbook2", "1", 1)
        frame = CallStackFrame(instruction_pointer)
        agent.state.call_stack.push(frame)

        await agent._post_execute(call1, True, result1, Mock())
        await agent._post_execute(call2, True, result2, Mock())

        # Verify two artifacts were created
        assert len(agent.state.artifacts) == 2

        # Verify artifacts have unique names
        artifact_names = list(agent.state.artifacts.artifacts.keys())
        assert artifact_names[0] != artifact_names[1]

        # Verify first artifact contains result1
        first_artifact = agent.state.artifacts[artifact_names[0]]
        assert first_artifact.content == result1

        # Verify second artifact contains result2
        second_artifact = agent.state.artifacts[artifact_names[1]]
        assert second_artifact.content == result2

    @pytest.mark.asyncio
    async def test_artifact_stores_string_representation(self, agent, playbook_call):
        """Test that artifacts store the string representation of non-string results."""
        # Test with a dict result
        dict_result = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
            "key4": "value4",
            "key5": "value5",
        }  # > 80 chars when stringified

        await agent._post_execute(playbook_call, True, dict_result, Mock())

        # Verify artifact was created
        artifacts_list = list(agent.state.artifacts.artifacts.values())
        assert len(artifacts_list) == 1

        artifact = artifacts_list[0]
        # Verify content is string representation
        assert artifact.content == str(dict_result)
        assert isinstance(artifact.content, str)

    @pytest.mark.asyncio
    async def test_artifact_with_list_result(self, agent, playbook_call):
        """Test artifact creation with a list result."""
        # Create a list that's > 80 chars when stringified
        list_result = [
            "item1",
            "item2",
            "item3",
            "item4",
            "item5",
            "item6",
            "item7",
            "item8",
            "item9",
        ]

        await agent._post_execute(playbook_call, True, list_result, Mock())

        # Verify artifact was created
        artifacts_list = list(agent.state.artifacts.artifacts.values())
        assert len(artifacts_list) == 1

        artifact = artifacts_list[0]
        assert artifact.content == str(list_result)

    @pytest.mark.asyncio
    async def test_artifact_with_none_result_no_artifact(self, agent, playbook_call):
        """Test that None results don't create artifacts."""
        await agent._post_execute(playbook_call, True, None, Mock())

        # Verify no artifact was created
        assert len(agent.state.artifacts) == 0

    @pytest.mark.asyncio
    async def test_artifact_with_empty_string_no_artifact(self, agent, playbook_call):
        """Test that empty strings don't create artifacts."""
        await agent._post_execute(playbook_call, True, "", Mock())

        # Verify no artifact was created
        assert len(agent.state.artifacts) == 0

    @pytest.mark.asyncio
    async def test_langfuse_span_updated_with_artifact_content(
        self, agent, playbook_call
    ):
        """Test that langfuse span is updated with artifact content for long results."""
        long_result = "x" * 100
        mock_langfuse_span = Mock()

        with patch("playbooks.agents.ai_agent.uuid.uuid4") as mock_uuid:
            mock_uuid.return_value = "test-uuid"

            await agent._post_execute(
                playbook_call, True, long_result, mock_langfuse_span
            )

            # For artifact results, langfuse should be updated with result.content
            # But result is now the artifact name (string), so it should get the string
            mock_langfuse_span.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_log_contains_call_result(self, agent, playbook_call):
        """Test that session log contains the PlaybookCallResult."""
        long_result = "x" * 100

        initial_log_length = len(agent.state.session_log.log)

        await agent._post_execute(playbook_call, True, long_result, Mock())

        # Verify session log was updated
        assert len(agent.state.session_log.log) == initial_log_length + 1

        # Verify the last item is a PlaybookCallResult
        last_item = agent.state.session_log.log[-1]["item"]
        assert isinstance(last_item, PlaybookCallResult)
        assert last_item.call == playbook_call

    @pytest.mark.asyncio
    async def test_call_stack_popped_after_post_execute(self, agent, playbook_call):
        """Test that the call stack is popped after post_execute."""
        initial_depth = len(agent.state.call_stack.frames)
        long_result = "x" * 100

        await agent._post_execute(playbook_call, True, long_result, Mock())

        # Verify call stack was popped
        assert len(agent.state.call_stack.frames) == initial_depth - 1

    @pytest.mark.asyncio
    async def test_artifact_content_preservation(self, agent, playbook_call):
        """Test that artifact preserves exact content including whitespace."""
        # Result with special characters and whitespace
        special_result = (
            "Line 1\n\tLine 2 with tabs\n    Line 3 with spaces\nLine 4" * 3
        )

        await agent._post_execute(playbook_call, True, special_result, Mock())

        # Get the created artifact
        artifacts_list = list(agent.state.artifacts.artifacts.values())
        artifact = artifacts_list[0]

        # Verify exact content preservation
        assert artifact.content == special_result

    @pytest.mark.asyncio
    async def test_boundary_79_chars_no_artifact(self, agent, playbook_call):
        """Test the boundary condition of 79 characters (just under threshold)."""
        result_79_chars = "x" * 79

        await agent._post_execute(playbook_call, True, result_79_chars, Mock())

        # Verify no artifact was created
        assert len(agent.state.artifacts) == 0

    @pytest.mark.asyncio
    async def test_boundary_81_chars_creates_artifact(self, agent, playbook_call):
        """Test the boundary condition of 81 characters (just over threshold)."""
        result_81_chars = "x" * 81

        await agent._post_execute(playbook_call, True, result_81_chars, Mock())

        # Verify artifact was created
        assert len(agent.state.artifacts) == 1

    @pytest.mark.asyncio
    async def test_config_threshold_override(self, agent, playbook_call):
        """Test that the config threshold can be overridden."""
        from playbooks.config import config

        # Store original value
        original_threshold = config.artifact_result_threshold

        try:
            # Override to a very low threshold
            config.artifact_result_threshold = 10

            result_11_chars = "x" * 11  # Just over new threshold

            await agent._post_execute(playbook_call, True, result_11_chars, Mock())

            # Should create artifact with the lower threshold
            assert len(agent.state.artifacts) == 1

            # Reset and test with value under threshold
            agent.state.artifacts.artifacts.clear()

            result_10_chars = "x" * 10  # Exactly at threshold
            await agent._post_execute(playbook_call, True, result_10_chars, Mock())

            # Should NOT create artifact
            assert len(agent.state.artifacts) == 0

        finally:
            # Restore original
            config.artifact_result_threshold = original_threshold

    @pytest.mark.asyncio
    async def test_artifact_message_content_format(self, agent, playbook_call):
        """Test that ArtifactLLMMessage has correct content format."""
        long_result = "x" * 100

        # Push an extra frame since post_execute will pop one
        instruction_pointer = InstructionPointer("TestPlaybook2", "1", 1)
        frame = CallStackFrame(instruction_pointer)
        agent.state.call_stack.push(frame)

        with patch("playbooks.agents.ai_agent.uuid.uuid4") as mock_uuid:
            mock_uuid.return_value = "test-uuid"

            await agent._post_execute(playbook_call, True, long_result, Mock())

            # Get the ArtifactLLMMessage from call stack (after pop)
            messages = agent.state.call_stack.peek().llm_messages
            artifact_messages = [
                msg for msg in messages if isinstance(msg, ArtifactLLMMessage)
            ]

            assert len(artifact_messages) == 1
            artifact_msg = artifact_messages[0]

            # Verify the message content includes the artifact details
            expected_artifact_name = "$TestPlaybook_test-uuid_result_artifact"
            assert expected_artifact_name in artifact_msg.content
            assert "Summary:" in artifact_msg.content
            assert long_result in artifact_msg.content
