"""Integration tests for MCP agent functionality."""

import json
from unittest.mock import AsyncMock

import pytest

from src.playbooks.agents import MCPAgent
from src.playbooks.agents.agent_builder import AgentBuilder
from src.playbooks.event_bus import EventBus
from src.playbooks.program import Program
from src.playbooks.utils.markdown_to_ast import markdown_to_ast


class TestMCPIntegration:
    """Integration tests for MCP agent functionality."""

    @pytest.mark.asyncio
    async def test_mcp_agent_end_to_end(self):
        """Test creating and using an MCP agent end-to-end."""
        # Create a program with an MCP agent
        program_text = """```public.json
[]
```

# WeatherAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    transport: sse
    timeout: 30.0
---
This is a weather MCP agent that provides weather information.
"""

        event_bus = EventBus("test-session")

        # Create program
        program = Program(program_content=program_text, event_bus=event_bus)
        await program.initialize()

        # Find the weather agent
        weather_agent = None
        for agent in program.agents:
            if agent.klass == "WeatherAgent":
                weather_agent = agent
                break

        assert weather_agent is not None
        assert isinstance(weather_agent, MCPAgent)
        assert weather_agent.remote_config["type"] == "mcp"
        assert weather_agent.remote_config["url"] == "http://localhost:8000/mcp"

        # Mock the transport to avoid actual network calls
        mock_transport = AsyncMock()
        mock_transport.connect = AsyncMock()
        mock_transport.disconnect = AsyncMock()
        mock_transport.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "get_weather",
                    "description": "Get current weather for a location",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name"}
                        },
                        "required": ["location"],
                    },
                }
            ]
        )
        mock_transport.call_tool = AsyncMock(
            return_value=AsyncMock(
                content=[
                    AsyncMock(
                        text='{"temperature": 22, "condition": "sunny", "location": "San Francisco"}'
                    )
                ],
                is_error=False,
            )
        )

        # Replace the agent's transport with our mock
        weather_agent.transport = mock_transport

        # Connect and discover playbooks
        await weather_agent.connect()
        await weather_agent.discover_playbooks()

        # Verify playbooks were discovered
        assert "get_weather" in weather_agent.playbooks
        playbook = weather_agent.playbooks["get_weather"]
        assert playbook.name == "get_weather"
        assert playbook.description == "Get current weather for a location"

        # Execute the playbook
        result = await weather_agent.execute_playbook(
            "get_weather", [], {"location": "San Francisco"}
        )

        # Verify the result
        result = json.loads(result)
        assert result["temperature"] == 22
        assert result["condition"] == "sunny"
        assert result["location"] == "San Francisco"

        # Verify transport was called correctly
        mock_transport.connect.assert_called_once()
        mock_transport.list_tools.assert_called_once()
        mock_transport.call_tool.assert_called_once_with(
            "get_weather", {"location": "San Francisco"}
        )

    def test_agent_builder_creates_mcp_agent_from_markdown(self):
        """Test that AgentBuilder correctly creates MCP agents from markdown."""
        markdown_text = """# TestMCPAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    transport: sse
---
This is a test MCP agent.
"""

        ast = markdown_to_ast(markdown_text)
        agents = AgentBuilder.create_agent_classes_from_ast(ast)

        assert len(agents) == 1
        assert "TestMCPAgent" in agents

        # Create instance
        event_bus = EventBus("test-session")
        agent_instance = agents["TestMCPAgent"](event_bus)

        # Verify it's an MCP agent with correct configuration
        assert isinstance(agent_instance, MCPAgent)
        assert agent_instance.klass == "TestMCPAgent"
        assert agent_instance.remote_config["type"] == "mcp"
        assert agent_instance.remote_config["url"] == "http://localhost:8000/mcp"
        assert agent_instance.remote_config["transport"] == "sse"
