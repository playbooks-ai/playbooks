"""
Tests for CLI compilation functionality including the new compiler improvements.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from playbooks.cli import compile as cli_compile
from playbooks.compiler import FileCompilationResult
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
            FileCompilationResult(
                file_path=str(temp_dir / "test.pb"),
                frontmatter_dict={},
                content="# CompiledAgent\nCompiled content",
                is_compiled=False,
                compiled_file_path=str(temp_dir / "test.pbasm"),
            )
        ]

        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(simple_playbook)

        # Test compilation without output file
        cli_compile([str(test_file)])

        # Check that compiler was called correctly
        mock_compiler.process_files.assert_called_once()

        # Check that content was printed to stdout, not saved to file
        captured = capsys.readouterr()
        assert "CompiledAgent" in captured.out
        assert "Compiled content" in captured.out

        # Check that no output file was created
        output_file = temp_dir / "test.pbasm"
        assert not output_file.exists()

    @patch("playbooks.cli.Compiler")
    def test_single_file_compilation_with_output(
        self, mock_compiler_class, temp_dir, simple_playbook
    ):
        """Test compiling a single file with specified output."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            FileCompilationResult(
                file_path=str(temp_dir / "test.pb"),
                frontmatter_dict={},
                content="# CompiledAgent\nCompiled content",
                is_compiled=False,
                compiled_file_path=str(temp_dir / "test.pbasm"),
            )
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
        self, mock_compiler_class, temp_dir, simple_playbook, capsys
    ):
        """Test compiling multiple files to stdout."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            FileCompilationResult(
                file_path=str(temp_dir / "test1.pb"),
                frontmatter_dict={},
                content="# CompiledAgent1\nCompiled content 1",
                is_compiled=False,
                compiled_file_path=str(temp_dir / "test1.pbasm"),
            ),
            FileCompilationResult(
                file_path=str(temp_dir / "test2.pb"),
                frontmatter_dict={},
                content="# CompiledAgent2\nCompiled content 2",
                is_compiled=False,
                compiled_file_path=str(temp_dir / "test2.pbasm"),
            ),
        ]

        # Create test files
        test_file1 = temp_dir / "test1.pb"
        test_file2 = temp_dir / "test2.pb"
        test_file1.write_text(simple_playbook)
        test_file2.write_text(simple_playbook.replace("TestAgent", "TestAgent2"))

        # Test compilation
        cli_compile([str(test_file1), str(test_file2)])

        # Check that both files' content was printed to stdout
        captured = capsys.readouterr()
        assert "CompiledAgent1" in captured.out
        assert "Compiled content 1" in captured.out
        assert "CompiledAgent2" in captured.out
        assert "Compiled content 2" in captured.out

        # Check that no output files were created
        output_file1 = temp_dir / "test1.pbasm"
        output_file2 = temp_dir / "test2.pbasm"
        assert not output_file1.exists()
        assert not output_file2.exists()

    @patch("playbooks.cli.Compiler")
    def test_multiple_files_with_output_error(
        self, mock_compiler_class, temp_dir, simple_playbook
    ):
        """Test error when specifying output file with multiple inputs."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            FileCompilationResult(
                file_path=str(temp_dir / "test1.pb"),
                frontmatter_dict={},
                content="# CompiledAgent1\nCompiled content 1",
                is_compiled=False,
                compiled_file_path=str(temp_dir / "test1.pbasm"),
            ),
            FileCompilationResult(
                file_path=str(temp_dir / "test2.pb"),
                frontmatter_dict={},
                content="# CompiledAgent2\nCompiled content 2",
                is_compiled=False,
                compiled_file_path=str(temp_dir / "test2.pbasm"),
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
        self, mock_compiler_class, temp_dir, playbook_with_frontmatter, capsys
    ):
        """Test that CLI preserves frontmatter in stdout output."""
        # Setup mock with frontmatter
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            FileCompilationResult(
                file_path=str(temp_dir / "test.pb"),
                frontmatter_dict={
                    "title": "CLI Test Playbook",
                    "author": "Test Author",
                },
                content="# CompiledCLIAgent\nCompiled CLI content",
                is_compiled=False,
                compiled_file_path=str(temp_dir / "test.pbasm"),
            )
        ]

        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(playbook_with_frontmatter)

        # Test compilation
        cli_compile([str(test_file)])

        # Check stdout contains frontmatter
        captured = capsys.readouterr()

        # Should contain both frontmatter and compiled content
        assert "title: CLI Test Playbook" in captured.out
        assert "author: Test Author" in captured.out
        assert "CompiledCLIAgent" in captured.out

        # Check that no output file was created
        output_file = temp_dir / "test.pbasm"
        assert not output_file.exists()

    @patch("playbooks.cli.Compiler")
    def test_mixed_file_types_compilation(
        self, mock_compiler_class, temp_dir, simple_playbook, capsys
    ):
        """Test CLI compilation with mixed .pb and .pbasm files to stdout."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            FileCompilationResult(
                file_path=str(temp_dir / "source.pb"),
                frontmatter_dict={},
                content="# CompiledFromPB\nCompiled from .pb",
                is_compiled=False,
                compiled_file_path=str(temp_dir / "source.pbasm"),
            ),
            FileCompilationResult(
                file_path=str(temp_dir / "precompiled.pbasm"),
                frontmatter_dict={},
                content="# AlreadyCompiled\nAlready compiled",
                is_compiled=True,
                compiled_file_path=str(temp_dir / "precompiled.pbasm"),
            ),
        ]

        # Create test files
        pb_file = temp_dir / "source.pb"
        pbasm_file = temp_dir / "precompiled.pbasm"
        pb_file.write_text(simple_playbook)
        pbasm_file.write_text("# AlreadyCompiled\nAlready compiled content")

        # Test compilation
        cli_compile([str(pb_file), str(pbasm_file)])

        # Check stdout contains both files' content
        captured = capsys.readouterr()
        assert "CompiledFromPB" in captured.out
        assert "Compiled from .pb" in captured.out
        assert "AlreadyCompiled" in captured.out
        assert "Already compiled" in captured.out

        # Check that no output files were created
        pb_output = temp_dir / "source.pbasm"
        pbasm_output = temp_dir / "precompiled.pbasm.pbasm"
        assert not pb_output.exists()
        assert not pbasm_output.exists()

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
        self, mock_compiler_class, temp_dir, simple_playbook, capsys
    ):
        """Test proper file extension handling in CLI with stdout output."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            FileCompilationResult(
                file_path=str(temp_dir / "no_extension"),
                frontmatter_dict={},
                content="# CompiledAgent\nCompiled content",
                is_compiled=False,
                compiled_file_path=str(temp_dir / "no_extension"),
            )
        ]

        # Create test file without extension
        test_file = temp_dir / "no_extension"
        test_file.write_text(simple_playbook)

        # Test compilation
        cli_compile([str(test_file)])

        # Check that content was printed to stdout
        captured = capsys.readouterr()
        assert "CompiledAgent" in captured.out
        assert "Compiled content" in captured.out

        # Check that no output file was created
        output_file = temp_dir / "no_extension.pbasm"
        assert not output_file.exists()

    @patch("playbooks.cli.Loader")
    @patch("playbooks.cli.Compiler")
    def test_loader_integration(
        self, mock_compiler_class, mock_loader_class, temp_dir, simple_playbook, capsys
    ):
        """Test CLI integration with Loader."""
        # Setup mocks
        mock_loader_class.read_program_files.return_value = [
            (str(temp_dir / "test.pb"), simple_playbook, False)
        ]

        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            FileCompilationResult(
                file_path=str(temp_dir / "test.pb"),
                frontmatter_dict={},
                content="# CompiledAgent\nCompiled content",
                is_compiled=False,
                compiled_file_path=str(temp_dir / "test.pbasm"),
            )
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

        # Verify content was printed to stdout
        captured = capsys.readouterr()
        assert "CompiledAgent" in captured.out
        assert "Compiled content" in captured.out

    @patch("playbooks.cli.Compiler")
    def test_no_frontmatter_handling(
        self, mock_compiler_class, temp_dir, simple_playbook, capsys
    ):
        """Test CLI handling of files without frontmatter to stdout."""
        # Setup mock with empty frontmatter
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            FileCompilationResult(
                file_path=str(temp_dir / "test.pb"),
                frontmatter_dict={},
                content="# CompiledAgent\nCompiled content",
                is_compiled=False,
                compiled_file_path=str(temp_dir / "test.pbasm"),
            )
        ]

        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(simple_playbook)

        # Test compilation
        cli_compile([str(test_file)])

        # Check stdout output
        captured = capsys.readouterr()

        # Should contain only compiled content (no frontmatter)
        assert "CompiledAgent" in captured.out
        assert "Compiled content" in captured.out
        assert "---" not in captured.out

        # Check that no output file was created
        output_file = temp_dir / "test.pbasm"
        assert not output_file.exists()


class TestCLIIntegration:
    """Test CLI integration scenarios."""

    @patch("playbooks.cli.Compiler")
    def test_string_program_paths_conversion(
        self, mock_compiler_class, temp_dir, simple_playbook, capsys
    ):
        """Test that string program paths are converted to list."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            FileCompilationResult(
                file_path=str(temp_dir / "test.pb"),
                frontmatter_dict={},
                content="# CompiledAgent\nCompiled content",
                is_compiled=False,
                compiled_file_path=str(temp_dir / "test.pbasm"),
            )
        ]

        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(simple_playbook)

        # Test with string input (should be converted to list internally)
        cli_compile(str(test_file))  # Single string instead of list

        # Should still work and output to stdout
        captured = capsys.readouterr()
        assert "CompiledAgent" in captured.out
        assert "Compiled content" in captured.out

        # Check that no output file was created
        output_file = temp_dir / "test.pbasm"
        assert not output_file.exists()

    @patch("playbooks.cli.Compiler")
    def test_relative_path_handling(
        self, mock_compiler_class, temp_dir, simple_playbook, capsys
    ):
        """Test CLI handling of relative paths with stdout output."""
        # Setup mock
        mock_compiler = Mock()
        mock_compiler_class.return_value = mock_compiler
        mock_compiler.process_files.return_value = [
            FileCompilationResult(
                file_path="./test.pb",
                frontmatter_dict={},
                content="# CompiledAgent\nCompiled content",
                is_compiled=False,
                compiled_file_path="./test.pbasm",
            )
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

            # Should output to stdout
            captured = capsys.readouterr()
            assert "CompiledAgent" in captured.out
            assert "Compiled content" in captured.out

            # Should not create output file
            assert not Path("test.pbasm").exists()
        finally:
            os.chdir(original_cwd)
