"""Tests for the MCP transport implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.playbooks.transport.mcp_transport import MCPTransport


class TestMCPTransport:
    """Test cases for the MCPTransport class."""

    def test_init_with_valid_config(self):
        """Test initialization with valid configuration."""
        config = {
            "url": "http://localhost:8000/mcp",
            "transport": "sse",
            "timeout": 30.0,
        }

        transport = MCPTransport(config)

        assert transport.url == "http://localhost:8000/mcp"
        assert transport.transport_type == "sse"
        assert transport.timeout == 30.0
        assert not transport.is_connected
        assert transport.client is None

    def test_init_without_url_raises_error(self):
        """Test that initialization without URL raises ValueError."""
        config = {"transport": "sse"}

        with pytest.raises(
            ValueError, match="MCP transport requires 'url' in configuration"
        ):
            MCPTransport(config)

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        config = {"url": "http://localhost:8000/mcp"}

        transport = MCPTransport(config)

        assert transport.transport_type == "sse"  # Default
        assert transport.timeout == 30.0  # Default
        assert transport.auth == {}  # Default

    @pytest.mark.asyncio
    @patch("src.playbooks.transport.mcp_transport.Client")
    @patch("src.playbooks.transport.mcp_transport.SSETransport")
    async def test_connect_sse(self, mock_sse_transport, mock_client_class):
        """Test connecting with SSE transport."""
        config = {"url": "http://localhost:8000/mcp", "transport": "sse"}

        # Mock the transport and client
        mock_transport_instance = MagicMock()
        mock_sse_transport.return_value = mock_transport_instance

        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        transport = MCPTransport(config)
        await transport.connect()

        # Verify SSE transport was created
        mock_sse_transport.assert_called_once_with("http://localhost:8000/mcp")

        # Verify client was created with transport
        mock_client_class.assert_called_once_with(mock_transport_instance)

        # Verify client connection was established
        mock_client_instance.__aenter__.assert_called_once()

        assert transport.is_connected
        assert transport.client is mock_client_instance

    @pytest.mark.asyncio
    @patch("src.playbooks.transport.mcp_transport.Client")
    @patch("src.playbooks.transport.mcp_transport.PythonStdioTransport")
    async def test_connect_stdio(self, mock_stdio_transport, mock_client_class):
        """Test connecting with stdio transport."""
        config = {"url": "path/to/server.py", "transport": "stdio"}

        # Mock the transport and client
        mock_transport_instance = MagicMock()
        mock_stdio_transport.return_value = mock_transport_instance

        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        transport = MCPTransport(config)
        await transport.connect()

        # Verify stdio transport was created
        mock_stdio_transport.assert_called_once_with("path/to/server.py")

        # Verify client was created with transport
        mock_client_class.assert_called_once_with(mock_transport_instance)

        assert transport.is_connected

    @pytest.mark.asyncio
    @patch("src.playbooks.transport.mcp_transport.Client")
    async def test_connect_auto_detect(self, mock_client_class):
        """Test connecting with auto-detected transport."""
        config = {
            "url": "ws://localhost:8000/mcp",
            "transport": "websocket",  # Not explicitly handled, should auto-detect
        }

        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        transport = MCPTransport(config)
        await transport.connect()

        # Verify client was created with URL directly (auto-detect)
        mock_client_class.assert_called_once_with("ws://localhost:8000/mcp")

        assert transport.is_connected

    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """Test that connecting when already connected is a no-op."""
        config = {"url": "http://localhost:8000/mcp"}
        transport = MCPTransport(config)

        # Manually set connected state
        transport._connected = True

        # Should not raise an error and should remain connected
        await transport.connect()
        assert transport.is_connected

    @pytest.mark.asyncio
    @patch("src.playbooks.transport.mcp_transport.Client")
    async def test_connect_failure(self, mock_client_class):
        """Test connection failure handling."""
        config = {"url": "http://localhost:8000/mcp"}

        # Mock client to raise exception on connect
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__.side_effect = Exception("Connection failed")
        mock_client_class.return_value = mock_client_instance

        transport = MCPTransport(config)

        with pytest.raises(ConnectionError, match="MCP connection failed"):
            await transport.connect()

        assert not transport.is_connected

    @pytest.mark.asyncio
    async def test_disconnect_when_connected(self):
        """Test disconnecting when connected."""
        config = {"url": "http://localhost:8000/mcp"}
        transport = MCPTransport(config)

        # Mock connected state
        mock_client = AsyncMock()
        transport.client = mock_client
        transport._connected = True

        await transport.disconnect()

        # Verify client disconnect was called
        mock_client.__aexit__.assert_called_once_with(None, None, None)

        assert not transport.is_connected
        assert transport.client is None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        """Test that disconnecting when not connected is safe."""
        config = {"url": "http://localhost:8000/mcp"}
        transport = MCPTransport(config)

        # Should not raise an error
        await transport.disconnect()
        assert not transport.is_connected

    @pytest.mark.asyncio
    async def test_call_list_tools(self):
        """Test calling list_tools method."""
        config = {"url": "http://localhost:8000/mcp"}
        transport = MCPTransport(config)

        # Mock connected state and client
        mock_client = AsyncMock()
        mock_tools = [{"name": "tool1"}, {"name": "tool2"}]
        mock_client.list_tools.return_value = mock_tools

        transport.client = mock_client
        transport._connected = True

        result = await transport.call("list_tools")

        assert result == mock_tools
        assert transport._tools_cache == mock_tools
        mock_client.list_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_call_tool(self):
        """Test calling call_tool method."""
        config = {"url": "http://localhost:8000/mcp"}
        transport = MCPTransport(config)

        # Mock connected state and client
        mock_client = AsyncMock()
        mock_result = {"result": "success"}
        mock_client.call_tool.return_value = mock_result

        transport.client = mock_client
        transport._connected = True

        result = await transport.call(
            "call_tool", {"tool_name": "test_tool", "arguments": {"param": "value"}}
        )

        assert result == mock_result
        mock_client.call_tool.assert_called_once_with("test_tool", {"param": "value"})

    @pytest.mark.asyncio
    async def test_call_when_not_connected(self):
        """Test that calls fail when not connected."""
        config = {"url": "http://localhost:8000/mcp"}
        transport = MCPTransport(config)

        with pytest.raises(ConnectionError, match="MCP transport not connected"):
            await transport.call("list_tools")

    @pytest.mark.asyncio
    async def test_call_invalid_method(self):
        """Test calling an unsupported method."""
        config = {"url": "http://localhost:8000/mcp"}
        transport = MCPTransport(config)

        # Mock connected state
        transport.client = AsyncMock()
        transport._connected = True

        with pytest.raises(ValueError, match="Unsupported MCP method: invalid_method"):
            await transport.call("invalid_method")

    @pytest.mark.asyncio
    async def test_convenience_methods(self):
        """Test convenience methods."""
        config = {"url": "http://localhost:8000/mcp"}
        transport = MCPTransport(config)

        # Mock connected state and client
        mock_client = AsyncMock()
        mock_client.list_tools.return_value = [{"name": "tool1"}]
        mock_client.call_tool.return_value = {"result": "success"}
        mock_client.list_resources.return_value = [{"uri": "resource1"}]
        mock_client.read_resource.return_value = {"content": "data"}

        transport.client = mock_client
        transport._connected = True

        # Test convenience methods
        tools = await transport.list_tools()
        assert tools == [{"name": "tool1"}]

        result = await transport.call_tool("test_tool", {"param": "value"})
        assert result == {"result": "success"}

        resources = await transport.list_resources()
        assert resources == [{"uri": "resource1"}]

        resource_data = await transport.read_resource("test://resource")
        assert resource_data == {"content": "data"}

    def test_get_cached_tools(self):
        """Test getting cached tools."""
        config = {"url": "http://localhost:8000/mcp"}
        transport = MCPTransport(config)

        # Initially no cache
        assert transport.get_cached_tools() is None

        # Set cache
        tools = [{"name": "tool1"}]
        transport._tools_cache = tools

        assert transport.get_cached_tools() == tools
