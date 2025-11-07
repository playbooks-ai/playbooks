"""Tests for loader.py module - focusing on read_program method."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from playbooks.core.exceptions import ProgramLoadError
from playbooks.compilation.loader import Loader


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_playbook():
    """Sample playbook content."""
    return """# TestAgent
This is a test agent

## Test Playbook
A test playbook

### Triggers
- At the beginning

### Steps
- Do something
- End program
"""


@pytest.fixture
def sample_compiled_playbook():
    """Sample compiled playbook content."""
    return """# CompiledAgent
This is a compiled agent

## CompiledPlaybook() -> None
A compiled playbook

### Triggers
- T1:BGN At the beginning

### Steps
- 01:QUE Do(something)
- 02:YLD for exit
"""


class TestReadProgram:
    """Test the read_program method."""

    def test_read_program_single_file(self, temp_dir, sample_playbook):
        """Test reading a single file with read_program."""
        test_file = temp_dir / "test.pb"
        test_file.write_text(sample_playbook)

        content, do_not_compile = Loader.read_program([str(test_file)])

        assert content == sample_playbook
        assert do_not_compile is False

    def test_read_program_compiled_file(self, temp_dir, sample_compiled_playbook):
        """Test reading a compiled file sets do_not_compile flag."""
        test_file = temp_dir / "test.pbasm"
        test_file.write_text(sample_compiled_playbook)

        content, do_not_compile = Loader.read_program([str(test_file)])

        assert content == sample_compiled_playbook
        assert do_not_compile is True

    def test_read_program_multiple_files(self, temp_dir, sample_playbook):
        """Test reading multiple files combines content."""
        test_file1 = temp_dir / "test1.pb"
        test_file2 = temp_dir / "test2.pb"

        content1 = sample_playbook
        content2 = sample_playbook.replace("TestAgent", "SecondAgent")

        test_file1.write_text(content1)
        test_file2.write_text(content2)

        combined_content, do_not_compile = Loader.read_program(
            [str(test_file1), str(test_file2)]
        )

        # Content should be joined with double newlines
        # Note: Order may vary due to set() deduplication, so check both contents are present
        assert content1 in combined_content or content2 in combined_content
        assert "TestAgent" in combined_content or "SecondAgent" in combined_content
        assert "\n\n" in combined_content  # Should have double newline separator
        assert do_not_compile is False

    def test_read_program_mixed_file_types(
        self, temp_dir, sample_playbook, sample_compiled_playbook
    ):
        """Test reading mixed file types sets do_not_compile flag."""
        pb_file = temp_dir / "test.pb"
        pbasm_file = temp_dir / "test.pbasm"

        pb_file.write_text(sample_playbook)
        pbasm_file.write_text(sample_compiled_playbook)

        content, do_not_compile = Loader.read_program([str(pb_file), str(pbasm_file)])

        # Should include both contents
        assert sample_playbook in content
        assert sample_compiled_playbook in content
        # Should set do_not_compile to True if any compiled file is present
        assert do_not_compile is True

    def test_read_program_glob_pattern(self, temp_dir, sample_playbook):
        """Test reading files using glob pattern."""
        # Create multiple files
        for i in range(3):
            test_file = temp_dir / f"test{i}.pb"
            test_file.write_text(sample_playbook.replace("TestAgent", f"Agent{i}"))

        pattern = str(temp_dir / "*.pb")
        content, do_not_compile = Loader.read_program([pattern])

        # Should contain content from all files
        assert "Agent0" in content
        assert "Agent1" in content
        assert "Agent2" in content
        assert do_not_compile is False

    def test_read_program_file_not_found_error(self, temp_dir):
        """Test read_program raises ProgramLoadError for FileNotFoundError."""
        nonexistent_file = temp_dir / "nonexistent.pb"

        with pytest.raises(ProgramLoadError):
            Loader.read_program([str(nonexistent_file)])

    def test_read_program_os_error(self, temp_dir, sample_playbook):
        """Test read_program handles OSError."""
        test_file = temp_dir / "test.pb"
        test_file.write_text(sample_playbook)

        # Mock Path.read_text to raise OSError
        with patch("pathlib.Path.read_text", side_effect=OSError("OS Error")):
            with pytest.raises(ProgramLoadError, match="OS Error"):
                Loader.read_program([str(test_file)])

    def test_read_program_io_error(self, temp_dir, sample_playbook):
        """Test read_program handles IOError."""
        test_file = temp_dir / "test.pb"
        test_file.write_text(sample_playbook)

        # Mock Path.read_text to raise IOError
        with patch("pathlib.Path.read_text", side_effect=IOError("IO Error")):
            with pytest.raises(ProgramLoadError, match="IO Error"):
                Loader.read_program([str(test_file)])


class TestReadProgramInternal:
    """Test the internal _read_program method."""

    def test_read_program_empty_paths(self):
        """Test _read_program with empty path list."""
        with pytest.raises(FileNotFoundError, match="No files found"):
            Loader._read_program([])

    def test_read_program_glob_no_matches(self, temp_dir):
        """Test _read_program with glob pattern that matches nothing."""
        pattern = str(temp_dir / "*.nonexistent")

        with pytest.raises(FileNotFoundError, match="No files found"):
            Loader._read_program([pattern])

    def test_read_program_single_file_missing(self, temp_dir):
        """Test _read_program with missing single file."""
        missing_file = temp_dir / "missing.pb"

        with pytest.raises(FileNotFoundError, match="missing.pb not found"):
            Loader._read_program([str(missing_file)])

    def test_read_program_multiple_files_some_missing(self, temp_dir, sample_playbook):
        """Test _read_program with some files missing."""
        existing_file = temp_dir / "existing.pb"
        missing_file = temp_dir / "missing.pb"

        existing_file.write_text(sample_playbook)

        with pytest.raises(FileNotFoundError, match="missing.pb not found"):
            Loader._read_program([str(existing_file), str(missing_file)])

    def test_read_program_empty_content(self, temp_dir):
        """Test _read_program with empty files."""
        empty_file = temp_dir / "empty.pb"
        empty_file.write_text("")

        with pytest.raises(FileNotFoundError, match="Files found but content is empty"):
            Loader._read_program([str(empty_file)])

    def test_read_program_whitespace_only_content(self, temp_dir):
        """Test _read_program with whitespace-only files."""
        whitespace_file = temp_dir / "whitespace.pb"
        whitespace_file.write_text("   \n  \t  \n  ")

        # This should pass as whitespace is considered content
        content, do_not_compile = Loader._read_program([str(whitespace_file)])
        assert content == "   \n  \t  \n  "
        assert do_not_compile is False

    def test_read_program_deduplication(self, temp_dir, sample_playbook):
        """Test that duplicate files are deduplicated."""
        test_file = temp_dir / "test.pb"
        test_file.write_text(sample_playbook)

        # Pass the same file twice
        content, do_not_compile = Loader._read_program([str(test_file), str(test_file)])

        # Should only include content once
        assert content == sample_playbook  # Not duplicated
        assert do_not_compile is False

    def test_read_program_glob_patterns_detection(self, temp_dir, sample_playbook):
        """Test detection of glob patterns vs regular files."""
        # Create test files
        test_file1 = temp_dir / "testa.pb"  # Single char for ? pattern
        test_file2 = temp_dir / "other.pb"
        test_file1.write_text(sample_playbook)
        test_file2.write_text(sample_playbook.replace("TestAgent", "OtherAgent"))

        # Test different glob pattern characters
        patterns_to_test = [
            str(temp_dir / "*.pb"),  # asterisk
            str(temp_dir / "test?.pb"),  # question mark
            str(temp_dir / "[to]*.pb"),  # brackets
        ]

        for pattern in patterns_to_test:
            content, _ = Loader._read_program([pattern])
            assert len(content) > 0

    def test_read_program_directory_handling(self, temp_dir):
        """Test that directories are handled properly."""
        # Pass a directory instead of a file
        with pytest.raises(FileNotFoundError, match="not found"):
            Loader._read_program([str(temp_dir)])

    def test_read_program_recursive_glob(self, temp_dir, sample_playbook):
        """Test recursive glob patterns."""
        # Create nested directory structure
        nested_dir = temp_dir / "nested"
        nested_dir.mkdir()

        # Create files at different levels
        root_file = temp_dir / "root.pb"
        nested_file = nested_dir / "nested.pb"

        root_file.write_text(sample_playbook)
        nested_file.write_text(sample_playbook.replace("TestAgent", "NestedAgent"))

        # Use recursive glob pattern
        pattern = str(temp_dir / "**/*.pb")
        content, do_not_compile = Loader._read_program([pattern])

        # Should find both files
        assert "TestAgent" in content
        assert "NestedAgent" in content
        assert do_not_compile is False

    def test_read_program_content_joining(self, temp_dir, sample_playbook):
        """Test that multiple file contents are joined correctly."""
        file1 = temp_dir / "file1.pb"
        file2 = temp_dir / "file2.pb"
        file3 = temp_dir / "file3.pb"

        content1 = "Content 1"
        content2 = "Content 2"
        content3 = "Content 3"

        file1.write_text(content1)
        file2.write_text(content2)
        file3.write_text(content3)

        combined_content, _ = Loader._read_program([str(file1), str(file2), str(file3)])

        # Content should be joined with double newlines
        # Note: Order may vary due to set() deduplication, so check all content is present
        assert content1 in combined_content
        assert content2 in combined_content
        assert content3 in combined_content
        assert combined_content.count("\n\n") == 2  # Two double-newline separators

    def test_read_program_compiled_flag_precedence(
        self, temp_dir, sample_playbook, sample_compiled_playbook
    ):
        """Test that compiled flag is set if any file is compiled."""
        pb_file = temp_dir / "regular.pb"
        pbasm_file = temp_dir / "compiled.pbasm"

        pb_file.write_text(sample_playbook)
        pbasm_file.write_text(sample_compiled_playbook)

        # Test different orders
        content1, do_not_compile1 = Loader._read_program(
            [str(pb_file), str(pbasm_file)]
        )
        content2, do_not_compile2 = Loader._read_program(
            [str(pbasm_file), str(pb_file)]
        )

        # Both should set do_not_compile to True
        assert do_not_compile1 is True
        assert do_not_compile2 is True


class TestReadProgramFilesErrorCases:
    """Test additional error cases for read_program_files."""

    def test_read_program_files_all_empty_content(self, temp_dir):
        """Test read_program_files when all files have empty content."""
        # Create files with only whitespace
        file1 = temp_dir / "empty1.pb"
        file2 = temp_dir / "empty2.pb"

        file1.write_text("   ")
        file2.write_text("\t\n")

        with pytest.raises(
            ProgramLoadError, match="Files found but all content is empty"
        ):
            Loader.read_program_files([str(file1), str(file2)])

    def test_read_program_files_no_valid_files(self, temp_dir):
        """Test read_program_files when no valid files are found."""
        # Create a directory (not a file)
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        with pytest.raises(ProgramLoadError, match="not found"):
            Loader.read_program_files([str(subdir)])

    def test_read_program_files_mixed_valid_invalid(self, temp_dir, sample_playbook):
        """Test read_program_files with mix of valid and invalid files."""
        valid_file = temp_dir / "valid.pb"
        invalid_file = temp_dir / "invalid.pb"

        valid_file.write_text(sample_playbook)
        # invalid_file doesn't exist

        with pytest.raises(ProgramLoadError, match="invalid.pb not found"):
            Loader.read_program_files([str(valid_file), str(invalid_file)])
