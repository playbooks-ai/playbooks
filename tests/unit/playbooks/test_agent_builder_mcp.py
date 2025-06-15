"""Tests for AgentBuilder MCP agent creation."""

import pytest

from src.playbooks.agent_builder import AgentBuilder
from src.playbooks.agents import LocalAIAgent, MCPAgent
from src.playbooks.event_bus import EventBus
from src.playbooks.exceptions import AgentConfigurationError
from src.playbooks.utils.markdown_to_ast import markdown_to_ast


class TestAgentBuilderMCP:
    """Test cases for AgentBuilder MCP functionality."""

    def test_create_local_agent_from_ast(self):
        """Test creating a local agent from AST (no remote config)."""
        markdown_text = """# TestAgent
This is a test agent.

## test_playbook
This is a test playbook.

### Steps
- 01:RET Done
"""

        ast = markdown_to_ast(markdown_text)
        agents = AgentBuilder.create_agents_from_ast(ast)

        assert len(agents) == 1
        assert "TestAgent" in agents

        # Create instance to verify type
        event_bus = EventBus("test-session")
        agent_instance = agents["TestAgent"](event_bus)
        assert isinstance(agent_instance, LocalAIAgent)
        assert agent_instance.klass == "TestAgent"

    def test_create_mcp_agent_from_ast(self):
        """Test creating an MCP agent from AST with remote config."""
        markdown_text = """# MCPTestAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    transport: sse
---
This is an MCP test agent.
"""

        ast = markdown_to_ast(markdown_text)
        agents = AgentBuilder.create_agents_from_ast(ast)

        assert len(agents) == 1
        assert "MCPTestAgent" in agents

        # Create instance to verify type
        event_bus = EventBus("test-session")
        agent_instance = agents["MCPTestAgent"](event_bus)
        assert isinstance(agent_instance, MCPAgent)
        assert agent_instance.klass == "MCPTestAgent"
        assert agent_instance.remote_config["type"] == "mcp"
        assert agent_instance.remote_config["url"] == "http://localhost:8000/mcp"

    def test_mcp_agent_missing_url_raises_error(self):
        """Test that MCP agent without URL raises configuration error."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    transport: sse
---
MCP agent without URL.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent BadMCPAgent requires 'url' in remote configuration",
        ):
            AgentBuilder.create_agents_from_ast(ast)

    def test_mixed_agent_types_from_ast(self):
        """Test creating both local and MCP agents from the same AST."""
        markdown_text = """# LocalAgent
This is a local agent.

## local_playbook
This is a local playbook.

### Steps
- 01:RET Done

# RemoteAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
---
This is a remote MCP agent.
"""

        ast = markdown_to_ast(markdown_text)
        agents = AgentBuilder.create_agents_from_ast(ast)

        assert len(agents) == 2
        assert "LocalAgent" in agents
        assert "RemoteAgent" in agents

        # Create instances to verify types
        event_bus = EventBus("test-session")

        local_agent = agents["LocalAgent"](event_bus)
        assert isinstance(local_agent, LocalAIAgent)
        assert local_agent.klass == "LocalAgent"

        remote_agent = agents["RemoteAgent"](event_bus)
        assert isinstance(remote_agent, MCPAgent)
        assert remote_agent.klass == "RemoteAgent"

    def test_agent_builder_create_mcp_agent_class_directly(self):
        """Test creating MCP agent class directly."""
        builder = AgentBuilder()

        h1 = {"text": "DirectMCPAgent", "line_number": 1}

        remote_config = {
            "type": "mcp",
            "url": "http://localhost:8000/mcp",
            "transport": "sse",
        }

        agent_class = builder._create_mcp_agent_class(
            "DirectMCPAgent", "Direct MCP agent test", h1, remote_config
        )

        # Verify class properties - the actual naming convention is AgentDirectmcpagent
        assert agent_class.__name__ == "AgentDirectmcpagent"
        assert issubclass(agent_class, MCPAgent)

        # Create instance
        event_bus = EventBus("test-session")
        agent_instance = agent_class(event_bus)
        assert isinstance(agent_instance, MCPAgent)
        assert agent_instance.klass == "DirectMCPAgent"
        assert agent_instance.remote_config == remote_config

    def test_agent_class_name_generation(self):
        """Test agent class name generation."""
        builder = AgentBuilder()

        # Test normal name - the actual naming convention is AgentTestagent
        assert builder.make_agent_class_name("TestAgent") == "AgentTestagent"

        # Test name with spaces
        assert builder.make_agent_class_name("Test Agent") == "AgentTestAgent"

        # Test name with special characters
        assert builder.make_agent_class_name("Test-Agent_123") == "AgentTestAgent123"
