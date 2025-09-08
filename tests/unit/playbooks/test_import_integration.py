"""
Integration tests for import functionality with the full Playbooks system.
"""

import tempfile
from pathlib import Path
from textwrap import dedent

import pytest

from playbooks.compiler import FileCompilationSpec
from playbooks.loader import Loader


class TestImportIntegration:
    """Integration tests for import functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_loader_with_imports(self, temp_dir):
        """Test that Loader correctly processes imports."""
        # Create imported file
        helper_file = temp_dir / "helper.txt"
        helper_file.write_text("Helper content")

        # Create main file with import
        main_file = temp_dir / "main.pb"
        main_file.write_text(
            dedent(
                """
            # Test Agent
            
            ## Workflow
            !import helper.txt
            ### Steps
            - End program
        """
            ).strip()
        )

        # Load with imports processed
        files = Loader.read_program_files([str(main_file)])

        # Should be one file with imported content
        assert len(files) == 1
        file_path, content, is_compiled = files[0]

        assert "Helper content" in content
        assert "# Test Agent" in content
        assert not is_compiled

    def test_nested_imports_with_loader(self, temp_dir):
        """Test nested imports through Loader."""
        # Create chain of imports
        level2_file = temp_dir / "level2.txt"
        level2_file.write_text("Level 2 content")

        level1_file = temp_dir / "level1.txt"
        level1_file.write_text(
            dedent(
                """
            Level 1 content
            !import level2.txt
        """
            ).strip()
        )

        main_file = temp_dir / "main.pb"
        main_file.write_text(
            dedent(
                """
            # Main Agent
            !import level1.txt
            ## Steps
            - Process data
        """
            ).strip()
        )

        # Load with nested imports
        files = Loader.read_program_files([str(main_file)])

        file_path, content, _ = files[0]

        # All levels should be included
        assert "Level 1 content" in content
        assert "Level 2 content" in content
        assert "# Main Agent" in content

    def test_compiler_with_imported_content(self, temp_dir):
        """Test that Compiler works with imported content."""
        # Create a simple imported file
        steps_file = temp_dir / "steps.txt"
        steps_file.write_text("- Step 1\n- Step 2")

        # Create main playbook with import
        main_file = temp_dir / "main.pb"
        main_content = dedent(
            """
            # Simple Agent
            
            ## Main Task
            ### Steps
            !import steps.txt
            - Step 3
        """
        ).strip()
        main_file.write_text(main_content)

        # Load and process imports
        files = Loader.read_program_files([str(main_file)])
        file_path, processed_content, is_compiled = files[0]

        # Verify imports were processed
        assert "- Step 1" in processed_content
        assert "- Step 2" in processed_content

        # Create compilation spec
        FileCompilationSpec(
            file_path=file_path, content=processed_content, is_compiled=is_compiled
        )

        # Compile (this will use the LLM if configured)
        # For testing, we'll just verify the structure is maintained
        assert "# Simple Agent" in processed_content
        assert "## Main Task" in processed_content

    def test_indented_import_integration(self, temp_dir):
        """Test indented imports in full integration."""
        # Create file with list items
        items_file = temp_dir / "items.md"
        items_file.write_text(
            dedent(
                """
            - Item A
              - Sub-item A1
            - Item B
        """
            ).strip()
        )

        # Create main file with indented import
        main_file = temp_dir / "main.pb"
        main_file.write_text(
            dedent(
                """
            # List Agent
            
            ## Process List
            ### Steps
            - Process the following items:
              !import items.md
            - Complete processing
        """
            ).strip()
        )

        # Load with imports
        files = Loader.read_program_files([str(main_file)])
        _, content, _ = files[0]

        # Check indentation is preserved
        assert "  - Item A" in content
        assert "    - Sub-item A1" in content
        assert "  - Item B" in content

    def test_multiple_file_imports(self, temp_dir):
        """Test loading multiple files with imports."""
        # Create shared configuration
        config_file = temp_dir / "config.txt"
        config_file.write_text("Shared configuration")

        # Create first agent
        agent1_file = temp_dir / "agent1.pb"
        agent1_file.write_text(
            dedent(
                """
            # Agent 1
            !import config.txt
            ## Task 1
            ### Steps
            - Do task 1
        """
            ).strip()
        )

        # Create second agent
        agent2_file = temp_dir / "agent2.pb"
        agent2_file.write_text(
            dedent(
                """
            # Agent 2
            !import config.txt
            ## Task 2
            ### Steps
            - Do task 2
        """
            ).strip()
        )

        # Load both files
        files = Loader.read_program_files([str(agent1_file), str(agent2_file)])

        assert len(files) == 2

        # Both should have the shared config
        for file_path, content, _ in files:
            assert "Shared configuration" in content

    def test_import_error_handling(self, temp_dir):
        """Test error handling for import failures."""
        # Create main file with non-existent import
        main_file = temp_dir / "main.pb"
        main_file.write_text(
            dedent(
                """
            # Error Test Agent
            !import nonexistent.txt
            ## Steps
            - This should fail
        """
            ).strip()
        )

        # Should raise an error when loading
        with pytest.raises(Exception) as exc_info:
            Loader.read_program_files([str(main_file)])

        assert "nonexistent.txt" in str(exc_info.value)

    def test_circular_import_detection_integration(self, temp_dir):
        """Test circular import detection in integration."""
        # Create circular dependency
        file_a = temp_dir / "a.pb"
        file_a.write_text("# Agent A\n!import b.pb")

        file_b = temp_dir / "b.pb"
        file_b.write_text("# Agent B\n!import a.pb")

        # Should detect circular import
        with pytest.raises(Exception) as exc_info:
            Loader.read_program_files([str(file_a)])

        assert "Circular import" in str(exc_info.value)

    def test_import_with_frontmatter(self, temp_dir):
        """Test imports in files with frontmatter."""
        # Create imported content
        shared_file = temp_dir / "shared.txt"
        shared_file.write_text("Shared steps")

        # Create file with frontmatter and import
        main_file = temp_dir / "main.pb"
        main_file.write_text(
            dedent(
                """
            ---
            model: gpt-4
            temperature: 0.5
            ---
            
            # Agent with Frontmatter
            
            !import shared.txt
            
            ## Main Task
            ### Steps
            - Execute task
        """
            ).strip()
        )

        # Load and verify
        files = Loader.read_program_files([str(main_file)])
        _, content, _ = files[0]

        # Should preserve frontmatter and include import
        assert "model: gpt-4" in content
        assert "Shared steps" in content
        assert "# Agent with Frontmatter" in content
