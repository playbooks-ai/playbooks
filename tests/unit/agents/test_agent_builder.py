"""Tests for AgentBuilder functionality."""

import pytest

from playbooks.agents.agent_builder import AgentBuilder
from playbooks.core.exceptions import AgentConfigurationError


class TestParseAgentHeader:
    """Tests for parse_agent_header method."""

    def test_parse_plain_name_defaults_to_ai(self):
        """Agent name without type annotation defaults to AI."""
        name, agent_type = AgentBuilder.parse_agent_header("Host")
        assert name == "Host"
        assert agent_type == "AI"

    def test_parse_explicit_ai_type(self):
        """Agent name with explicit :AI annotation."""
        name, agent_type = AgentBuilder.parse_agent_header("Host:AI")
        assert name == "Host"
        assert agent_type == "AI"

    def test_parse_human_type(self):
        """Agent name with :Human annotation."""
        name, agent_type = AgentBuilder.parse_agent_header("User:Human")
        assert name == "User"
        assert agent_type == "Human"

    def test_parse_mcp_type(self):
        """Agent name with :MCP annotation."""
        name, agent_type = AgentBuilder.parse_agent_header("FileSystem:MCP")
        assert name == "FileSystem"
        assert agent_type == "MCP"

    def test_parse_with_whitespace(self):
        """Handles whitespace around name and type."""
        name, agent_type = AgentBuilder.parse_agent_header("  User  :  Human  ")
        assert name == "User"
        assert agent_type == "Human"

    def test_parse_invalid_type_raises_error(self):
        """Invalid agent type raises AgentConfigurationError."""
        with pytest.raises(AgentConfigurationError) as exc_info:
            AgentBuilder.parse_agent_header("Agent:Invalid")

        assert "Invalid agent type: 'Invalid'" in str(exc_info.value)
        assert "Must be one of ['AI', 'Human', 'MCP']" in str(exc_info.value)

    def test_parse_multiple_colons_raises_error(self):
        """Multiple colons in type annotation raises error."""
        with pytest.raises(AgentConfigurationError) as exc_info:
            AgentBuilder.parse_agent_header("Agent:AI:Extra")

        assert "Invalid agent type: 'AI:Extra'" in str(exc_info.value)

    def test_parse_empty_string(self):
        """Empty string returns empty name with AI type."""
        name, agent_type = AgentBuilder.parse_agent_header("")
        assert name == ""
        assert agent_type == "AI"

    def test_parse_case_sensitive_type(self):
        """Agent type is case-sensitive."""
        with pytest.raises(AgentConfigurationError) as exc_info:
            AgentBuilder.parse_agent_header("User:human")  # lowercase

        assert "Invalid agent type: 'human'" in str(exc_info.value)

    def test_parse_alice_human(self):
        """Real-world example: Alice:Human."""
        name, agent_type = AgentBuilder.parse_agent_header("Alice:Human")
        assert name == "Alice"
        assert agent_type == "Human"

    def test_parse_bob_human(self):
        """Real-world example: Bob:Human."""
        name, agent_type = AgentBuilder.parse_agent_header("Bob:Human")
        assert name == "Bob"
        assert agent_type == "Human"

    def test_parse_facilitator_ai(self):
        """Real-world example: Facilitator:AI."""
        name, agent_type = AgentBuilder.parse_agent_header("Facilitator:AI")
        assert name == "Facilitator"
        assert agent_type == "AI"
