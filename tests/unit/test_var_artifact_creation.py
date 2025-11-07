"""Tests for automatic artifact creation when Var() values exceed the threshold.

This test suite reproduces and verifies the fix for the issue where large values
passed to Var() were stored as regular Variables instead of being automatically
converted to Artifacts.
"""

import pytest

from playbooks.agents.ai_agent import AIAgent
from playbooks.config import config
from playbooks.event_bus import EventBus
from playbooks.execution_state import ExecutionState
from playbooks.python_executor import PythonExecutor
from playbooks.variables import Artifact


class MockProgram:
    """Mock program for testing."""

    def __init__(self):
        self._debug_server = None


class MockAgent(AIAgent):
    """Mock agent for testing."""

    klass = "MockAgent"
    description = "Mock agent"
    metadata = {}
    playbooks = {}
    namespace_manager = None

    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus)
        self.program = MockProgram()

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
    return agent


@pytest.fixture
def executor(agent):
    """Create a PythonExecutor instance."""
    return PythonExecutor(agent)


class TestVarArtifactCreation:
    """Test automatic artifact creation for large Var() values."""

    @pytest.mark.asyncio
    async def test_var_with_large_dict_creates_artifact(self, executor, agent):
        """Test that Var() with a large dict (>threshold chars) creates an Artifact.

        This reproduces the user's issue where a large financial_data dict
        was stored as a regular Variable instead of an Artifact.
        """
        # Create a dict that exceeds the threshold (80 chars in test config)
        large_dict = {
            "revenue_ttm": "$96.77B",
            "revenue_growth_yoy": "18.8%",
            "gross_profit_ttm": "$17.66B",
            "gross_margin": "18.2%",
            "operating_income_ttm": "$8.89B",
            "operating_margin": "9.2%",
            "net_income_ttm": "$14.97B",
            "net_margin": "15.5%",
        }

        # Verify the dict string representation exceeds threshold
        assert len(str(large_dict)) > config.artifact_result_threshold

        code = f"""
$financial_data = {large_dict}
await Var('financial_data', $financial_data)
"""

        result = await executor.execute(code)

        # Verify the variable was captured
        assert "financial_data" in result.vars

        # Check state variables - should be an Artifact
        assert "$financial_data" in agent.state.variables
        stored_var = agent.state.variables["$financial_data"]

        # This is the key assertion - it should be an Artifact, not a regular Variable
        assert isinstance(
            stored_var, Artifact
        ), f"Expected Artifact but got {type(stored_var).__name__}"
        assert stored_var.summary == "Variable: financial_data"
        assert str(large_dict) in str(stored_var.value)

    @pytest.mark.asyncio
    async def test_var_with_large_string_creates_artifact(self, executor, agent):
        """Test that Var() with a large string (>threshold chars) creates an Artifact."""
        # Create a string that exceeds the threshold
        large_string = "x" * (config.artifact_result_threshold + 1)

        code = f"""
$long_text = "{large_string}"
await Var('long_text', $long_text)
"""

        result = await executor.execute(code)

        # Verify the variable was captured
        assert "long_text" in result.vars

        # Check state variables - should be an Artifact
        assert "$long_text" in agent.state.variables
        stored_var = agent.state.variables["$long_text"]

        # Should be an Artifact
        assert isinstance(
            stored_var, Artifact
        ), f"Expected Artifact but got {type(stored_var).__name__}"
        assert stored_var.summary == "Variable: long_text"
        assert stored_var.value == large_string

    @pytest.mark.asyncio
    async def test_var_with_large_list_creates_artifact(self, executor, agent):
        """Test that Var() with a large list (>threshold chars) creates an Artifact."""
        # Create a list that exceeds the threshold
        large_list = ["item" + str(i) for i in range(50)]

        # Verify the list string representation exceeds threshold
        assert len(str(large_list)) > config.artifact_result_threshold

        code = f"""
$data_list = {large_list}
await Var('data_list', $data_list)
"""

        result = await executor.execute(code)

        # Verify the variable was captured
        assert "data_list" in result.vars

        # Check state variables - should be an Artifact
        assert "$data_list" in agent.state.variables
        stored_var = agent.state.variables["$data_list"]

        # Should be an Artifact
        assert isinstance(
            stored_var, Artifact
        ), f"Expected Artifact but got {type(stored_var).__name__}"
        assert stored_var.summary == "Variable: data_list"

    @pytest.mark.asyncio
    async def test_var_with_small_value_remains_variable(self, executor, agent):
        """Test that Var() with a small value (<threshold) remains a regular Variable."""
        small_value = "short"

        # Verify the value is below threshold
        assert len(str(small_value)) <= config.artifact_result_threshold

        code = f"""
$small_data = "{small_value}"
await Var('small_data', $small_data)
"""

        result = await executor.execute(code)

        # Verify the variable was captured
        assert "small_data" in result.vars

        # Check state variables - should NOT be an Artifact
        assert "$small_data" in agent.state.variables
        stored_var = agent.state.variables["$small_data"]

        # Should be a regular Variable, not an Artifact
        assert not isinstance(
            stored_var, Artifact
        ), "Expected regular Variable but got Artifact"
        assert stored_var.value == small_value

    @pytest.mark.asyncio
    async def test_var_at_threshold_boundary_no_artifact(self, executor, agent):
        """Test that Var() with value exactly at threshold does NOT create Artifact."""
        # Create a string exactly at the threshold
        boundary_value = "x" * config.artifact_result_threshold

        # Verify the value is exactly at threshold
        assert len(str(boundary_value)) == config.artifact_result_threshold

        code = f"""
$boundary_data = "{boundary_value}"
await Var('boundary_data', $boundary_data)
"""

        result = await executor.execute(code)

        # Verify the variable was captured
        assert "boundary_data" in result.vars

        # Check state variables - should NOT be an Artifact
        assert "$boundary_data" in agent.state.variables
        stored_var = agent.state.variables["$boundary_data"]

        # Should be a regular Variable, not an Artifact (threshold is exclusive)
        assert not isinstance(
            stored_var, Artifact
        ), "Expected regular Variable but got Artifact"

    @pytest.mark.asyncio
    async def test_var_one_over_threshold_creates_artifact(self, executor, agent):
        """Test that Var() with value one char over threshold creates Artifact."""
        # Create a string exactly one character over the threshold
        over_value = "x" * (config.artifact_result_threshold + 1)

        # Verify the value is one over threshold
        assert len(str(over_value)) == config.artifact_result_threshold + 1

        code = f"""
$over_data = "{over_value}"
await Var('over_data', $over_data)
"""

        result = await executor.execute(code)

        # Verify the variable was captured
        assert "over_data" in result.vars

        # Check state variables - should be an Artifact
        assert "$over_data" in agent.state.variables
        stored_var = agent.state.variables["$over_data"]

        # Should be an Artifact
        assert isinstance(
            stored_var, Artifact
        ), f"Expected Artifact but got {type(stored_var).__name__}"

    @pytest.mark.asyncio
    async def test_var_with_none_value_no_artifact(self, executor, agent):
        """Test that Var() with None value doesn't create Artifact."""
        code = """
$null_data = None
await Var('null_data', $null_data)
"""

        result = await executor.execute(code)

        # Verify the variable was captured
        assert "null_data" in result.vars

        # Check state variables - should NOT be an Artifact
        assert "$null_data" in agent.state.variables
        stored_var = agent.state.variables["$null_data"]

        # Should be a regular Variable
        assert not isinstance(stored_var, Artifact)
        assert stored_var.value is None

    @pytest.mark.asyncio
    async def test_explicit_var_call_with_large_value(self, executor, agent):
        """Test explicit Var() call (not assignment) with large value."""
        large_dict = {"key" + str(i): "value" + str(i) for i in range(20)}

        # Verify the dict exceeds threshold
        assert len(str(large_dict)) > config.artifact_result_threshold

        code = f"""
await Var('explicit_data', {large_dict})
"""

        result = await executor.execute(code)

        # Verify the variable was captured
        assert "explicit_data" in result.vars

        # Check state variables - should be an Artifact
        assert "$explicit_data" in agent.state.variables
        stored_var = agent.state.variables["$explicit_data"]

        # Should be an Artifact
        assert isinstance(
            stored_var, Artifact
        ), f"Expected Artifact but got {type(stored_var).__name__}"
        assert stored_var.summary == "Variable: explicit_data"
