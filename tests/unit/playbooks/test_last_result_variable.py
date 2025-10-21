"""Tests for $_ variable that captures last playbook call result."""

from unittest.mock import Mock

import pytest

from playbooks.agents.ai_agent import AIAgent
from playbooks.call_stack import CallStackFrame, InstructionPointer
from playbooks.config import config
from playbooks.event_bus import EventBus
from playbooks.execution_state import ExecutionState
from playbooks.playbook_call import PlaybookCall
from playbooks.program import Program
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
    """Create a mock event bus for testing."""
    return Mock(spec=EventBus)


@pytest.fixture
def program(event_bus):
    """Create a mock program for testing."""
    return Mock(spec=Program)


@pytest.fixture
def agent(event_bus):
    """Create a mock agent with execution state."""
    agent = MockAIAgent(event_bus)
    agent.state = ExecutionState(event_bus, "MockAIAgent", "test-agent-id")

    # Initialize $__ variable as required
    mock_execution_summary = Mock()
    mock_execution_summary.value = "test execution"
    agent.state.variables.variables["$__"] = mock_execution_summary

    # Push a frame onto the call stack so we can add messages to it
    instruction_pointer = InstructionPointer("TestPlaybook", "1", 1)
    frame = CallStackFrame(instruction_pointer)
    agent.state.call_stack.push(frame)

    return agent


class TestLastResultVariable:
    """Test $_ variable functionality."""

    @pytest.mark.asyncio
    async def test_underscore_set_after_say_short_content(self, agent):
        """Test that $_ is set after Say() call with short content."""
        short_message = "Hello, world!"  # < 200 chars

        # Create a playbook call for Say
        call = PlaybookCall("Say", ["user", short_message], {})

        # Simulate _post_execute with short result
        await agent._post_execute(call, True, short_message, Mock())

        # Verify $_ contains the message
        assert "$_" in agent.state.variables
        assert agent.state.variables["$_"].value == short_message

    @pytest.mark.asyncio
    async def test_underscore_contains_artifact_when_content_over_threshold(
        self, agent
    ):
        """Test that $_ contains artifact when Say() content > threshold."""
        # Create long content exceeding threshold
        long_message = "x" * (config.artifact_result_threshold + 1)

        # Create a playbook call for Say
        call = PlaybookCall("Say", ["user", long_message], {})

        # Simulate _post_execute with long result
        await agent._post_execute(call, True, long_message, Mock())

        # Verify $_ contains an Artifact
        assert "$_" in agent.state.variables
        underscore_value = agent.state.variables["$_"].value
        assert isinstance(underscore_value, Artifact)
        assert underscore_value.value == long_message
        assert "Output from Say()" in underscore_value.summary

    @pytest.mark.asyncio
    async def test_var_assignment_with_underscore_captures_value(self, agent):
        """Test that Var[$answer, $_] correctly captures and assigns the value."""
        from playbooks.llm_response_line import LLMResponseLine

        # First, set $_ with a short value
        short_result = "Test result"
        call = PlaybookCall("Say", ["user", short_result], {})
        await agent._post_execute(call, True, short_result, Mock())

        # Now parse a Var assignment that references $_
        line = await LLMResponseLine.create(
            "`Var[$answer, $_]`", agent.state.event_bus, agent
        )

        # Verify $answer was assigned the value from $_
        assert "$answer" in line.vars
        assert line.vars["$answer"].value == short_result

    @pytest.mark.asyncio
    async def test_var_assignment_with_underscore_captures_artifact(self, agent):
        """Test that Var[$answer, $_] correctly captures and assigns an artifact."""
        from playbooks.llm_response_line import LLMResponseLine

        # First, set $_ with a long value that becomes an artifact
        long_result = "x" * (config.artifact_result_threshold + 1)
        call = PlaybookCall("Say", ["user", long_result], {})
        await agent._post_execute(call, True, long_result, Mock())

        # Verify $_ contains an artifact
        assert "$_" in agent.state.variables
        artifact = agent.state.variables["$_"].value
        assert isinstance(artifact, Artifact)

        # Now parse a Var assignment that references $_
        line = await LLMResponseLine.create(
            "`Var[$answer, $_]`", agent.state.event_bus, agent
        )

        # Verify $answer was assigned the artifact from $_
        assert "$answer" in line.vars
        assert isinstance(line.vars["$answer"].value, Artifact)
        assert line.vars["$answer"].value == artifact

    @pytest.mark.asyncio
    async def test_underscore_set_after_any_playbook_call(self, agent):
        """Test that $_ is set after any playbook call, not just Say()."""
        # Create a playbook call for a different function
        result_value = "custom result"
        call = PlaybookCall("CustomPlaybook", [], {})

        # Simulate _post_execute
        await agent._post_execute(call, True, result_value, Mock())

        # Verify $_ contains the result
        assert "$_" in agent.state.variables
        assert agent.state.variables["$_"].value == result_value

    @pytest.mark.asyncio
    async def test_full_pattern_say_var_return(self, agent):
        """Test full pattern: Say() → stream → Var with $_ → Return artifact."""
        from playbooks.llm_response_line import LLMResponseLine

        # Step 1: Say() with long content (will create artifact)
        long_answer = "x" * (config.artifact_result_threshold + 1)
        say_call = PlaybookCall("Say", ["user", long_answer], {})
        await agent._post_execute(say_call, True, long_answer, Mock())

        # Verify artifact was created and stored in $_
        assert "$_" in agent.state.variables
        underscore_artifact = agent.state.variables["$_"].value
        assert isinstance(underscore_artifact, Artifact)

        # Step 2: Var[$answer, $_] to capture the artifact
        var_line = await LLMResponseLine.create(
            "`Var[$answer, $_]`", agent.state.event_bus, agent
        )

        # Verify $answer has the artifact
        assert "$answer" in var_line.vars
        answer_artifact = var_line.vars["$answer"].value
        assert isinstance(answer_artifact, Artifact)
        assert answer_artifact == underscore_artifact

        # Step 3: Return[$answer] would return the artifact
        # This is handled by the Return parsing, but we can verify the variable exists
        assert answer_artifact.value == long_answer

    @pytest.mark.asyncio
    async def test_underscore_overwritten_by_subsequent_calls(self, agent):
        """Test that $_ is overwritten by subsequent playbook calls."""
        # First call
        result1 = "first result"
        call1 = PlaybookCall("Playbook1", [], {})
        await agent._post_execute(call1, True, result1, Mock())

        assert agent.state.variables["$_"].value == result1

        # Second call
        result2 = "second result"
        call2 = PlaybookCall("Playbook2", [], {})
        await agent._post_execute(call2, True, result2, Mock())

        # Verify $_ now contains the second result
        assert agent.state.variables["$_"].value == result2

    @pytest.mark.asyncio
    async def test_underscore_with_returned_artifact(self, agent):
        """Test that $_ is set correctly when playbook returns an artifact object."""
        # Create an artifact to return
        returned_artifact = Artifact(
            name="test_artifact", summary="Test artifact", value="artifact content"
        )

        call = PlaybookCall("PlaybookReturningArtifact", [], {})
        await agent._post_execute(call, True, returned_artifact, Mock())

        # Verify $_ contains the artifact
        assert "$_" in agent.state.variables
        assert agent.state.variables["$_"].value == returned_artifact

    @pytest.mark.asyncio
    async def test_var_assignment_with_missing_underscore(self, agent):
        """Test that Var assignment with $_ handles missing variable gracefully."""
        from playbooks.llm_response_line import LLMResponseLine

        # Don't set $_ first

        # Try to parse a Var assignment that references $_
        line = await LLMResponseLine.create(
            "`Var[$answer, $_]`", agent.state.event_bus, agent
        )

        # When variable is not found, it should store the reference as-is
        assert "$answer" in line.vars
        # The value should be the string "$_" since it couldn't be resolved
        assert line.vars["$answer"].value == "$_"

    @pytest.mark.asyncio
    async def test_underscore_with_none_result(self, agent):
        """Test that $_ is set to None when playbook returns None."""
        call = PlaybookCall("PlaybookReturningNone", [], {})
        await agent._post_execute(call, True, None, Mock())

        # Verify $_ contains None
        assert "$_" in agent.state.variables
        assert agent.state.variables["$_"].value is None

    @pytest.mark.asyncio
    async def test_token_efficiency_pattern(self, agent):
        """Test that the pattern achieves token efficiency (content written once)."""
        from playbooks.llm_response_line import LLMResponseLine

        # Simulate the scenario from the problem statement:
        # Generate a long form response, save it as artifact and return

        long_content = "A" * (config.artifact_result_threshold + 1)

        # Old inefficient way would require writing content twice:
        # `Say("user", "<content>")` `Var[$answer, """Summary\n---\n<content>"""]` `Return[$answer]`
        # Content appears twice!

        # New efficient way:
        # `Say("user", "<content>")` `Var[$answer, $_]` `Return[$answer]`
        # Content appears only once!

        # Step 1: Say generates and streams the content
        say_call = PlaybookCall("Say", ["user", long_content], {})
        await agent._post_execute(say_call, True, long_content, Mock())

        # Step 2: Var captures from $_
        var_line = await LLMResponseLine.create(
            "`Var[$answer, $_]`", agent.state.event_bus, agent
        )

        # Verify: The artifact exists and contains the content
        assert "$answer" in var_line.vars
        final_artifact = var_line.vars["$answer"].value
        assert isinstance(final_artifact, Artifact)
        assert final_artifact.value == long_content

        # Success: Content was written once (in Say call), but captured in artifact
        # This saves tokens since LLM doesn't need to generate the content twice
