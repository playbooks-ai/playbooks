"""Tests for MCPAgent implementation."""

from unittest.mock import AsyncMock

import pytest

from src.playbooks.agents import MCPAgent
from src.playbooks.event_bus import EventBus
from src.playbooks.playbook import RemotePlaybook


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus("test-session")


@pytest.fixture
def mcp_config():
    """Create MCP configuration for testing."""
    return {"url": "http://localhost:8000/mcp", "transport": "sse", "timeout": 30.0}


@pytest.fixture
def mock_transport():
    """Create a mock transport for testing."""
    transport = AsyncMock()
    transport.connect = AsyncMock()
    transport.disconnect = AsyncMock()
    transport.list_tools = AsyncMock()
    transport.call_tool = AsyncMock()
    transport.is_connected = True
    return transport


class TestMCPAgent:
    """Test cases for MCPAgent."""

    def test_mcp_agent_initialization(self, event_bus, mcp_config):
        """Test MCPAgent initialization."""
        agent = MCPAgent(
            klass="TestMCPAgent",
            description="Test MCP agent",
            event_bus=event_bus,
            remote_config=mcp_config,
        )

        assert agent.klass == "TestMCPAgent"
        assert agent.description == "Test MCP agent"
        assert agent.remote_config == mcp_config
        assert agent.transport is not None
        assert not agent._connected

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, event_bus, mcp_config, mock_transport):
        """Test connecting and disconnecting from MCP server."""
        agent = MCPAgent(
            klass="TestMCPAgent",
            description="Test MCP agent",
            event_bus=event_bus,
            remote_config=mcp_config,
        )

        # Replace transport with mock
        agent.transport = mock_transport

        # Test connect
        await agent.connect()
        assert agent._connected
        mock_transport.connect.assert_called_once()

        # Test disconnect
        await agent.disconnect()
        assert not agent._connected
        mock_transport.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_playbooks(self, event_bus, mcp_config, mock_transport):
        """Test discovering MCP tools as playbooks."""
        # Mock tools response
        mock_tools = [
            {
                "name": "add_numbers",
                "description": "Add two numbers together",
                "inputSchema": {
                    "type": "object",
                    "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                },
            },
            {
                "name": "get_weather",
                "description": "Get weather information",
                "inputSchema": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                },
            },
        ]
        mock_transport.list_tools.return_value = mock_tools

        agent = MCPAgent(
            klass="TestMCPAgent",
            description="Test MCP agent",
            event_bus=event_bus,
            remote_config=mcp_config,
        )
        agent.transport = mock_transport
        agent._connected = True

        # Discover playbooks
        await agent.discover_playbooks()

        # Verify playbooks were created
        assert len(agent.playbooks) == 2
        assert "add_numbers" in agent.playbooks
        assert "get_weather" in agent.playbooks

        # Verify playbook properties
        add_numbers_pb = agent.playbooks["add_numbers"]
        assert isinstance(add_numbers_pb, RemotePlaybook)
        assert add_numbers_pb.name == "add_numbers"
        assert add_numbers_pb.description == "Add two numbers together"
        assert add_numbers_pb.agent_name == "TestMCPAgent"

    @pytest.mark.asyncio
    async def test_execute_playbook(self, event_bus, mcp_config, mock_transport):
        """Test executing an MCP tool playbook."""
        # Setup mock transport
        mock_transport.call_tool.return_value = {"result": 8}

        agent = MCPAgent(
            klass="TestMCPAgent",
            description="Test MCP agent",
            event_bus=event_bus,
            remote_config=mcp_config,
        )
        agent.transport = mock_transport
        agent._connected = True

        # Create a mock playbook
        mock_execute_fn = AsyncMock(return_value={"result": 8})
        playbook = RemotePlaybook(
            name="add_numbers",
            description="Add two numbers",
            agent_name="TestMCPAgent",
            execute_fn=mock_execute_fn,
        )
        agent.playbooks["add_numbers"] = playbook

        # Execute playbook
        result = await agent.execute_playbook("add_numbers", [], {"a": 3, "b": 5})

        # Verify result
        assert result == {"result": 8}
        mock_execute_fn.assert_called_once_with(a=3, b=5)

    @pytest.mark.asyncio
    async def test_execute_playbook_cross_agent_call(self, event_bus, mcp_config):
        """Test cross-agent playbook execution."""
        agent = MCPAgent(
            klass="TestMCPAgent",
            description="Test MCP agent",
            event_bus=event_bus,
            remote_config=mcp_config,
        )

        # Create mock other agent
        other_agent = AsyncMock()
        other_agent.execute_playbook = AsyncMock(return_value="other_result")
        agent.register_agent("OtherAgent", other_agent)

        # Execute cross-agent call
        result = await agent.execute_playbook(
            "OtherAgent.some_playbook", [], {"param": "value"}
        )

        # Verify cross-agent call
        assert result == "other_result"
        other_agent.execute_playbook.assert_called_once_with(
            "some_playbook", [], {"param": "value"}
        )

    @pytest.mark.asyncio
    async def test_execute_unknown_playbook(self, event_bus, mcp_config):
        """Test executing an unknown playbook raises error."""
        agent = MCPAgent(
            klass="TestMCPAgent",
            description="Test MCP agent",
            event_bus=event_bus,
            remote_config=mcp_config,
        )
        agent._connected = True

        # Try to execute unknown playbook
        with pytest.raises(ValueError, match="Unknown playbook: unknown_playbook"):
            await agent.execute_playbook("unknown_playbook")

    @pytest.mark.asyncio
    async def test_context_manager(self, event_bus, mcp_config, mock_transport):
        """Test using MCPAgent as async context manager."""
        agent = MCPAgent(
            klass="TestMCPAgent",
            description="Test MCP agent",
            event_bus=event_bus,
            remote_config=mcp_config,
        )
        agent.transport = mock_transport

        async with agent:
            assert agent._connected
            mock_transport.connect.assert_called_once()

        assert not agent._connected
        mock_transport.disconnect.assert_called_once()
