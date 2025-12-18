"""Test source tracking for agents from cached .pbasm files."""

import tempfile
from pathlib import Path

import pytest

from playbooks.agents.agent_builder import AgentBuilder
from playbooks.compilation.markdown_to_ast import markdown_to_ast
from playbooks.infrastructure.event_bus import EventBus


class TestSourceTracking:
    """Test that Agent objects have correct source tracking from cache files."""

    @pytest.mark.asyncio
    async def test_agent_source_tracking_from_cache(self):
        """Test that agents created from cached .pbasm files have correct source info."""
        # Create a simple playbook content (simulating compiled content)
        compiled_content = """# TestAgent

This is a test agent.

## greet(name)
Say hello to {name}.
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pbasm", delete=False
        ) as cache_file:
            cache_file.write(compiled_content)
            cache_file.flush()

            try:
                # Create AST from the cached content with source tracking
                ast = markdown_to_ast(
                    compiled_content, source_file_path=cache_file.name
                )

                # Create agent classes from the AST
                agent_classes = await AgentBuilder.create_agent_classes_from_ast(ast)

                # Verify we have the TestAgent
                assert "TestAgent" in agent_classes

                # Create an instance of the agent
                event_bus = EventBus("test_session")
                agent_class = agent_classes["TestAgent"]
                agent = agent_class(event_bus=event_bus, agent_id="test_agent_1")

                # Verify the agent has the correct source tracking
                assert hasattr(agent, "source_file_path")
                assert agent.source_file_path == cache_file.name
                print(f"✅ Agent source_file_path: {agent.source_file_path}")

                # Also check that it has source_line_number (should be set during creation)
                assert hasattr(agent, "source_line_number")
                print(f"✅ Agent source_line_number: {agent.source_line_number}")

            finally:
                # Clean up
                Path(cache_file.name).unlink()

    def test_ast_nodes_have_source_file_path(self):
        """Test that AST nodes have source_file_path when specified."""
        content = """# TestAgent

This is a test agent.

## greet(name)
Say hello to {name}.
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pbasm", delete=False) as f:
            f.write(content)
            f.flush()

            # Create AST with source file path
            ast = markdown_to_ast(content, source_file_path=f.name)

            # Check that the root node has source_file_path
            assert "source_file_path" in ast
            assert ast["source_file_path"] == f.name
            print(f"✅ Root AST node source_file_path: {ast['source_file_path']}")

            # Check that child nodes also have source_file_path
            if "children" in ast:
                for child in ast["children"]:
                    if isinstance(child, dict):
                        assert "source_file_path" in child
                        assert child["source_file_path"] == f.name
                        print(
                            f"✅ Child AST node source_file_path: {child['source_file_path']}"
                        )

            # Clean up
            Path(f.name).unlink()

    @pytest.mark.asyncio
    async def test_program_passes_cache_paths(self):
        """Test that Program class correctly passes cache file paths to markdown_to_ast."""
        from playbooks.program import Program

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a mock compiled program path (cache file)
            cache_file = tmpdir_path / "test_agent_hash123.pbasm"
            compiled_content = """# CachedAgent

This agent was loaded from cache.

## cached_method()
This method came from cache.
"""
            cache_file.write_text(compiled_content)

            # Create a Program with compiled program paths
            program = Program(
                event_bus=EventBus("test_session"),
                compiled_program_paths=[str(cache_file)],
            )

            # Initialize to load agent classes
            await program.initialize()

            # Verify we have the CachedAgent
            assert "CachedAgent" in program.agent_klasses
            print("✅ Found agent: CachedAgent")

            # The agent class should be properly configured
            agent_class = program.agent_klasses["CachedAgent"]
            assert hasattr(agent_class, "klass")
            assert agent_class.klass == "CachedAgent"
            print(f"✅ Agent class klass: {agent_class.klass}")
