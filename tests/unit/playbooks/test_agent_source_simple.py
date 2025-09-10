"""Test agent source tracking with minimal dependencies."""

import tempfile
from pathlib import Path

from src.playbooks.agents.local_ai_agent import LocalAIAgent
from src.playbooks.event_bus import EventBus
from src.playbooks.utils.markdown_to_ast import markdown_to_ast


class TestAgentSourceSimple:
    """Simple test for agent source tracking."""

    def test_local_ai_agent_source_tracking(self):
        """Test that LocalAIAgent stores source tracking info correctly."""
        # Create a minimal H1 node with source info
        content = """# TestAgent

This is a test agent.

## Test playbook
Say hello to the user.
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pbasm", delete=False
        ) as cache_file:
            cache_file.write(content)
            cache_file.flush()

            try:
                # Create AST with source tracking
                ast = markdown_to_ast(content, source_file_path=cache_file.name)

                # Get the H1 node (TestAgent)
                h1_node = None
                for child in ast.get("children", []):
                    if child.get("type") == "h1" and "TestAgent" in child.get(
                        "text", ""
                    ):
                        h1_node = child
                        break

                assert h1_node is not None, "TestAgent H1 node not found"
                assert h1_node.get("source_file_path") == cache_file.name

                print(f"✅ H1 node has source_file_path: {h1_node['source_file_path']}")
                print(f"✅ H1 node line_number: {h1_node.get('line_number')}")

                # Create agent class using LocalAIAgent.create_class
                from src.playbooks.agents.namespace_manager import AgentNamespaceManager

                namespace_manager = AgentNamespaceManager()

                agent_class = LocalAIAgent.create_class(
                    klass="TestAgent",
                    description="This is a test agent.",
                    metadata={},
                    h1=h1_node,
                    source_line_number=h1_node.get("line_number", 1),
                    namespace_manager=namespace_manager,
                )

                # Create an instance of the agent

                event_bus = EventBus("test_session")
                agent = agent_class(event_bus=event_bus, agent_id="test_agent")

                # Test that the agent has source tracking
                assert hasattr(agent, "source_file_path")
                assert agent.source_file_path == cache_file.name
                print(f"✅ Agent source_file_path: {agent.source_file_path}")

                assert hasattr(agent, "source_line_number")
                print(f"✅ Agent source_line_number: {agent.source_line_number}")

            finally:
                Path(cache_file.name).unlink()

    def test_base_agent_initialization(self):
        """Test that BaseAgent correctly accepts and stores source tracking parameters."""
        from src.playbooks.agents.base_agent import BaseAgent

        # Create a dummy agent class that extends BaseAgent
        class DummyAgent(BaseAgent):
            klass = "DummyAgent"
            description = "Test agent"
            metadata = {}

        # Test initialization with source tracking
        test_source_file = "/tmp/test.pbasm"
        test_line_number = 42

        agent = DummyAgent(
            agent_id="dummy_1",
            program=None,  # We can use None for this test
            source_line_number=test_line_number,
            source_file_path=test_source_file,
        )

        # Verify the source tracking attributes are set
        assert agent.source_line_number == test_line_number
        assert agent.source_file_path == test_source_file
        print(f"✅ BaseAgent source_line_number: {agent.source_line_number}")
        print(f"✅ BaseAgent source_file_path: {agent.source_file_path}")
