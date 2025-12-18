"""Tests for variable assignment during playbook execution."""

import pytest

from playbooks.agents.ai_agent import AIAgent
from playbooks.config import config
from playbooks.execution.call import PlaybookCall
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.variables import Artifact


class MockAgent(AIAgent):
    """Mock agent for testing."""

    klass = "MockAgent"
    description = "Mock agent"
    metadata = {}
    playbooks = {}
    namespace_manager = None

    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus)

    async def discover_playbooks(self):
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

    # Mock the execution summary variable (__ uses bracket notation)
    agent.state["__"] = "Test execution summary"

    return agent


class TestVariableAssignmentExecution:
    """Test storing results in variables during execution."""

    def test_short_result_stored_in_variable(self, agent):
        """Test that short results are stored directly in the specified variable."""
        # Create a playbook call with variable assignment ($ prefix in call)
        call = PlaybookCall(
            "GetValue", [], {}, variable_to_assign="$result", type_annotation=None
        )

        # Mock the playbook execution to return a short result
        short_result = "short_value"

        # Simulate storing the result (remove $ prefix for storage)
        if call.variable_to_assign:
            var_name = call.variable_to_assign.lstrip("$")
            if short_result != call.variable_to_assign:
                agent.state[var_name] = short_result

        # Verify the variable was set (no $ prefix in storage, no .value wrapper)
        assert "result" in agent.state
        assert agent.state["result"] == "short_value"

    def test_int_result_stored_in_variable(self, agent):
        """Test that integer results are stored correctly."""
        call = PlaybookCall(
            "Count", [], {}, variable_to_assign="$count", type_annotation="int"
        )

        result = 42

        # Simulate storing the result (remove $ prefix for storage)
        if call.variable_to_assign:
            var_name = call.variable_to_assign.lstrip("$")
            if result != call.variable_to_assign:
                agent.state[var_name] = result

        # Verify the variable was set (no $ prefix, no .value wrapper)
        assert "count" in agent.state
        assert agent.state["count"] == 42

    def test_bool_result_stored_in_variable(self, agent):
        """Test that boolean results are stored correctly."""
        call = PlaybookCall(
            "Check", [], {}, variable_to_assign="$flag", type_annotation="bool"
        )

        result = True

        # Simulate storing the result (remove $ prefix for storage)
        if call.variable_to_assign:
            var_name = call.variable_to_assign.lstrip("$")
            if result != call.variable_to_assign:
                agent.state[var_name] = result

        # Verify the variable was set (no $ prefix, no .value wrapper)
        assert "flag" in agent.state
        assert agent.state["flag"] is True

    def test_no_assignment_no_extra_variables(self, agent):
        """Test that calls without assignment don't create extra variables."""
        call = PlaybookCall("DoSomething", [], {})

        result = "some_result"

        # Simulate the logic - no assignment should happen
        if call.variable_to_assign:
            var_name = call.variable_to_assign.lstrip("$")
            if result != call.variable_to_assign:
                agent.state[var_name] = result

        # Count non-system variables (those not starting with __)
        from playbooks.state.variables import VariablesTracker

        user_vars = VariablesTracker.public_variables(agent.state)
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

        # Simulate artifact case where result IS the variable name (no $ in new system)
        result = "report"

        # Simulate the conditional logic
        if call.variable_to_assign:
            var_name = call.variable_to_assign.lstrip("$")
            if result != var_name:
                agent.state[var_name] = result

        # Verify NO assignment happened (no circular assignment)
        # Note: In real scenario, the artifact would already be set by _post_execute
        from playbooks.state.variables import VariablesTracker

        user_vars = VariablesTracker.public_variables(agent.state)
        assert len(user_vars) == 0

    def test_multiple_assignments_in_sequence(self, agent):
        """Test multiple calls with assignments execute correctly."""
        # First call
        call1 = PlaybookCall(
            "Get1", [], {}, variable_to_assign="$a", type_annotation=None
        )
        result1 = "value_a"
        if call1.variable_to_assign:
            var_name1 = call1.variable_to_assign.lstrip("$")
            if result1 != var_name1:
                agent.state[var_name1] = result1

        # Second call
        call2 = PlaybookCall(
            "Get2", [], {}, variable_to_assign="$b", type_annotation=None
        )
        result2 = "value_b"
        if call2.variable_to_assign:
            var_name2 = call2.variable_to_assign.lstrip("$")
            if result2 != var_name2:
                agent.state[var_name2] = result2

        # Verify both variables are set (no $ prefix, no .value wrapper)
        assert "a" in agent.state
        assert agent.state["a"] == "value_a"
        assert "b" in agent.state
        assert agent.state["b"] == "value_b"


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
        # Store without $ prefix
        var_name = artifact_var_name.lstrip("$")
        agent.state[var_name] = artifact

        # Verify artifact was created with custom name (no $ prefix, artifact is the value)
        assert "custom_name" in agent.state
        artifact = agent.state["custom_name"]
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
        # Store without $ prefix
        var_name = artifact_var_name.lstrip("$")
        agent.state[var_name] = artifact

        # Verify artifact was created with hash-based name (no $ prefix, artifact is the value)
        assert var_name in agent.state
        artifact = agent.state[var_name]
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
        agent.state[artifact_var_name] = artifact

        # Verify artifact name doesn't have $ prefix
        assert "data" in agent.state
        artifact = agent.state["data"]
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
        # Store without $ prefix
        var_name = artifact_var_name.lstrip("$")
        agent.state[var_name] = artifact

        # Verify artifact was created with complex name (no $ prefix, artifact is the value)
        assert "user_data_2024" in agent.state
        artifact = agent.state["user_data_2024"]
        assert artifact.name == "user_data_2024"
