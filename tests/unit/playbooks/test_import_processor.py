"""
Unit tests for the import processor functionality.
"""

import tempfile
from pathlib import Path
from textwrap import dedent

import pytest

from playbooks.compilation.import_processor import (
    CircularImportError,
    ImportDepthError,
    ImportNotFoundError,
    ImportProcessor,
)


class TestImportProcessor:
    """Tests for ImportProcessor class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def processor(self, temp_dir):
        """Create an ImportProcessor instance."""
        return ImportProcessor(base_path=temp_dir)

    def test_simple_import(self, processor, temp_dir):
        """Test basic import functionality."""
        # Create imported file
        imported_file = temp_dir / "helper.txt"
        imported_file.write_text("This is imported content")

        # Create main file with import
        main_content = dedent(
            """
            # Main file
            !import helper.txt
            ## End of main
        """
        ).strip()

        main_file = temp_dir / "main.pb"

        # Process imports
        result = processor.process_imports(main_content, main_file)

        # Verify imported content is included
        assert "This is imported content" in result
        assert "# Main file" in result
        assert "## End of main" in result

    def test_relative_import(self, processor, temp_dir):
        """Test relative path imports."""
        # Create subdirectory with imported file
        subdir = temp_dir / "lib"
        subdir.mkdir()
        imported_file = subdir / "utils.pb"
        imported_file.write_text("Utility functions")

        # Create main file with relative import
        main_content = "!import ./lib/utils.pb"
        main_file = temp_dir / "main.pb"

        # Process imports
        result = processor.process_imports(main_content, main_file)

        assert "Utility functions" in result

    def test_parent_directory_import(self, processor, temp_dir):
        """Test importing from parent directory."""
        # Create file in parent directory
        parent_file = temp_dir / "shared.txt"
        parent_file.write_text("Shared content")

        # Create subdirectory with main file
        subdir = temp_dir / "project"
        subdir.mkdir()
        main_content = "!import ../shared.txt"
        main_file = subdir / "main.pb"

        # Process imports
        result = processor.process_imports(main_content, main_file)

        assert "Shared content" in result

    def test_indentation_preservation(self, processor, temp_dir):
        """Test that indentation is preserved in imported content."""
        # Create file with multi-line content
        imported_file = temp_dir / "steps.md"
        imported_file.write_text(
            dedent(
                """
            - Step 1
            - Step 2
              - Sub-step 2.1
            - Step 3
        """
            ).strip()
        )

        # Create main file with indented import
        main_content = dedent(
            """
            ## Process
            ### Steps
              !import steps.md
            ### End
        """
        ).strip()

        main_file = temp_dir / "main.pb"

        # Process imports
        result = processor.process_imports(main_content, main_file)

        # Check that indentation is applied
        assert "  - Step 1" in result
        assert "  - Step 2" in result
        assert "    - Sub-step 2.1" in result
        assert "  - Step 3" in result

    def test_nested_imports(self, processor, temp_dir):
        """Test nested import processing."""
        # Create deeply nested files
        file_c = temp_dir / "c.txt"
        file_c.write_text("Content C")

        file_b = temp_dir / "b.txt"
        file_b.write_text("Content B\n!import c.txt")

        file_a = temp_dir / "a.txt"
        file_a.write_text("Content A\n!import b.txt")

        main_content = "!import a.txt"
        main_file = temp_dir / "main.pb"

        # Process imports
        result = processor.process_imports(main_content, main_file)

        # Verify all content is included
        assert "Content A" in result
        assert "Content B" in result
        assert "Content C" in result

    def test_circular_import_detection(self, processor, temp_dir):
        """Test that circular imports are detected."""
        # Create files with circular dependency
        file_a = temp_dir / "a.txt"
        file_a.write_text("Content A\n!import b.txt")

        file_b = temp_dir / "b.txt"
        file_b.write_text("Content B\n!import a.txt")

        main_content = "!import a.txt"
        main_file = temp_dir / "main.pb"

        # Should raise CircularImportError
        with pytest.raises(CircularImportError) as exc_info:
            processor.process_imports(main_content, main_file)

        assert "Circular import detected" in str(exc_info.value)

    def test_self_import_detection(self, processor, temp_dir):
        """Test that self-imports are detected."""
        # Create file that imports itself
        self_file = temp_dir / "self.pb"
        self_file.write_text("Content\n!import self.pb")

        main_content = "!import self.pb"
        main_file = temp_dir / "main.pb"

        with pytest.raises(CircularImportError):
            processor.process_imports(main_content, main_file)

    def test_max_depth_limit(self, processor, temp_dir):
        """Test maximum import depth limit."""
        # Create a deep chain of imports
        for i in range(15):
            file_path = temp_dir / f"file_{i}.txt"
            if i < 14:
                file_path.write_text(f"Level {i}\n!import file_{i+1}.txt")
            else:
                file_path.write_text(f"Level {i}")

        # Set max depth to 10
        processor.max_depth = 10

        main_content = "!import file_0.txt"
        main_file = temp_dir / "main.pb"

        # Should raise ImportDepthError
        with pytest.raises(ImportDepthError) as exc_info:
            processor.process_imports(main_content, main_file)

        assert "Maximum import depth" in str(exc_info.value)

    def test_file_not_found_error(self, processor, temp_dir):
        """Test error handling for missing files."""
        main_content = "!import nonexistent.txt"
        main_file = temp_dir / "main.pb"

        with pytest.raises(ImportNotFoundError) as exc_info:
            processor.process_imports(main_content, main_file)

        assert "nonexistent.txt" in str(exc_info.value)
        assert "file not found" in str(exc_info.value)

    def test_multiple_imports(self, processor, temp_dir):
        """Test multiple imports in a single file."""
        # Create multiple files to import
        file1 = temp_dir / "header.txt"
        file1.write_text("Header content")

        file2 = temp_dir / "body.txt"
        file2.write_text("Body content")

        file3 = temp_dir / "footer.txt"
        file3.write_text("Footer content")

        main_content = dedent(
            """
            # Document
            !import header.txt
            
            ## Main
            !import body.txt
            
            ## End
            !import footer.txt
        """
        ).strip()

        main_file = temp_dir / "main.pb"

        # Process imports
        result = processor.process_imports(main_content, main_file)

        # Verify all imports are included in order
        assert "Header content" in result
        assert "Body content" in result
        assert "Footer content" in result

        # Verify order
        header_pos = result.index("Header content")
        body_pos = result.index("Body content")
        footer_pos = result.index("Footer content")
        assert header_pos < body_pos < footer_pos

    def test_import_with_comments(self, processor, temp_dir):
        """Test that comments after import directive are ignored."""
        # Create imported file
        imported_file = temp_dir / "data.txt"
        imported_file.write_text("Important data")

        # Import with comment
        main_content = "!import data.txt # This imports the data file"
        main_file = temp_dir / "main.pb"

        # Process imports
        result = processor.process_imports(main_content, main_file)

        assert "Important data" in result
        assert "This imports the data file" not in result

    def test_empty_file_import(self, processor, temp_dir):
        """Test importing an empty file."""
        # Create empty file
        empty_file = temp_dir / "empty.txt"
        empty_file.write_text("")

        main_content = dedent(
            """
            Before import
            !import empty.txt
            After import
        """
        ).strip()

        main_file = temp_dir / "main.pb"

        # Process imports
        result = processor.process_imports(main_content, main_file)

        # Should still have before and after content
        assert "Before import" in result
        assert "After import" in result

    def test_import_caching(self, processor, temp_dir):
        """Test that imported files are cached and reused."""
        # Create a file to import multiple times
        shared_file = temp_dir / "shared.txt"
        shared_file.write_text("Shared content")

        main_content = dedent(
            """
            !import shared.txt
            Middle section
            !import shared.txt
        """
        ).strip()

        main_file = temp_dir / "main.pb"

        # Process imports
        result = processor.process_imports(main_content, main_file)

        # Content should appear twice
        assert result.count("Shared content") == 2

        # Verify the file was only read once (cached)
        assert len(processor.processed_files) == 1

    def test_complex_playbook_import(self, processor, temp_dir):
        """Test importing a complex playbook structure."""
        # Create agent configuration
        config_file = temp_dir / "config.pb"
        config_file.write_text(
            dedent(
                """
            ---
            model: gpt-4
            temperature: 0.7
            ---
        """
            ).strip()
        )

        # Create shared steps
        steps_file = temp_dir / "steps.md"
        steps_file.write_text(
            dedent(
                """
            - Validate input
            - Process data
            - Return results
        """
            ).strip()
        )

        # Create main playbook with imports
        main_content = dedent(
            """
            !import config.pb
            
            # Data Processing Agent
            
            ## Main Workflow
            ### Steps
            !import steps.md
            
            ### Error Handling
            - Log errors
            - Retry if needed
        """
        ).strip()

        main_file = temp_dir / "main.pb"

        # Process imports
        result = processor.process_imports(main_content, main_file)

        # Verify structure is maintained
        assert "model: gpt-4" in result
        assert "# Data Processing Agent" in result
        assert "- Validate input" in result
        assert "- Log errors" in result

    def test_absolute_path_import(self, processor, temp_dir):
        """Test importing with absolute path."""
        # Create file with absolute path
        abs_file = temp_dir / "absolute.txt"
        abs_file.write_text("Absolute import")

        # Use absolute path in import
        main_content = f"!import {abs_file}"
        main_file = temp_dir / "main.pb"

        # Process imports
        result = processor.process_imports(main_content, main_file)

        assert "Absolute import" in result

    def test_file_size_limit(self, processor, temp_dir):
        """Test that file size limits are enforced."""
        # Create a large file
        large_file = temp_dir / "large.txt"
        large_content = "x" * (processor.max_file_size + 1)
        large_file.write_text(large_content)

        main_content = "!import large.txt"
        main_file = temp_dir / "main.pb"

        # Should raise error for exceeding size limit
        with pytest.raises(Exception) as exc_info:
            processor.process_imports(main_content, main_file)

        assert "exceeds maximum size" in str(exc_info.value)
