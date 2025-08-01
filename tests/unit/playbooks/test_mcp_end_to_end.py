"""Comprehensive end-to-end tests for MCP agent functionality."""

import json

import pytest
from fastmcp import Client

from src.playbooks.agents import MCPAgent
from src.playbooks.agents.agent_builder import AgentBuilder
from src.playbooks.event_bus import EventBus
from playbooks.exceptions import AgentConfigurationError
from src.playbooks.program import Program
from src.playbooks.transport.mcp_transport import MCPTransport
from src.playbooks.utils.markdown_to_ast import markdown_to_ast

from .test_mcp_server import get_test_server


class TestMCPAgent(MCPAgent):
    klass = "TestMCPAgent"
    description = "Test MCP agent"
    playbooks = {}
    metadata = {}


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

        self.client = Client(self.server)
        await self.client.__aenter__()
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from in-memory server."""
        if not self._connected or not self.client:
            return

        try:
            await self.client.__aexit__(None, None, None)
        except Exception:
            pass  # Ignore disconnect errors in tests
        finally:
            self.client = None
            self._connected = False

    async def list_tools(self):
        """List available tools."""
        if not self._connected:
            raise ConnectionError("Transport not connected")
        return await self.client.list_tools()

    async def call_tool(self, tool_name: str, arguments: dict):
        """Call a tool with arguments."""
        if not self._connected:
            raise ConnectionError("Transport not connected")
        return await self.client.call_tool(tool_name, arguments)

    async def list_resources(self):
        """List available resources."""
        if not self._connected:
            raise ConnectionError("Transport not connected")
        return await self.client.list_resources()

    async def read_resource(self, uri: str):
        """Read a resource."""
        if not self._connected:
            raise ConnectionError("Transport not connected")
        return await self.client.read_resource(uri)

    async def list_prompts(self):
        """List available prompts."""
        if not self._connected:
            raise ConnectionError("Transport not connected")
        return await self.client.list_prompts()

    async def get_prompt(self, name: str, arguments: dict = None):
        """Get a prompt."""
        if not self._connected:
            raise ConnectionError("Transport not connected")
        return await self.client.get_prompt(name, arguments or {})


class TestMCPEndToEnd:
    """Comprehensive end-to-end tests for MCP agent functionality."""

    @pytest.mark.asyncio
    async def test_mcp_agent_full_lifecycle(self):
        """Test complete MCP agent lifecycle with real server."""
        # Create test server
        test_server = get_test_server()
        mcp_server = test_server.get_server()

        # Create MCP agent
        event_bus = EventBus("test-session")

        agent = TestMCPAgent(
            event_bus=event_bus,
            remote_config={"url": "memory://test", "transport": "memory"},
        )

        # Replace transport with in-memory version
        agent.transport = InMemoryMCPTransport(mcp_server)

        try:
            # Test connection
            await agent.connect()
            assert agent._connected

            # Test tool discovery
            await agent.discover_playbooks()
            assert len(agent.playbooks) > 0

            # Verify specific tools are available
            expected_tools = [
                "add_numbers",
                "greet",
                "get_user_info",
                "list_users",
                "create_task",
            ]
            for tool_name in expected_tools:
                assert tool_name in agent.playbooks

            # Test simple tool execution
            result = await agent.execute_playbook("add_numbers", [], {"a": 10, "b": 20})
            assert result == "30"

            # Test tool with string parameters
            result = await agent.execute_playbook(
                "greet", [], {"name": "World", "greeting": "Hi"}
            )
            assert result == "Hi, World!"

            # Test tool with default parameters
            result = await agent.execute_playbook("greet", [], {"name": "Test"})
            assert result == "Hello, Test!"

            # Test complex tool execution
            result = await agent.execute_playbook(
                "create_task",
                [],
                {
                    "title": "Test Task",
                    "description": "A test task",
                    "priority": "high",
                },
            )
            task_data = json.loads(result)
            assert task_data["title"] == "Test Task"
            assert task_data["priority"] == "high"

            # Test list operation
            result = await agent.execute_playbook(
                "list_users", [], {"active_only": True}
            )
            users_data = json.loads(result)
            assert len(users_data) >= 2  # Should have active users

        finally:
            await agent.disconnect()
            assert not agent._connected

    @pytest.mark.asyncio
    async def test_mcp_agent_error_handling(self):
        """Test MCP agent error handling with various error scenarios."""
        test_server = get_test_server()
        mcp_server = test_server.get_server()

        event_bus = EventBus("test-session")
        agent = TestMCPAgent(
            event_bus=event_bus,
            remote_config={"url": "memory://test"},
        )

        agent.transport = InMemoryMCPTransport(mcp_server)

        try:
            await agent.connect()
            await agent.discover_playbooks()

            # Test tool that raises ValueError
            with pytest.raises(Exception):  # Should propagate the error
                await agent.execute_playbook(
                    "simulate_error", [], {"error_type": "value"}
                )

            # Test tool that raises TimeoutError
            with pytest.raises(Exception):
                await agent.execute_playbook(
                    "simulate_error", [], {"error_type": "timeout"}
                )

            # Test calling non-existent tool
            response = await agent.execute_playbook("non_existent_tool")
            assert "Playbook 'non_existent_tool' not found" in response

            # Test tool with invalid user ID
            with pytest.raises(Exception):
                await agent.execute_playbook("get_user_info", [], {"user_id": "999"})

        finally:
            await agent.disconnect()

    @pytest.mark.asyncio
    async def test_mcp_agent_with_program(self):
        """Test MCP agent integration with Program class."""
        test_server = get_test_server()
        mcp_server = test_server.get_server()

        # Create a program with MCP agent
        program_text = """```public.json
[]
```

# TaskManagerAgent
metadata:
  remote:
    type: mcp
    url: memory://test
    transport: memory
---
This agent manages tasks using MCP tools.
"""

        event_bus = EventBus("test-session")
        program = Program(program_text, event_bus)
        await program.initialize()

        # Find the task manager agent
        task_agent = None
        for agent in program.agents:
            if agent.klass == "TaskManagerAgent":
                task_agent = agent
                break

        assert task_agent is not None
        assert isinstance(task_agent, MCPAgent)

        # Replace transport with in-memory version
        task_agent.transport = InMemoryMCPTransport(mcp_server)

        try:
            # Connect and discover tools
            await task_agent.connect()
            await task_agent.discover_playbooks()

            # Test task management workflow
            # Create a task
            result = await task_agent.execute_playbook(
                "create_task",
                [],
                {
                    "title": "Integration Test Task",
                    "description": "Testing MCP integration",
                    "priority": "medium",
                },
            )
            task_data = json.loads(result)
            assert task_data["title"] == "Integration Test Task"

            # List tasks
            result = await task_agent.execute_playbook("list_tasks")
            tasks_data = json.loads(result)
            assert len(tasks_data) >= 1

            # Test counter operations
            result = await task_agent.execute_playbook("increment_counter")
            assert result == "1"

            result = await task_agent.execute_playbook("get_counter")
            assert result == "1"

            result = await task_agent.execute_playbook("reset_counter")
            assert result == "0"

        finally:
            await task_agent.disconnect()

    @pytest.mark.asyncio
    async def test_mcp_agent_cross_agent_communication(self):
        """Test MCP agent communication with local agents."""
        test_server = get_test_server()
        mcp_server = test_server.get_server()

        # Create a program with both local and MCP agents
        program_text = """```public.json
[]
```

```public.json
[]
```

# LocalCalculator
This is a local calculator agent.

```python
@playbook(public=True)
async def calculate_sum(a: int, b: int) -> int:
    return a + b
```

# RemoteTaskManager
metadata:
  remote:
    type: mcp
    url: memory://test
    transport: memory
---
This is a remote task management agent.
"""

        event_bus = EventBus("test-session")
        program = Program(program_text, event_bus)
        await program.initialize()

        # Find agents
        remote_agent = None
        local_agent = await program.create_agent("LocalCalculator")
        for agent in program.agents:
            if agent.klass == "RemoteTaskManager":
                remote_agent = agent

        assert local_agent is not None
        assert remote_agent is not None

        # Replace remote agent transport
        remote_agent.transport = InMemoryMCPTransport(mcp_server)

        try:
            # Connect remote agent
            await remote_agent.connect()
            await remote_agent.discover_playbooks()

            # Test cross-agent communication
            # Local agent should be able to call remote agent
            result = await local_agent.execute_playbook(
                "RemoteTaskManager.add_numbers", [], {"a": 15, "b": 25}
            )
            assert result == "40"

            # Remote agent should be able to call local agent
            # First verify the local agent has the playbook
            assert "calculate_sum" in local_agent.playbooks

            result = await remote_agent.execute_playbook(
                "LocalCalculator.calculate_sum", [], {"a": 10, "b": 5}
            )
            assert result == 15

        finally:
            await remote_agent.disconnect()

    @pytest.mark.asyncio
    async def test_mcp_agent_resource_access(self):
        """Test MCP agent resource access capabilities."""
        test_server = get_test_server()
        mcp_server = test_server.get_server()

        # Create transport directly for resource testing
        transport = InMemoryMCPTransport(mcp_server)

        try:
            await transport.connect()

            # Test resource listing
            resources = await transport.list_resources()
            assert len(resources) > 0

            # Verify specific resources exist
            resource_uris = [str(resource.uri) for resource in resources]
            expected_resources = ["config://version", "data://users", "data://stats"]
            for expected in expected_resources:
                assert expected in resource_uris

            # Test resource reading
            result = await transport.read_resource("config://version")
            assert result[0].text == "1.0.0"

            # Test parameterized resource
            result = await transport.read_resource("data://user/1")
            user_data = json.loads(result[0].text)
            assert user_data["name"] == "Alice"

            # Test stats resource
            result = await transport.read_resource("data://stats")
            stats_data = json.loads(result[0].text)
            assert "total_users" in stats_data
            assert stats_data["total_users"] >= 3

        finally:
            await transport.disconnect()

    @pytest.mark.asyncio
    async def test_mcp_agent_prompt_access(self):
        """Test MCP agent prompt access capabilities."""
        test_server = get_test_server()
        mcp_server = test_server.get_server()

        transport = InMemoryMCPTransport(mcp_server)

        try:
            await transport.connect()

            # Test prompt listing
            prompts = await transport.list_prompts()
            assert len(prompts) > 0

            # Verify specific prompts exist
            prompt_names = [prompt.name for prompt in prompts]
            expected_prompts = [
                "greeting_prompt",
                "task_summary_prompt",
                "code_review_prompt",
            ]
            for expected in expected_prompts:
                assert expected in prompt_names

            # Test prompt execution
            result = await transport.get_prompt(
                "greeting_prompt", {"name": "Test", "style": "casual"}
            )
            prompt_text = result.messages[0].content.text
            assert "Hey Test" in prompt_text

            # Test prompt with different parameters
            result = await transport.get_prompt(
                "code_review_prompt", {"language": "javascript", "complexity": "high"}
            )
            prompt_text = result.messages[0].content.text
            assert "Javascript" in prompt_text
            assert "advanced patterns" in prompt_text

        finally:
            await transport.disconnect()

    @pytest.mark.asyncio
    async def test_mcp_agent_configuration_scenarios(self):
        """Test various MCP agent configuration scenarios."""
        # Test different transport configurations
        configs = [
            {"url": "memory://test", "transport": "memory"},
            {"url": "memory://test", "transport": "memory", "timeout": 60.0},
            {
                "url": "memory://test",
                "transport": "memory",
                "auth": {"type": "api_key", "key": "test"},
            },
        ]

        for config in configs:
            event_bus = EventBus("test-session")
            agent = TestMCPAgent(
                event_bus=event_bus,
                remote_config=config,
            )

            # Verify agent was created successfully
            assert agent.remote_config == config
            assert agent.transport is not None

    def test_mcp_agent_builder_integration(self):
        """Test AgentBuilder integration with various MCP configurations."""
        # Test comprehensive configuration
        markdown_text = """# ComprehensiveMCPAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    transport: sse
    timeout: 45.0
    auth:
      type: bearer
      token: test-token
---
This is a comprehensive MCP agent configuration test.
"""

        ast = markdown_to_ast(markdown_text)
        agents = AgentBuilder.create_agent_classes_from_ast(ast)

        assert len(agents) == 1
        assert "ComprehensiveMCPAgent" in agents

        # Create instance and verify configuration
        event_bus = EventBus("test-session")
        agent_instance = agents["ComprehensiveMCPAgent"](event_bus)

        assert isinstance(agent_instance, MCPAgent)
        assert agent_instance.remote_config["url"] == "http://localhost:8000/mcp"
        assert agent_instance.remote_config["transport"] == "sse"
        assert agent_instance.remote_config["timeout"] == 45.0
        assert agent_instance.remote_config["auth"]["type"] == "bearer"
        assert agent_instance.remote_config["auth"]["token"] == "test-token"

    @pytest.mark.asyncio
    async def test_mcp_agent_context_manager_usage(self):
        """Test MCP agent as async context manager."""
        test_server = get_test_server()
        mcp_server = test_server.get_server()

        event_bus = EventBus("test-session")
        agent = TestMCPAgent(
            event_bus=event_bus,
            remote_config={"url": "memory://test"},
        )

        agent.transport = InMemoryMCPTransport(mcp_server)

        # Test context manager usage
        async with agent:
            assert agent._connected

            # Should be able to discover and use tools
            await agent.discover_playbooks()
            assert len(agent.playbooks) > 0

            result = await agent.execute_playbook(
                "add_numbers", [], {"a": 100, "b": 200}
            )
            assert result == "300"

        # Should be disconnected after context
        assert not agent._connected

    @pytest.mark.asyncio
    async def test_mcp_agent_performance_and_caching(self):
        """Test MCP agent performance characteristics and caching."""
        test_server = get_test_server()
        mcp_server = test_server.get_server()

        event_bus = EventBus("test-session")
        agent = TestMCPAgent(
            event_bus=event_bus,
            remote_config={"url": "memory://test"},
        )

        agent.transport = InMemoryMCPTransport(mcp_server)

        try:
            await agent.connect()

            # Test that multiple discovery calls don't duplicate playbooks
            await agent.discover_playbooks()
            initial_count = len(agent.playbooks)

            await agent.discover_playbooks()  # Second call
            assert len(agent.playbooks) == initial_count  # Should be same

            # Test multiple tool calls
            for i in range(5):
                result = await agent.execute_playbook("increment_counter")
                assert result == str(i + 1)

            # Verify counter state
            result = await agent.execute_playbook("get_counter")
            assert result == "5"

        finally:
            await agent.disconnect()

    def test_mcp_configuration_error_scenarios(self):
        """Test comprehensive error scenarios for MCP configuration."""
        # These should all raise AgentConfigurationError
        error_configs = [
            # Missing URL
            """# BadAgent1
metadata:
  remote:
    type: mcp
    transport: sse
---
Missing URL.
""",
            # Invalid transport
            """# BadAgent2
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    transport: invalid
---
Invalid transport.
""",
            # Negative timeout
            """# BadAgent3
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    timeout: -10
---
Negative timeout.
""",
            # Invalid auth type
            """# BadAgent4
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    auth:
      type: invalid_auth
---
Invalid auth type.
""",
            # Transport/URL mismatch
            """# BadAgent5
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    transport: stdio
---
Transport URL mismatch.
""",
        ]

        for config_text in error_configs:
            ast = markdown_to_ast(config_text)
            with pytest.raises(AgentConfigurationError):
                AgentBuilder.create_agent_classes_from_ast(ast)
