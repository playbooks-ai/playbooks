"""Tests for automatic artifact creation when Var() values exceed the threshold.

This test suite verifies that large values are automatically converted to Artifacts.
"""

import pytest

from playbooks.agents.ai_agent import AIAgent
from playbooks.config import config
from playbooks.execution.python_executor import PythonExecutor
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.execution_state import ExecutionState
from playbooks.state.variables import Artifact


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
        """Test that Var() with a large dict (>threshold chars) creates an Artifact."""
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

        assert len(str(large_dict)) > config.artifact_result_threshold

        code = f"""
state.financial_data = {large_dict}
await Var('financial_data', state.financial_data)
"""

        result = await executor.execute(code)

        # Verify the variable was captured
        assert "financial_data" in result.vars

        # Check state variables - should be an Artifact
        assert hasattr(agent.state.variables, "financial_data")
        stored_var = agent.state.variables.financial_data
        assert isinstance(stored_var, Artifact)
        assert "Variable: financial_data" in stored_var.summary

    @pytest.mark.asyncio
    async def test_var_with_large_string_creates_artifact(self, executor, agent):
        """Test that Var() with a large string (>threshold chars) creates an Artifact."""
        large_string = "x" * (config.artifact_result_threshold + 1)

        code = f"""
state.long_text = "{large_string}"
await Var('long_text', state.long_text)
"""

        result = await executor.execute(code)

        assert "long_text" in result.vars
        assert hasattr(agent.state.variables, "long_text")
        stored_var = agent.state.variables.long_text
        assert isinstance(stored_var, Artifact)

    @pytest.mark.asyncio
    async def test_var_with_large_list_creates_artifact(self, executor, agent):
        """Test that Var() with a large list (>threshold chars) creates an Artifact."""
        large_list = ["item" + str(i) for i in range(50)]

        assert len(str(large_list)) > config.artifact_result_threshold

        code = f"""
state.data_list = {large_list}
await Var('data_list', state.data_list)
"""

        result = await executor.execute(code)

        assert "data_list" in result.vars
        assert hasattr(agent.state.variables, "data_list")
        stored_var = agent.state.variables.data_list
        assert isinstance(stored_var, Artifact)

    @pytest.mark.asyncio
    async def test_var_with_small_value_remains_variable(self, executor, agent):
        """Test that Var() with a small value (<threshold) does NOT create Artifact."""
        small_value = "short"

        assert len(str(small_value)) <= config.artifact_result_threshold

        code = f"""
state.small_data = "{small_value}"
await Var('small_data', state.small_data)
"""

        result = await executor.execute(code)

        assert "small_data" in result.vars
        assert hasattr(agent.state.variables, "small_data")
        stored_var = agent.state.variables.small_data
        assert not isinstance(stored_var, Artifact)
        assert stored_var == small_value

    @pytest.mark.asyncio
    async def test_var_at_threshold_boundary_no_artifact(self, executor, agent):
        """Test that Var() with value exactly at threshold does NOT create Artifact."""
        boundary_value = "x" * config.artifact_result_threshold

        assert len(str(boundary_value)) == config.artifact_result_threshold

        code = f"""
state.boundary_data = "{boundary_value}"
await Var('boundary_data', state.boundary_data)
"""

        result = await executor.execute(code)

        assert "boundary_data" in result.vars
        assert hasattr(agent.state.variables, "boundary_data")
        stored_var = agent.state.variables.boundary_data
        assert not isinstance(stored_var, Artifact)

    @pytest.mark.asyncio
    async def test_var_one_over_threshold_creates_artifact(self, executor, agent):
        """Test that Var() with value one char over threshold creates Artifact."""
        over_value = "x" * (config.artifact_result_threshold + 1)

        assert len(str(over_value)) == config.artifact_result_threshold + 1

        code = f"""
state.over_data = "{over_value}"
await Var('over_data', state.over_data)
"""

        result = await executor.execute(code)

        assert "over_data" in result.vars
        assert hasattr(agent.state.variables, "over_data")
        stored_var = agent.state.variables.over_data
        assert isinstance(stored_var, Artifact)

    @pytest.mark.asyncio
    async def test_var_with_none_value_no_artifact(self, executor, agent):
        """Test that Var() with None value does not create Artifact."""
        code = """
state.empty_value = None
await Var('empty_value', state.empty_value)
"""

        result = await executor.execute(code)

        assert "empty_value" in result.vars
        assert hasattr(agent.state.variables, "empty_value")
        assert agent.state.variables.empty_value is None

    @pytest.mark.asyncio
    async def test_explicit_var_call_with_large_value(self, executor, agent):
        """Test explicit Var() call with large value creates an artifact."""
        large_dict = {"key" + str(i): "value" + str(i) for i in range(20)}

        assert len(str(large_dict)) > config.artifact_result_threshold

        code = f"""
await Var('explicit_data', {large_dict})
"""

        result = await executor.execute(code)

        assert "explicit_data" in result.vars
        assert hasattr(agent.state.variables, "explicit_data")
        stored_var = agent.state.variables.explicit_data
        assert isinstance(stored_var, Artifact)
