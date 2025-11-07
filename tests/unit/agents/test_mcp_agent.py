"""Tests for MCPAgent implementation."""

from unittest.mock import AsyncMock

import pytest

from playbooks.agents import MCPAgent
from playbooks.agents.ai_agent import AIAgent
from playbooks.infrastructure.event_bus import EventBus
from playbooks.playbook import RemotePlaybook
from playbooks.program import Program


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


@pytest.fixture
def mock_program():
    """Create a mock program for testing."""
    program = AsyncMock(spec=Program)
    program.agents = []
    program.execution_finished = False
    return program


class MCPTestAgent(MCPAgent):
    klass = "MCPTestAgent"
    description = "Test MCP agent"
    metadata = {}

    def __init__(self, **kwargs):
        # Initialize with empty playbooks to avoid deep copy issues
        self.__class__.playbooks = {}
        super().__init__(**kwargs)


class TestMCPAgent:
    """Test cases for MCPAgent."""

    def test_mcp_agent_initialization(self, event_bus, mcp_config, mock_program):
        """Test MCPAgent initialization."""
        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
        )

        assert agent.klass == "MCPTestAgent"
        assert agent.description == "Test MCP agent"
        assert agent.remote_config == mcp_config
        assert agent.transport is not None
        assert not agent._connected

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(
        self, event_bus, mcp_config, mock_transport, mock_program
    ):
        """Test connecting and disconnecting from MCP server."""
        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
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
    async def test_discover_playbooks(
        self, event_bus, mcp_config, mock_transport, mock_program
    ):
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

        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
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
        assert add_numbers_pb.agent_name == "MCPTestAgent"

    @pytest.mark.asyncio
    async def test_execute_playbook(
        self, event_bus, mcp_config, mock_transport, mock_program
    ):
        """Test executing an MCP tool playbook."""
        # Setup mock transport
        mock_transport.call_tool.return_value = {"result": 8}

        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
        )
        agent.transport = mock_transport
        agent._connected = True

        # Create a mock playbook
        mock_execute_fn = AsyncMock(return_value={"result": 8})
        playbook = RemotePlaybook(
            name="add_numbers",
            description="Add two numbers",
            agent_name="MCPTestAgent",
            execute_fn=mock_execute_fn,
        )
        agent.playbooks["add_numbers"] = playbook

        # Execute playbook
        success, result = await agent.execute_playbook(
            "add_numbers", [], {"a": 3, "b": 5}
        )

        # Verify result
        assert success
        assert result == {"result": 8}
        mock_execute_fn.assert_called_once_with(a=3, b=5)

    @pytest.mark.asyncio
    async def test_execute_playbook_cross_agent_call(
        self, event_bus, mcp_config, mock_program
    ):
        """Test cross-agent playbook execution."""
        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
        )

        # Create mock other agent
        other_agent = AsyncMock(
            spec=AIAgent,
            klass="OtherAgent",
            playbooks={"some_playbook": AsyncMock(spec=RemotePlaybook, public=True)},
        )
        other_agent.execute_playbook = AsyncMock(return_value=(True, "other_result"))
        mock_program.agents = [other_agent]

        # Execute cross-agent call
        success, result = await agent.execute_playbook(
            "OtherAgent.some_playbook", [], {"param": "value"}
        )

        # Verify cross-agent call
        assert success
        assert result == "other_result"
        other_agent.execute_playbook.assert_called_once_with(
            "some_playbook", [], {"param": "value"}
        )

    @pytest.mark.asyncio
    async def test_execute_unknown_playbook(self, event_bus, mcp_config, mock_program):
        """Test executing an unknown playbook raises error."""
        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
        )
        agent._connected = True

        # Try to execute unknown playbook
        success, result = await agent.execute_playbook("unknown_playbook")
        assert not success
        assert "Playbook 'unknown_playbook' not found" in result

    @pytest.mark.asyncio
    async def test_context_manager(
        self, event_bus, mcp_config, mock_transport, mock_program
    ):
        """Test using MCPAgent as async context manager."""
        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
        )
        agent.transport = mock_transport

        async with agent:
            assert agent._connected
            mock_transport.connect.assert_called_once()

        assert not agent._connected
        mock_transport.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_positional_args_mapping_multiple_params(
        self, event_bus, mcp_config, mock_transport, mock_program
    ):
        """Test that multiple positional args are correctly mapped to parameter names."""
        # Mock the tool call result
        mock_result = AsyncMock()
        mock_result.content = [AsyncMock(text="Search results")]
        mock_result.is_error = False
        mock_transport.call_tool.return_value = mock_result

        # Mock tool with multiple parameters
        mock_tools = [
            {
                "name": "search_in_file",
                "description": "Search for a query in a file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "query": {"type": "string"},
                    },
                },
            }
        ]
        mock_transport.list_tools.return_value = mock_tools

        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
        )
        agent.transport = mock_transport
        agent._connected = True

        # Discover playbooks
        await agent.discover_playbooks()

        # Execute with positional arguments
        playbook = agent.playbooks["search_in_file"]
        result = await playbook.execute_fn("world_model.md", "life")

        # Verify the transport was called with correctly mapped parameters
        mock_transport.call_tool.assert_called_once_with(
            "search_in_file", {"path": "world_model.md", "query": "life"}
        )
        assert result == "Search results"

    @pytest.mark.asyncio
    async def test_positional_args_mapping_single_param(
        self, event_bus, mcp_config, mock_transport, mock_program
    ):
        """Test that single positional arg is correctly mapped to parameter name."""
        # Mock the tool call result
        mock_result = AsyncMock()
        mock_result.content = [AsyncMock(text="Weather data")]
        mock_result.is_error = False
        mock_transport.call_tool.return_value = mock_result

        # Mock tool with single parameter
        mock_tools = [
            {
                "name": "get_weather",
                "description": "Get weather information",
                "inputSchema": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                },
            }
        ]
        mock_transport.list_tools.return_value = mock_tools

        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
        )
        agent.transport = mock_transport
        agent._connected = True

        # Discover playbooks
        await agent.discover_playbooks()

        # Execute with positional argument
        playbook = agent.playbooks["get_weather"]
        result = await playbook.execute_fn("San Francisco")

        # Verify the transport was called with correctly mapped parameter
        mock_transport.call_tool.assert_called_once_with(
            "get_weather", {"location": "San Francisco"}
        )
        assert result == "Weather data"

    @pytest.mark.asyncio
    async def test_keyword_args_mapping(
        self, event_bus, mcp_config, mock_transport, mock_program
    ):
        """Test that keyword args work correctly."""
        # Mock the tool call result
        mock_result = AsyncMock()
        mock_result.content = [AsyncMock(text="Search results")]
        mock_result.is_error = False
        mock_transport.call_tool.return_value = mock_result

        # Mock tool with multiple parameters
        mock_tools = [
            {
                "name": "search_in_file",
                "description": "Search for a query in a file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "query": {"type": "string"},
                    },
                },
            }
        ]
        mock_transport.list_tools.return_value = mock_tools

        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
        )
        agent.transport = mock_transport
        agent._connected = True

        # Discover playbooks
        await agent.discover_playbooks()

        # Execute with keyword arguments
        playbook = agent.playbooks["search_in_file"]
        result = await playbook.execute_fn(path="world_model.md", query="life")

        # Verify the transport was called with keyword arguments
        mock_transport.call_tool.assert_called_once_with(
            "search_in_file", {"path": "world_model.md", "query": "life"}
        )
        assert result == "Search results"

    @pytest.mark.asyncio
    async def test_mixed_args_kwargs(
        self, event_bus, mcp_config, mock_transport, mock_program
    ):
        """Test that mixed positional and keyword args work correctly."""
        # Mock the tool call result
        mock_result = AsyncMock()
        mock_result.content = [AsyncMock(text="Search results")]
        mock_result.is_error = False
        mock_transport.call_tool.return_value = mock_result

        # Mock tool with three parameters
        mock_tools = [
            {
                "name": "search_file",
                "description": "Search for a query in a file with options",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "query": {"type": "string"},
                        "case_sensitive": {"type": "boolean"},
                    },
                },
            }
        ]
        mock_transport.list_tools.return_value = mock_tools

        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
        )
        agent.transport = mock_transport
        agent._connected = True

        # Discover playbooks
        await agent.discover_playbooks()

        # Execute with mixed positional and keyword arguments
        playbook = agent.playbooks["search_file"]
        result = await playbook.execute_fn(
            "world_model.md", query="life", case_sensitive=True
        )

        # Verify the transport was called with mixed arguments
        mock_transport.call_tool.assert_called_once_with(
            "search_file",
            {"path": "world_model.md", "query": "life", "case_sensitive": True},
        )
        assert result == "Search results"

    @pytest.mark.asyncio
    async def test_too_many_positional_args(
        self, event_bus, mcp_config, mock_transport, mock_program
    ):
        """Test that extra positional args beyond schema parameters are ignored."""
        # Mock the tool call result
        mock_result = AsyncMock()
        mock_result.content = [AsyncMock(text="Weather data")]
        mock_result.is_error = False
        mock_transport.call_tool.return_value = mock_result

        # Mock tool with single parameter
        mock_tools = [
            {
                "name": "get_weather",
                "description": "Get weather information",
                "inputSchema": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                },
            }
        ]
        mock_transport.list_tools.return_value = mock_tools

        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
        )
        agent.transport = mock_transport
        agent._connected = True

        # Discover playbooks
        await agent.discover_playbooks()

        # Execute with too many positional arguments
        playbook = agent.playbooks["get_weather"]
        result = await playbook.execute_fn("San Francisco", "extra_arg", "another_arg")

        # Verify only the first parameter is used (extra args ignored)
        mock_transport.call_tool.assert_called_once_with(
            "get_weather", {"location": "San Francisco"}
        )
        assert result == "Weather data"

    @pytest.mark.asyncio
    async def test_error_response_handling(
        self, event_bus, mcp_config, mock_transport, mock_program
    ):
        """Test that error responses are properly formatted."""
        # Mock an error response
        mock_result = AsyncMock()
        mock_result.content = [AsyncMock(text="File not found")]
        mock_result.is_error = True
        mock_transport.call_tool.return_value = mock_result

        # Mock tool
        mock_tools = [
            {
                "name": "read_file",
                "description": "Read a file",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            }
        ]
        mock_transport.list_tools.return_value = mock_tools

        agent = MCPTestAgent(
            event_bus=event_bus,
            remote_config=mcp_config,
            program=mock_program,
        )
        agent.transport = mock_transport
        agent._connected = True

        # Discover playbooks
        await agent.discover_playbooks()

        # Execute with error result
        playbook = agent.playbooks["read_file"]
        result = await playbook.execute_fn("nonexistent.txt")

        # Verify error prefix is added
        assert result == "Error: File not found"
