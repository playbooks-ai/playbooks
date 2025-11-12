"""Integration tests for MCP memory transport."""

import os
import tempfile
from pathlib import Path

import pytest

from playbooks.agents import MCPAgent
from playbooks.core.exceptions import AgentConfigurationError
from playbooks.infrastructure.event_bus import EventBus
from playbooks.program import Program
from playbooks.transport.mcp_module_loader import clear_cache
from playbooks.transport.mcp_transport import MCPTransport


class TestMemoryTransportIntegration:
    """Integration tests for memory transport with real MCP server files."""

    def setup_method(self):
        """Setup before each test."""
        clear_cache()

    def teardown_method(self):
        """Cleanup after each test."""
        clear_cache()

    @pytest.mark.asyncio
    async def test_memory_transport_basic(self):
        """Test basic memory transport connection."""
        # Create a simple MCP server file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from fastmcp import FastMCP

mcp = FastMCP("TestServer")

@mcp.tool()
def hello(name: str) -> str:
    '''Say hello to someone.'''
    return f"Hello, {name}!"

@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    '''Add two numbers.'''
    return a + b
"""
            )
            tmp_path = tmp.name

        try:
            # Create transport with memory URL
            config = {
                "url": f"memory://{tmp_path}",
                "transport": "memory",
            }
            transport = MCPTransport(config)

            # Connect and verify
            await transport.connect()
            assert transport._connected

            # List tools
            tools = await transport.list_tools()
            assert len(tools) >= 2
            tool_names = [t["name"] for t in tools]
            assert "hello" in tool_names
            assert "add_numbers" in tool_names

            # Call a tool
            result = await transport.call_tool("hello", {"name": "World"})
            assert "Hello, World!" in str(result)

            # Disconnect
            await transport.disconnect()
            assert not transport._connected

        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_memory_transport_with_custom_var(self):
        """Test memory transport with custom variable name."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from fastmcp import FastMCP

my_custom_server = FastMCP("CustomServer")

@my_custom_server.tool()
def test_tool() -> str:
    '''Test tool.'''
    return "success"
"""
            )
            tmp_path = tmp.name

        try:
            config = {
                "url": f"memory://{tmp_path}?var=my_custom_server",
                "transport": "memory",
            }
            transport = MCPTransport(config)

            await transport.connect()
            tools = await transport.list_tools()
            assert len(tools) >= 1
            assert tools[0]["name"] == "test_tool"

            await transport.disconnect()

        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_memory_transport_relative_path(self):
        """Test memory transport with relative path from CWD."""
        # Create temp directory and file
        with tempfile.TemporaryDirectory() as tmpdir:
            server_file = Path(tmpdir) / "server.py"
            server_file.write_text(
                """
from fastmcp import FastMCP

mcp = FastMCP("RelativeServer")

@mcp.tool()
def relative_tool() -> str:
    '''Tool from relative path.'''
    return "relative"
"""
            )

            # Save original CWD
            orig_cwd = os.getcwd()
            try:
                # Change to temp directory
                os.chdir(tmpdir)

                config = {
                    "url": "memory://server.py",
                    "transport": "memory",
                }
                transport = MCPTransport(config)

                await transport.connect()
                tools = await transport.list_tools()
                assert len(tools) >= 1
                assert tools[0]["name"] == "relative_tool"

                await transport.disconnect()

            finally:
                os.chdir(orig_cwd)

    @pytest.mark.asyncio
    async def test_memory_transport_with_mcp_agent(self):
        """Test memory transport integration with MCPAgent."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from fastmcp import FastMCP

mcp = FastMCP("AgentTestServer")

@mcp.tool()
def agent_tool(value: str) -> str:
    '''Tool for agent test.'''
    return f"processed: {value}"
"""
            )
            tmp_path = tmp.name

        try:
            event_bus = EventBus("test-session")
            remote_config = {
                "url": f"memory://{tmp_path}",
                "transport": "memory",
            }

            # Create agent
            agent = MCPAgent(
                event_bus=event_bus,
                remote_config=remote_config,
            )

            # Connect and discover
            await agent.connect()
            assert agent._connected

            await agent.discover_playbooks()
            assert len(agent.playbooks) >= 1
            assert "agent_tool" in agent.playbooks

            # Test playbook execution
            playbook = agent.playbooks["agent_tool"]
            result = await playbook.execute(value="test")
            assert "processed: test" in str(result)

            await agent.disconnect()

        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_memory_transport_with_program(self):
        """Test memory transport with Program class."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from fastmcp import FastMCP

mcp = FastMCP("ProgramTestServer")

@mcp.tool()
def program_tool() -> str:
    '''Tool for program test.'''
    return "program_success"
"""
            )
            tmp_path = tmp.name

        try:
            # Create a playbook with memory transport agent
            program_text = f"""
# TestAgent
metadata:
  remote:
    type: mcp
    url: memory://{tmp_path}
    transport: memory
---
Test agent with memory transport.

```public.json
[]
```
"""

            event_bus = EventBus("test-session")
            program = Program(program_content=program_text, event_bus=event_bus)
            await program.initialize()

            # Find the agent
            test_agent = program.agents_by_klass["TestAgent"][0]
            assert test_agent is not None
            assert isinstance(test_agent, MCPAgent)

            # Connect and verify
            await test_agent.connect()
            await test_agent.discover_playbooks()

            assert "program_tool" in test_agent.playbooks

            await test_agent.disconnect()
            await program.cleanup()

        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_memory_transport_caching(self):
        """Test that multiple agents can share the same cached server."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from fastmcp import FastMCP

mcp = FastMCP("SharedServer")

@mcp.tool()
def shared_tool() -> str:
    '''Shared tool.'''
    return "shared"
"""
            )
            tmp_path = tmp.name

        try:
            event_bus = EventBus("test-session")
            remote_config = {
                "url": f"memory://{tmp_path}",
                "transport": "memory",
            }

            # Create two agents with same config
            agent1 = MCPAgent(event_bus=event_bus, remote_config=remote_config)
            agent2 = MCPAgent(event_bus=event_bus, remote_config=remote_config)

            # Both should connect successfully (using cached server)
            await agent1.connect()
            await agent2.connect()

            assert agent1._connected
            assert agent2._connected

            await agent1.disconnect()
            await agent2.disconnect()

        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_memory_transport_file_not_found(self):
        """Test error handling for non-existent file."""
        config = {
            "url": "memory:///nonexistent/path/server.py",
            "transport": "memory",
        }

        with pytest.raises(ValueError, match="MCP server file not found"):
            MCPTransport(config)

    @pytest.mark.asyncio
    async def test_memory_transport_missing_variable(self):
        """Test error handling for missing server variable."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
# No mcp variable here
x = 42
"""
            )
            tmp_path = tmp.name

        try:
            config = {
                "url": f"memory://{tmp_path}",
                "transport": "memory",
            }

            with pytest.raises(ValueError, match="does not contain variable 'mcp'"):
                MCPTransport(config)

        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_memory_transport_validation(self):
        """Test MCPAgent validation for memory transport."""
        # Valid memory URL
        MCPAgent.validate(
            "TestAgent",
            {
                "type": "mcp",
                "url": "memory://path/to/server.py",
                "transport": "memory",
            },
        )

        # Invalid: memory transport without memory:// URL
        with pytest.raises(AgentConfigurationError, match="requires memory:// URL"):
            MCPAgent.validate(
                "TestAgent",
                {
                    "type": "mcp",
                    "url": "http://example.com",
                    "transport": "memory",
                },
            )

    @pytest.mark.asyncio
    async def test_memory_transport_with_real_example_file(self):
        """Test with real example MCP server files if they exist."""
        # Try to use the filesystem_mcp.py from examples
        example_path = (
            Path(__file__).parent.parent.parent
            / "examples"
            / "deepagents"
            / "filesystem_mcp.py"
        )

        if not example_path.exists():
            pytest.skip("Example file not found")

        config = {
            "url": f"memory://{example_path}",
            "transport": "memory",
        }
        transport = MCPTransport(config)

        await transport.connect()
        tools = await transport.list_tools()

        # Filesystem MCP should have tools like ls, read_file, etc.
        assert len(tools) > 0
        tool_names = [t["name"] for t in tools]
        assert "ls" in tool_names or "read_file" in tool_names

        await transport.disconnect()


class TestMemoryTransportErrors:
    """Test error cases for memory transport."""

    def setup_method(self):
        """Setup before each test."""
        clear_cache()

    def teardown_method(self):
        """Cleanup after each test."""
        clear_cache()

    def test_invalid_url_scheme(self):
        """Test error for non-memory URL with memory transport."""
        with pytest.raises(ValueError, match="Invalid memory transport"):
            MCPTransport(
                {
                    "url": "http://example.com",
                    "transport": "memory",
                }
            )

    def test_syntax_error_in_module(self):
        """Test error for Python syntax errors in server file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
# Syntax error
def broken(
"""
            )
            tmp_path = tmp.name

        try:
            with pytest.raises(ValueError, match="Invalid memory transport"):
                MCPTransport(
                    {
                        "url": f"memory://{tmp_path}",
                        "transport": "memory",
                    }
                )
        finally:
            os.unlink(tmp_path)

    def test_import_error_in_module(self):
        """Test error for import errors in server file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                """
from nonexistent_module import something

mcp = something()
"""
            )
            tmp_path = tmp.name

        try:
            with pytest.raises(ValueError, match="Invalid memory transport"):
                MCPTransport(
                    {
                        "url": f"memory://{tmp_path}",
                        "transport": "memory",
                    }
                )
        finally:
            os.unlink(tmp_path)
