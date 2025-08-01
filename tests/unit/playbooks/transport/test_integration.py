"""Integration tests for the transport layer with real MCP servers."""

import pytest
from fastmcp import FastMCP

from src.playbooks.transport.mcp_transport import MCPTransport


# Create a simple test MCP server
def create_test_server():
    """Create a simple FastMCP server for testing."""
    mcp = FastMCP("Test Server")

    @mcp.tool
    def add_numbers(a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b

    @mcp.tool
    def greet(name: str) -> str:
        """Greet someone by name."""
        return f"Hello, {name}!"

    @mcp.resource("config://version")
    def get_version() -> str:
        """Get the server version."""
        return "1.0.0"

    @mcp.resource("data://user/{user_id}")
    def get_user(user_id: str) -> dict:
        """Get user data by ID."""
        return {"id": user_id, "name": f"User {user_id}", "active": True}

    return mcp


class TestMCPTransportIntegration:
    """Integration tests for MCP transport with real servers."""

    @pytest.mark.asyncio
    async def test_in_memory_transport_integration(self):
        """Test MCPTransport with in-memory FastMCP server."""
        # Create test server
        test_server = create_test_server()

        # Create transport that connects directly to the server
        # We'll use the FastMCPTransport directly for this test
        from fastmcp import Client

        async with Client(test_server) as client:
            # Test listing tools
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]

            assert "add_numbers" in tool_names
            assert "greet" in tool_names
            assert len(tools) == 2

            # Test calling tools - FastMCP returns list of TextContent objects
            result = await client.call_tool("add_numbers", {"a": 5, "b": 3})
            assert result.content[0].text == "8"

            result = await client.call_tool("greet", {"name": "World"})
            assert result.content[0].text == "Hello, World!"

            # Test listing resources
            resources = await client.list_resources()
            resource_uris = [
                str(resource.uri) for resource in resources
            ]  # Convert AnyUrl to string

            assert "config://version" in resource_uris
            # Note: Template resources may not be listed, so we'll just check for at least one
            assert len(resources) >= 1

            # Test reading resources - FastMCP returns list of TextResourceContents
            result = await client.read_resource("config://version")
            assert result[0].text == "1.0.0"

            result = await client.read_resource("data://user/123")
            assert "User 123" in result[0].text

    @pytest.mark.asyncio
    async def test_mcp_transport_wrapper_integration(self):
        """Test our MCPTransport wrapper with a real server."""
        # Create test server
        test_server = create_test_server()

        # Create a mock config that would work with our transport
        # Note: For this test, we'll create a custom transport that uses
        # the in-memory server directly

        class InMemoryMCPTransport(MCPTransport):
            """Custom transport for testing with in-memory server."""

            def __init__(self, server):
                # Initialize with dummy config
                super().__init__({"url": "memory://test"})
                self.server = server

            async def connect(self) -> None:
                """Connect to in-memory server."""
                if self._connected:
                    return

                from fastmcp import Client

                self.client = Client(self.server)
                await self.client.__aenter__()
                self._connected = True

        # Test the transport
        transport = InMemoryMCPTransport(test_server)

        try:
            await transport.connect()
            assert transport.is_connected

            # Test tool listing
            tools = await transport.list_tools()
            tool_names = [tool.name for tool in tools]
            assert "add_numbers" in tool_names
            assert "greet" in tool_names

            # Test tool calling - FastMCP returns list of TextContent objects
            result = await transport.call_tool("add_numbers", {"a": 10, "b": 20})
            assert result.content[0].text == "30"

            # Test resource listing
            resources = await transport.list_resources()
            assert len(resources) >= 1  # At least the config://version resource

            # Test resource reading - FastMCP returns list of TextResourceContents
            result = await transport.read_resource("config://version")
            assert result[0].text == "1.0.0"

        finally:
            await transport.disconnect()
            assert not transport.is_connected

    @pytest.mark.asyncio
    async def test_transport_context_manager_integration(self):
        """Test transport as context manager with real server."""
        test_server = create_test_server()

        class InMemoryMCPTransport(MCPTransport):
            def __init__(self, server):
                super().__init__({"url": "memory://test"})
                self.server = server

            async def connect(self) -> None:
                if self._connected:
                    return
                from fastmcp import Client

                self.client = Client(self.server)
                await self.client.__aenter__()
                self._connected = True

        # Test context manager usage
        transport = InMemoryMCPTransport(test_server)

        async with transport:
            assert transport.is_connected

            # Should be able to use transport normally
            tools = await transport.list_tools()
            assert len(tools) > 0

            result = await transport.call_tool("greet", {"name": "Integration Test"})
            assert "Hello, Integration Test!" in result.content[0].text

        # Should be disconnected after context
        assert not transport.is_connected
