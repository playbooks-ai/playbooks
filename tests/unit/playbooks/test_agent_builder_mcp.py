"""Tests for AgentBuilder MCP agent creation."""

import pytest

from playbooks.exceptions import AgentConfigurationError
from src.playbooks.agents import LocalAIAgent, MCPAgent
from src.playbooks.agents.agent_builder import AgentBuilder
from src.playbooks.event_bus import EventBus
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
        agents = AgentBuilder.create_agent_classes_from_ast(ast)

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
        agents = AgentBuilder.create_agent_classes_from_ast(ast)

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
            match="MCP agent 'BadMCPAgent' requires 'url' in remote configuration",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

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
        agents = AgentBuilder.create_agent_classes_from_ast(ast)

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

        metadata = {
            "remote": {
                "type": "mcp",
                "url": "http://localhost:8000/mcp",
                "transport": "sse",
            }
        }

        agent_class = MCPAgent.create_class(
            "DirectMCPAgent", "Direct MCP agent test", metadata, {}, 1
        )

        # Verify class properties - the actual naming convention is AgentDirectmcpagent
        assert agent_class.__name__ == "DirectMCPAgent"
        assert issubclass(agent_class, MCPAgent)

        # Create instance
        event_bus = EventBus("test-session")
        agent_instance = agent_class(event_bus)
        assert isinstance(agent_instance, MCPAgent)
        assert agent_instance.klass == "DirectMCPAgent"
        assert agent_instance.remote_config == metadata["remote"]

    def test_mcp_configuration_validation_invalid_url_type(self):
        """Test MCP configuration validation with invalid URL type."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    url: 12345  # Invalid: not a string
---
MCP agent with invalid URL type.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent 'BadMCPAgent' requires a valid URL string, got: int",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

    def test_mcp_configuration_validation_empty_url(self):
        """Test MCP configuration validation with empty URL."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    url: ""  # Invalid: empty string
---
MCP agent with empty URL.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent 'BadMCPAgent' requires a valid URL string, got empty string",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

    def test_mcp_configuration_validation_invalid_transport(self):
        """Test MCP configuration validation with invalid transport."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    transport: invalid_transport
---
MCP agent with invalid transport.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent 'BadMCPAgent' has invalid transport 'invalid_transport'",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

    def test_mcp_configuration_validation_invalid_timeout(self):
        """Test MCP configuration validation with invalid timeout."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    timeout: -5  # Invalid: negative timeout
---
MCP agent with invalid timeout.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent 'BadMCPAgent' timeout must be a positive number, got: -5",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

    def test_mcp_configuration_validation_invalid_auth_type(self):
        """Test MCP configuration validation with invalid auth type."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    auth:
      type: invalid_auth
---
MCP agent with invalid auth type.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent 'BadMCPAgent' has invalid auth type 'invalid_auth'",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

    def test_mcp_configuration_validation_missing_api_key(self):
        """Test MCP configuration validation with missing API key."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    auth:
      type: api_key
      # Missing key field
---
MCP agent with missing API key.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent 'BadMCPAgent' with api_key auth requires 'key' field",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

    def test_mcp_configuration_validation_missing_bearer_token(self):
        """Test MCP configuration validation with missing bearer token."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    auth:
      type: bearer
      # Missing token field
---
MCP agent with missing bearer token.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent 'BadMCPAgent' with bearer auth requires 'token' field",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

    def test_mcp_configuration_validation_missing_basic_auth_fields(self):
        """Test MCP configuration validation with missing basic auth fields."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    auth:
      type: basic
      username: user
      # Missing password field
---
MCP agent with incomplete basic auth.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent 'BadMCPAgent' with basic auth requires 'username' and 'password' fields",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

    def test_mcp_configuration_validation_missing_mtls_fields(self):
        """Test MCP configuration validation with missing mTLS fields."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    auth:
      type: mtls
      cert: /path/to/cert.pem
      # Missing key field
---
MCP agent with incomplete mTLS auth.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent 'BadMCPAgent' with mtls auth requires 'cert' and 'key' fields",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

    def test_mcp_configuration_validation_stdio_with_http_url(self):
        """Test MCP configuration validation with stdio transport and HTTP URL."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp  # Invalid for stdio
    transport: stdio
---
MCP agent with stdio transport and HTTP URL.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent 'BadMCPAgent' with stdio transport should not use HTTP/WebSocket URL",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

    def test_mcp_configuration_validation_sse_with_non_http_url(self):
        """Test MCP configuration validation with SSE transport and non-HTTP URL."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    url: /path/to/script.py  # Invalid for SSE
    transport: sse
---
MCP agent with SSE transport and file path URL.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent 'BadMCPAgent' with sse transport requires HTTP\\(S\\) URL",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

    def test_mcp_configuration_validation_websocket_with_invalid_url(self):
        """Test MCP configuration validation with WebSocket transport and invalid URL."""
        markdown_text = """# BadMCPAgent
metadata:
  remote:
    type: mcp
    url: /path/to/script.py  # Invalid for WebSocket
    transport: websocket
---
MCP agent with WebSocket transport and file path URL.
"""

        ast = markdown_to_ast(markdown_text)

        with pytest.raises(
            AgentConfigurationError,
            match="MCP agent 'BadMCPAgent' with websocket transport requires WebSocket or HTTP URL",
        ):
            AgentBuilder.create_agent_classes_from_ast(ast)

    def test_mcp_configuration_validation_valid_configurations(self):
        """Test that valid MCP configurations pass validation."""
        # Test various valid configurations
        valid_configs = [
            # Basic SSE configuration
            """# ValidAgent1
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    transport: sse
---
Valid MCP agent with SSE.
""",
            # Stdio configuration
            """# ValidAgent2
metadata:
  remote:
    type: mcp
    url: /path/to/server.py
    transport: stdio
---
Valid MCP agent with stdio.
""",
            # Configuration with auth
            """# ValidAgent3
metadata:
  remote:
    type: mcp
    url: http://localhost:8000/mcp
    transport: sse
    timeout: 60.0
    auth:
      type: api_key
      key: secret-key
---
Valid MCP agent with auth.
""",
            # WebSocket configuration
            """# ValidAgent4
metadata:
  remote:
    type: mcp
    url: ws://localhost:8000/mcp
    transport: websocket
---
Valid MCP agent with WebSocket.
""",
        ]

        for config_text in valid_configs:
            ast = markdown_to_ast(config_text)
            # Should not raise any exceptions
            agents = AgentBuilder.create_agent_classes_from_ast(ast)
            assert len(agents) == 1
