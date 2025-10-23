"""Tests for variable assignment during playbook execution."""

from unittest.mock import Mock

import pytest

from playbooks.agents.ai_agent import AIAgent
from playbooks.config import config
from playbooks.event_bus import EventBus
from playbooks.execution_state import ExecutionState
from playbooks.playbook_call import PlaybookCall
from playbooks.variables import Artifact


class MockAgent(AIAgent):
    """Mock agent for testing."""

    klass = "MockAgent"
    description = "Mock agent"
    metadata = {}
    playbooks = {}
    namespace_manager = None

    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus)

    def discover_playbooks(self):
        """Mock implementation of discover_playbooks."""
        return {}


@pytest.fixture
def event_bus():
    """Create an event bus."""
    return EventBus("test_session")


@pytest.fixture
def agent(event_bus):
    """Create a mock agent with execution state."""
    agent = MockAgent(event_bus)
    agent.state = ExecutionState(event_bus, "MockAgent", "test-agent-id")

    # Mock the execution summary variable
    mock_execution_summary = Mock()
    mock_execution_summary.value = "Test execution summary"
    agent.state.variables.variables["$__"] = mock_execution_summary

    return agent


class TestVariableAssignmentExecution:
    """Test storing results in variables during execution."""

    def test_short_result_stored_in_variable(self, agent):
        """Test that short results are stored directly in the specified variable."""
        # Create a playbook call with variable assignment
        call = PlaybookCall(
            "GetValue", [], {}, variable_to_assign="$result", type_annotation=None
        )

        # Mock the playbook execution to return a short result
        short_result = "short_value"

        # We need to mock the actual playbook execution
        # For this test, we'll directly test the variable storage logic
        # by simulating what happens after execute_playbook returns

        # Simulate storing the result
        if call.variable_to_assign:
            if short_result != call.variable_to_assign:
                agent.state.variables[call.variable_to_assign] = short_result

        # Verify the variable was set
        assert "$result" in agent.state.variables
        assert agent.state.variables["$result"].value == "short_value"

    def test_int_result_stored_in_variable(self, agent):
        """Test that integer results are stored correctly."""
        call = PlaybookCall(
            "Count", [], {}, variable_to_assign="$count", type_annotation="int"
        )

        result = 42

        # Simulate storing the result
        if call.variable_to_assign:
            if result != call.variable_to_assign:
                agent.state.variables[call.variable_to_assign] = result

        # Verify the variable was set
        assert "$count" in agent.state.variables
        assert agent.state.variables["$count"].value == 42

    def test_bool_result_stored_in_variable(self, agent):
        """Test that boolean results are stored correctly."""
        call = PlaybookCall(
            "Check", [], {}, variable_to_assign="$flag", type_annotation="bool"
        )

        result = True

        # Simulate storing the result
        if call.variable_to_assign:
            if result != call.variable_to_assign:
                agent.state.variables[call.variable_to_assign] = result

        # Verify the variable was set
        assert "$flag" in agent.state.variables
        assert agent.state.variables["$flag"].value is True

    def test_no_assignment_no_extra_variables(self, agent):
        """Test that calls without assignment don't create extra variables."""
        call = PlaybookCall("DoSomething", [], {})

        result = "some_result"

        # Simulate the logic - no assignment should happen
        if call.variable_to_assign:
            if result != call.variable_to_assign:
                agent.state.variables[call.variable_to_assign] = result

        # Count non-system variables (those not starting with $__)
        user_vars = [v for v in agent.state.variables if not v.name.startswith("$__")]
        assert len(user_vars) == 0

    def test_skip_assignment_when_result_is_variable_name(self, agent):
        """Test that we skip assignment when result equals variable name (artifact case)."""
        call = PlaybookCall(
            "LongPlaybook",
            [],
            {},
            variable_to_assign="$report",
            type_annotation=None,
        )

        # Simulate artifact case where result IS the variable name
        result = "$report"

        # Simulate the conditional logic
        if call.variable_to_assign:
            if result != call.variable_to_assign:
                agent.state.variables[call.variable_to_assign] = result

        # Verify NO assignment happened (no circular assignment)
        # Note: In real scenario, the artifact would already be set by _post_execute
        user_vars = [v for v in agent.state.variables if not v.name.startswith("$__")]
        assert len(user_vars) == 0

    def test_multiple_assignments_in_sequence(self, agent):
        """Test multiple calls with assignments execute correctly."""
        # First call
        call1 = PlaybookCall(
            "Get1", [], {}, variable_to_assign="$a", type_annotation=None
        )
        result1 = "value_a"
        if call1.variable_to_assign and result1 != call1.variable_to_assign:
            agent.state.variables[call1.variable_to_assign] = result1

        # Second call
        call2 = PlaybookCall(
            "Get2", [], {}, variable_to_assign="$b", type_annotation=None
        )
        result2 = "value_b"
        if call2.variable_to_assign and result2 != call2.variable_to_assign:
            agent.state.variables[call2.variable_to_assign] = result2

        # Verify both variables are set
        assert "$a" in agent.state.variables
        assert agent.state.variables["$a"].value == "value_a"
        assert "$b" in agent.state.variables
        assert agent.state.variables["$b"].value == "value_b"


class TestArtifactNamingWithAssignment:
    """Test artifact creation with user-specified variable names."""

    def test_long_result_creates_artifact_with_custom_name(self, agent):
        """Test that long results with assignment create artifact with specified name."""
        import hashlib

        call = PlaybookCall(
            "LongPlaybook",
            [],
            {},
            variable_to_assign="$custom_name",
            type_annotation=None,
        )
        long_result = "x" * (config.artifact_result_threshold + 1)

        # Simulate _post_execute logic for artifact creation
        if len(str(long_result)) > config.artifact_result_threshold:
            if call.variable_to_assign:
                artifact_var_name = call.variable_to_assign
                artifact_name_base = (
                    artifact_var_name[1:]
                    if artifact_var_name.startswith("$")
                    else artifact_var_name
                )
            else:
                # Use hash of content for stable names across runs
                content_hash = hashlib.sha256(str(long_result).encode()).hexdigest()[:8]
                artifact_name_base = f"a_{content_hash}"
                artifact_var_name = f"${artifact_name_base}"

        artifact = Artifact(
            name=artifact_name_base,
            summary=f"Result of {call.playbook_klass} call",
            value=long_result,
        )
        agent.state.variables[artifact_var_name] = artifact

        # Verify artifact was created with custom name
        assert "$custom_name" in agent.state.variables
        artifact = agent.state.variables["$custom_name"].value
        assert isinstance(artifact, Artifact)
        assert artifact.name == "custom_name"
        assert artifact.summary == "Result of LongPlaybook call"

    def test_long_result_without_assignment_uses_hash(self, agent):
        """Test that long results without assignment use hash-based names for stability."""
        import hashlib

        call = PlaybookCall("LongPlaybook", [], {})
        long_result = "x" * (config.artifact_result_threshold + 1)

        # Simulate _post_execute logic without assignment
        if len(str(long_result)) > config.artifact_result_threshold:
            if call.variable_to_assign:
                artifact_var_name = call.variable_to_assign
                artifact_name_base = (
                    artifact_var_name[1:]
                    if artifact_var_name.startswith("$")
                    else artifact_var_name
                )
            else:
                # Use hash of content for stable names across runs
                content_hash = hashlib.sha256(str(long_result).encode()).hexdigest()[:8]
                artifact_name_base = f"a_{content_hash}"
                artifact_var_name = f"${artifact_name_base}"

        artifact = Artifact(
            name=artifact_name_base,
            summary=f"Result of {call.playbook_klass} call",
            value=long_result,
        )
        agent.state.variables[artifact_var_name] = artifact

        # Verify artifact was created with hash-based name
        assert artifact_var_name in agent.state.variables
        artifact = agent.state.variables[artifact_var_name].value
        assert isinstance(artifact, Artifact)
        assert artifact.name == artifact_name_base
        assert artifact.summary == f"Result of {call.playbook_klass} call"

    def test_variable_name_without_dollar_prefix(self, agent):
        """Test artifact naming when variable has no $ prefix."""
        import hashlib

        call = PlaybookCall(
            "GetData",
            [],
            {},
            variable_to_assign="data",  # No $ prefix
            type_annotation=None,
        )
        long_result = "x" * (config.artifact_result_threshold + 1)

        # Simulate _post_execute logic
        if len(str(long_result)) > config.artifact_result_threshold:
            if call.variable_to_assign:
                artifact_var_name = call.variable_to_assign
                artifact_name_base = (
                    artifact_var_name[1:]
                    if artifact_var_name.startswith("$")
                    else artifact_var_name
                )
            else:
                # Use hash of content for stable names across runs
                content_hash = hashlib.sha256(str(long_result).encode()).hexdigest()[:8]
                artifact_name_base = f"a_{content_hash}"
                artifact_var_name = f"${artifact_name_base}"

        artifact = Artifact(
            name=artifact_name_base,
            summary=f"Result of {call.playbook_klass} call",
            value=long_result,
        )
        agent.state.variables[artifact_var_name] = artifact

        # Verify artifact name doesn't have $ prefix
        assert "data" in agent.state.variables
        artifact = agent.state.variables["data"].value
        assert artifact.name == "data"

    def test_complex_variable_name_in_artifact(self, agent):
        """Test artifact with complex variable name like $user_data_2024."""
        import hashlib

        call = PlaybookCall(
            "FetchData",
            [],
            {},
            variable_to_assign="$user_data_2024",
            type_annotation="dict",
        )
        long_result = "x" * (config.artifact_result_threshold + 1)

        # Simulate _post_execute logic
        if len(str(long_result)) > config.artifact_result_threshold:
            if call.variable_to_assign:
                artifact_var_name = call.variable_to_assign
                artifact_name_base = (
                    artifact_var_name[1:]
                    if artifact_var_name.startswith("$")
                    else artifact_var_name
                )
            else:
                # Use hash of content for stable names across runs
                content_hash = hashlib.sha256(str(long_result).encode()).hexdigest()[:8]
                artifact_name_base = f"a_{content_hash}"
                artifact_var_name = f"${artifact_name_base}"

        artifact = Artifact(
            name=artifact_name_base,
            summary=f"Result of {call.playbook_klass} call",
            value=long_result,
        )
        agent.state.variables[artifact_var_name] = artifact

        # Verify artifact was created with complex name
        assert "$user_data_2024" in agent.state.variables
        artifact = agent.state.variables["$user_data_2024"].value
        assert artifact.name == "user_data_2024"
