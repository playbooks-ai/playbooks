"""
Tests for CLI compilation functionality including the new compiler improvements.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from playbooks.cli import compile as cli_compile
from playbooks.exceptions import ProgramLoadError


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def simple_playbook():
    """Simple playbook content for testing."""
    return """# TestAgent
This is a test agent

## Test Playbook
A simple test playbook

### Triggers
- At the beginning

### Steps
- Say hello
- End program
"""


@pytest.fixture
def playbook_with_frontmatter():
    """Playbook with frontmatter for testing."""
    return """---
title: "CLI Test Playbook"
author: "Test Author"
version: "1.0"
---

# CLITestAgent
This is a test agent for CLI testing

## CLI Test Playbook
A test playbook for CLI functionality

### Triggers
- At the beginning

### Steps
- Say hello from CLI
- End program
"""


class TestCLICompilation:
    """Test CLI compilation functionality."""

    @patch("playbooks.cli.Compiler")
    def test_single_file_compilation_stdout(
        self, mock_compiler_class, temp_dir, simple_playbook, capsys
    ):
        """Test compiling a single file to stdout."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            (str(temp_dir / "test.pb"), {}, "# CompiledAgent\nCompiled content", False)
        ]

        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(simple_playbook)

        # Test compilation without output file
        cli_compile([str(test_file)])

        # Check that compiler was called correctly
        mock_compiler.process_files.assert_called_once()

        # Check that output file was created (not stdout since we generate filename)
        output_file = temp_dir / "test.pbasm"
        assert output_file.exists()

    @patch("playbooks.cli.Compiler")
    def test_single_file_compilation_with_output(
        self, mock_compiler_class, temp_dir, simple_playbook
    ):
        """Test compiling a single file with specified output."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            (str(temp_dir / "test.pb"), {}, "# CompiledAgent\nCompiled content", False)
        ]

        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(simple_playbook)
        output_file = temp_dir / "custom_output.pbasm"

        # Test compilation with output file
        cli_compile([str(test_file)], str(output_file))

        # Check that output file was created with correct content
        assert output_file.exists()
        content = output_file.read_text()
        assert "CompiledAgent" in content

    @patch("playbooks.cli.Compiler")
    def test_multiple_files_compilation(
        self, mock_compiler_class, temp_dir, simple_playbook
    ):
        """Test compiling multiple files."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            (
                str(temp_dir / "test1.pb"),
                {},
                "# CompiledAgent1\nCompiled content 1",
                False,
            ),
            (
                str(temp_dir / "test2.pb"),
                {},
                "# CompiledAgent2\nCompiled content 2",
                False,
            ),
        ]

        # Create test files
        test_file1 = temp_dir / "test1.pb"
        test_file2 = temp_dir / "test2.pb"
        test_file1.write_text(simple_playbook)
        test_file2.write_text(simple_playbook.replace("TestAgent", "TestAgent2"))

        # Test compilation
        cli_compile([str(test_file1), str(test_file2)])

        # Check that both output files were created
        output_file1 = temp_dir / "test1.pbasm"
        output_file2 = temp_dir / "test2.pbasm"
        assert output_file1.exists()
        assert output_file2.exists()

        content1 = output_file1.read_text()
        content2 = output_file2.read_text()
        assert "CompiledAgent1" in content1
        assert "CompiledAgent2" in content2

    @patch("playbooks.cli.Compiler")
    def test_multiple_files_with_output_error(
        self, mock_compiler_class, temp_dir, simple_playbook
    ):
        """Test error when specifying output file with multiple inputs."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            (
                str(temp_dir / "test1.pb"),
                {},
                "# CompiledAgent1\nCompiled content 1",
                False,
            ),
            (
                str(temp_dir / "test2.pb"),
                {},
                "# CompiledAgent2\nCompiled content 2",
                False,
            ),
        ]

        # Create test files
        test_file1 = temp_dir / "test1.pb"
        test_file2 = temp_dir / "test2.pb"
        test_file1.write_text(simple_playbook)
        test_file2.write_text(simple_playbook.replace("TestAgent", "TestAgent2"))

        # Test compilation with output file - should raise error and exit
        with pytest.raises(SystemExit):
            cli_compile(
                [str(test_file1), str(test_file2)], str(temp_dir / "output.pbasm")
            )

    @patch("playbooks.cli.Compiler")
    def test_frontmatter_preservation_in_cli(
        self, mock_compiler_class, temp_dir, playbook_with_frontmatter
    ):
        """Test that CLI preserves frontmatter in output."""
        # Setup mock with frontmatter
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            (
                str(temp_dir / "test.pb"),
                {"title": "CLI Test Playbook", "author": "Test Author"},
                "# CompiledCLIAgent\nCompiled CLI content",
                False,
            )
        ]

        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(playbook_with_frontmatter)

        # Test compilation
        cli_compile([str(test_file)])

        # Check output file contains frontmatter
        output_file = temp_dir / "test.pbasm"
        assert output_file.exists()
        content = output_file.read_text()

        # Should contain both frontmatter and compiled content
        assert "title: CLI Test Playbook" in content
        assert "author: Test Author" in content
        assert "CompiledCLIAgent" in content

    @patch("playbooks.cli.Compiler")
    def test_mixed_file_types_compilation(
        self, mock_compiler_class, temp_dir, simple_playbook
    ):
        """Test CLI compilation with mixed .pb and .pbasm files."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            (
                str(temp_dir / "source.pb"),
                {},
                "# CompiledFromPB\nCompiled from .pb",
                False,
            ),
            (
                str(temp_dir / "precompiled.pbasm"),
                {},
                "# AlreadyCompiled\nAlready compiled",
                True,
            ),
        ]

        # Create test files
        pb_file = temp_dir / "source.pb"
        pbasm_file = temp_dir / "precompiled.pbasm"
        pb_file.write_text(simple_playbook)
        pbasm_file.write_text("# AlreadyCompiled\nAlready compiled content")

        # Test compilation
        cli_compile([str(pb_file), str(pbasm_file)])

        # Check outputs
        pb_output = temp_dir / "source.pbasm"
        pbasm_output = temp_dir / "precompiled.pbasm.pbasm"  # Note the double extension

        assert pb_output.exists()
        assert pbasm_output.exists()

    @patch("playbooks.cli.Compiler")
    def test_compilation_error_handling(
        self, mock_compiler_class, temp_dir, simple_playbook
    ):
        """Test CLI error handling during compilation."""
        # Setup mock to raise error
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.side_effect = ProgramLoadError(
            "Test compilation error"
        )

        # Create test file
        test_file = temp_dir / "error_test.pb"
        test_file.write_text(simple_playbook)

        # Test compilation - CLI should catch the error and exit
        with pytest.raises(
            ProgramLoadError
        ):  # Error is not caught by CLI at this level
            cli_compile([str(test_file)])

    @patch("playbooks.cli.Compiler")
    def test_file_extension_handling(
        self, mock_compiler_class, temp_dir, simple_playbook
    ):
        """Test proper file extension handling in CLI."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            (
                str(temp_dir / "no_extension"),
                {},
                "# CompiledAgent\nCompiled content",
                False,
            )
        ]

        # Create test file without extension
        test_file = temp_dir / "no_extension"
        test_file.write_text(simple_playbook)

        # Test compilation
        cli_compile([str(test_file)])

        # Should create .pbasm file
        output_file = temp_dir / "no_extension.pbasm"
        assert output_file.exists()

    @patch("playbooks.cli.Loader")
    @patch("playbooks.cli.Compiler")
    def test_loader_integration(
        self, mock_compiler_class, mock_loader_class, temp_dir, simple_playbook
    ):
        """Test CLI integration with Loader."""
        # Setup mocks
        mock_loader_class.read_program_files.return_value = [
            (str(temp_dir / "test.pb"), simple_playbook, False)
        ]

        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            (str(temp_dir / "test.pb"), {}, "# CompiledAgent\nCompiled content", False)
        ]

        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(simple_playbook)

        # Test compilation
        cli_compile([str(test_file)])

        # Verify Loader was called correctly
        mock_loader_class.read_program_files.assert_called_once_with([str(test_file)])

        # Verify Compiler was called with Loader results
        mock_compiler.process_files.assert_called_once()

    @patch("playbooks.cli.Compiler")
    def test_no_frontmatter_handling(
        self, mock_compiler_class, temp_dir, simple_playbook
    ):
        """Test CLI handling of files without frontmatter."""
        # Setup mock with empty frontmatter
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            (str(temp_dir / "test.pb"), {}, "# CompiledAgent\nCompiled content", False)
        ]

        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(simple_playbook)

        # Test compilation
        cli_compile([str(test_file)])

        # Check output file
        output_file = temp_dir / "test.pbasm"
        assert output_file.exists()
        content = output_file.read_text()

        # Should contain only compiled content (no frontmatter)
        assert "CompiledAgent" in content
        assert "---" not in content


class TestCLIIntegration:
    """Test CLI integration scenarios."""

    @patch("playbooks.cli.Compiler")
    def test_string_program_paths_conversion(
        self, mock_compiler_class, temp_dir, simple_playbook
    ):
        """Test that string program paths are converted to list."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            (str(temp_dir / "test.pb"), {}, "# CompiledAgent\nCompiled content", False)
        ]

        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(simple_playbook)

        # Test with string input (should be converted to list internally)
        cli_compile(str(test_file))  # Single string instead of list

        # Should still work
        output_file = temp_dir / "test.pbasm"
        assert output_file.exists()

    @patch("playbooks.cli.Compiler")
    def test_relative_path_handling(
        self, mock_compiler_class, temp_dir, simple_playbook
    ):
        """Test CLI handling of relative paths."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            ("./test.pb", {}, "# CompiledAgent\nCompiled content", False)
        ]

        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(simple_playbook)

        # Change to temp directory and use relative path
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            cli_compile(["./test.pb"])

            # Should create output file
            assert Path("test.pbasm").exists()
        finally:
            os.chdir(original_cwd)
