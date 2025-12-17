"""Tests for agent factory methods (get_or_create, get_all)."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from playbooks.agents.local_ai_agent import LocalAIAgent
from playbooks.program import Program
from playbooks.state.variables import Box


@pytest.fixture
def mock_program():
    """Create a mock program with agent management."""
    program = Mock(spec=Program)
    program.agent_klasses = {}
    program.agents_by_klass = {}
    program.agents_by_id = {}
    program.agents = []
    program.runtime = Mock()
    program.runtime.start_agent = AsyncMock()
    program.create_agent = AsyncMock()
    # Don't mock get_or_create_agent - we need the real implementation
    return program


@pytest.fixture
def agent_class(mock_program):
    """Create a test agent class."""

    class TestAccountant(LocalAIAgent):
        klass = "AccountantExpert"
        description = "Test accountant"
        metadata = {}

    mock_program.agent_klasses["AccountantExpert"] = TestAccountant
    return TestAccountant


@pytest.mark.asyncio
class TestGetOrCreate:
    """Tests for AgentClass.get_or_create()."""

    async def test_returns_idle_agent_when_available(self, agent_class):
        """Test that get_or_create returns an idle agent when one exists."""
        from playbooks.program import Program

        # Create real program instance with mocked methods
        mock_program = Mock(spec=Program)

        # Create idle agent
        idle_agent = Mock()
        idle_agent.state = Box()
        idle_agent.state._busy = False

        mock_program.agents_by_klass = {"AccountantExpert": [idle_agent]}
        mock_program.agent_klasses = {
            "AccountantExpert": agent_class
        }  # Add agent_klasses
        mock_program.create_agent = AsyncMock()
        mock_program.runtime = Mock()
        mock_program.runtime.start_agent = AsyncMock()

        # Set up required attributes for get_or_create_agent
        mock_program._agent_creation_lock = asyncio.Lock()
        mock_program.event_agents_changed = Mock()

        # Attach the real get_or_create_agent method
        mock_program.get_or_create_agent = Program.get_or_create_agent.__get__(
            mock_program, Program
        )

        # Mock requester
        requester = Mock()
        requester.program = mock_program
        requester.klass = "TaxAgent"

        # Call get_or_create
        result = await agent_class.get_or_create(requester=requester)

        # Should return the idle agent
        assert result == idle_agent
        # Should not create new agent
        mock_program.create_agent.assert_not_called()

    async def test_creates_new_agent_when_all_busy(self, agent_class):
        """Test that get_or_create creates a new agent when all are busy."""
        from playbooks.program import Program

        mock_program = Mock(spec=Program)

        # Create busy agent
        busy_agent = Mock()
        busy_agent.state = Box()
        busy_agent.state._busy = True

        mock_program.agents_by_klass = {"AccountantExpert": [busy_agent]}
        mock_program.agent_klasses = {
            "AccountantExpert": agent_class
        }  # Add agent_klasses

        # Mock new agent creation
        new_agent = Mock()
        mock_program.create_agent = AsyncMock(return_value=new_agent)
        mock_program.runtime = Mock()
        mock_program.runtime.start_agent = AsyncMock()

        # Set up required attributes for get_or_create_agent
        mock_program._agent_creation_lock = asyncio.Lock()
        mock_program.event_agents_changed = Mock()

        # Attach real method
        mock_program.get_or_create_agent = Program.get_or_create_agent.__get__(
            mock_program, Program
        )

        # Mock requester
        requester = Mock()
        requester.program = mock_program
        requester.klass = "TaxAgent"

        # Call get_or_create
        result = await agent_class.get_or_create(requester=requester)

        # Should create and return new agent
        assert result == new_agent
        mock_program.create_agent.assert_called_once_with("AccountantExpert")
        mock_program.runtime.start_agent.assert_called_once_with(new_agent)

    async def test_creates_new_agent_when_none_exist(self, agent_class):
        """Test that get_or_create creates a new agent when none exist."""
        from playbooks.program import Program

        mock_program = Mock(spec=Program)
        mock_program.agents_by_klass = {"AccountantExpert": []}
        mock_program.agent_klasses = {
            "AccountantExpert": agent_class
        }  # Add agent_klasses

        # Mock new agent creation
        new_agent = Mock()
        mock_program.create_agent = AsyncMock(return_value=new_agent)
        mock_program.runtime = Mock()
        mock_program.runtime.start_agent = AsyncMock()

        # Set up required attributes for get_or_create_agent
        mock_program._agent_creation_lock = asyncio.Lock()
        mock_program.event_agents_changed = Mock()

        # Attach real method
        mock_program.get_or_create_agent = Program.get_or_create_agent.__get__(
            mock_program, Program
        )

        # Mock requester
        requester = Mock()
        requester.program = mock_program
        requester.klass = "TaxAgent"

        # Call get_or_create
        result = await agent_class.get_or_create(requester=requester)

        # Should create and return new agent
        assert result == new_agent
        mock_program.create_agent.assert_called_once()
        mock_program.runtime.start_agent.assert_called_once()

    async def test_allows_same_type_creation(self, agent_class):
        """Test that agent can get_or_create another agent of same type."""
        from playbooks.program import Program

        mock_program = Mock(spec=Program)
        mock_program.agents_by_klass = {"AccountantExpert": []}
        mock_program.agent_klasses = {
            "AccountantExpert": agent_class
        }  # Add agent_klasses

        # Mock new agent creation
        new_agent = Mock()
        mock_program.create_agent = AsyncMock(return_value=new_agent)
        mock_program.runtime = Mock()
        mock_program.runtime.start_agent = AsyncMock()

        # Set up required attributes for get_or_create_agent
        mock_program._agent_creation_lock = asyncio.Lock()
        mock_program.event_agents_changed = Mock()

        # Attach real method
        mock_program.get_or_create_agent = Program.get_or_create_agent.__get__(
            mock_program, Program
        )

        # Requester is SAME type
        requester = Mock()
        requester.program = mock_program
        requester.klass = "AccountantExpert"  # Same as agent_class

        # Should NOT raise error - same-type creation is allowed
        result = await agent_class.get_or_create(requester=requester)

        assert result == new_agent

    async def test_load_balancing_with_multiple_idle(self, agent_class):
        """Test that get_or_create randomly selects from multiple idle agents."""
        from playbooks.program import Program

        mock_program = Mock(spec=Program)

        # Create multiple idle agents
        idle1 = Mock()
        idle1.state = Box()
        idle1.state._busy = False

        idle2 = Mock()
        idle2.state = Box()
        idle2.state._busy = False

        mock_program.agents_by_klass = {"AccountantExpert": [idle1, idle2]}
        mock_program.agent_klasses = {
            "AccountantExpert": agent_class
        }  # Add agent_klasses
        mock_program.create_agent = AsyncMock()
        mock_program.runtime = Mock()
        mock_program.runtime.start_agent = AsyncMock()

        # Set up required attributes for get_or_create_agent
        mock_program._agent_creation_lock = asyncio.Lock()
        mock_program.event_agents_changed = Mock()

        # Attach real method
        mock_program.get_or_create_agent = Program.get_or_create_agent.__get__(
            mock_program, Program
        )

        # Mock requester
        requester = Mock()
        requester.program = mock_program
        requester.klass = "TaxAgent"

        # Call multiple times - should select from idle agents
        results = []
        for _ in range(10):
            result = await agent_class.get_or_create(requester=requester)
            results.append(result)

        # Should return one of the idle agents (not create new)
        assert all(r in [idle1, idle2] for r in results)
        mock_program.create_agent.assert_not_called()

    async def test_passes_create_kwargs(self, agent_class):
        """Test that create kwargs are passed through to create_agent."""
        from playbooks.program import Program

        mock_program = Mock(spec=Program)
        mock_program.agents_by_klass = {"AccountantExpert": []}
        mock_program.agent_klasses = {
            "AccountantExpert": agent_class
        }  # Add agent_klasses

        new_agent = Mock()
        mock_program.create_agent = AsyncMock(return_value=new_agent)
        mock_program.runtime = Mock()
        mock_program.runtime.start_agent = AsyncMock()

        # Set up required attributes for get_or_create_agent
        mock_program._agent_creation_lock = asyncio.Lock()
        mock_program.event_agents_changed = Mock()

        # Attach real method
        mock_program.get_or_create_agent = Program.get_or_create_agent.__get__(
            mock_program, Program
        )

        requester = Mock()
        requester.program = mock_program
        requester.klass = "TaxAgent"

        # Call with kwargs
        await agent_class.get_or_create(
            requester=requester, custom_arg="value", another_arg=123
        )

        # Should pass kwargs through
        mock_program.create_agent.assert_called_once_with(
            "AccountantExpert", custom_arg="value", another_arg=123
        )


class TestGetAll:
    """Tests for AgentClass.get_all()."""

    def test_returns_all_agents_of_type(self, mock_program, agent_class):
        """Test that get_all returns all agents of the type."""
        agent1 = Mock()
        agent2 = Mock()
        agent3 = Mock()

        mock_program.agents_by_klass["AccountantExpert"] = [agent1, agent2, agent3]

        result = agent_class.get_all(mock_program)

        assert result == [agent1, agent2, agent3]

    def test_returns_empty_list_when_none_exist(self, mock_program, agent_class):
        """Test that get_all returns empty list when no agents exist."""
        mock_program.agents_by_klass = {}

        result = agent_class.get_all(mock_program)

        assert result == []

    def test_returns_correct_type_only(self, mock_program, agent_class):
        """Test that get_all only returns agents of the correct type."""
        accountant = Mock()
        other_agent = Mock()

        mock_program.agents_by_klass = {
            "AccountantExpert": [accountant],
            "OtherAgent": [other_agent],
        }

        result = agent_class.get_all(mock_program)

        assert result == [accountant]
        assert other_agent not in result
