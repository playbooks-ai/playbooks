"""
Tests for Loader improvements including individual file reading and mixed file type support.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from playbooks.exceptions import ProgramLoadError
from playbooks.loader import Loader


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


class TestIndividualFileReading:
    """Test individual file reading functionality."""

    def test_read_single_pb_file(self, temp_dir, sample_playbook):
        """Test reading a single .pb file."""
        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(sample_playbook)

        # Read files
        result = Loader.read_program_files([str(test_file)])

        assert len(result) == 1
        file_path, content, is_compiled = result[0]
        assert file_path == str(test_file)
        assert content == sample_playbook
        assert is_compiled is False

    def test_read_single_pbasm_file(self, temp_dir, sample_compiled_playbook):
        """Test reading a single .pbasm file."""
        # Create test file
        test_file = temp_dir / "test.pbasm"
        test_file.write_text(sample_compiled_playbook)

        # Read files
        result = Loader.read_program_files([str(test_file)])

        assert len(result) == 1
        file_path, content, is_compiled = result[0]
        assert file_path == str(test_file)
        assert content == sample_compiled_playbook
        assert is_compiled is True

    def test_read_multiple_pb_files(self, temp_dir, sample_playbook):
        """Test reading multiple .pb files."""
        # Create test files
        test_file1 = temp_dir / "test1.pb"
        test_file2 = temp_dir / "test2.pb"
        test_file1.write_text(sample_playbook)
        test_file2.write_text(sample_playbook.replace("TestAgent", "TestAgent2"))

        # Read files
        result = Loader.read_program_files([str(test_file1), str(test_file2)])

        assert len(result) == 2

        # Check first file
        file1_result = next(r for r in result if r[0] == str(test_file1))
        assert file1_result[1] == sample_playbook
        assert file1_result[2] is False

        # Check second file
        file2_result = next(r for r in result if r[0] == str(test_file2))
        assert "TestAgent2" in file2_result[1]
        assert file2_result[2] is False

    def test_read_mixed_file_types(
        self, temp_dir, sample_playbook, sample_compiled_playbook
    ):
        """Test reading mixed .pb and .pbasm files."""
        # Create test files
        pb_file = temp_dir / "source.pb"
        pbasm_file = temp_dir / "compiled.pbasm"
        pb_file.write_text(sample_playbook)
        pbasm_file.write_text(sample_compiled_playbook)

        # Read files
        result = Loader.read_program_files([str(pb_file), str(pbasm_file)])

        assert len(result) == 2

        # Check .pb file
        pb_result = next(r for r in result if r[0] == str(pb_file))
        assert pb_result[1] == sample_playbook
        assert pb_result[2] is False

        # Check .pbasm file
        pbasm_result = next(r for r in result if r[0] == str(pbasm_file))
        assert pbasm_result[1] == sample_compiled_playbook
        assert pbasm_result[2] is True


class TestGlobPatternSupport:
    """Test glob pattern support in file reading."""

    def test_glob_pattern_pb_files(self, temp_dir, sample_playbook):
        """Test glob pattern for .pb files."""
        # Create multiple test files
        for i in range(3):
            test_file = temp_dir / f"test{i}.pb"
            test_file.write_text(sample_playbook.replace("TestAgent", f"TestAgent{i}"))

        # Create a non-matching file
        other_file = temp_dir / "other.txt"
        other_file.write_text("Not a playbook")

        # Read with glob pattern
        pattern = str(temp_dir / "*.pb")
        result = Loader.read_program_files([pattern])

        # Should find all 3 .pb files but not the .txt file
        assert len(result) == 3
        assert all(file_path.endswith(".pb") for file_path, _, _ in result)
        assert all(not is_compiled for _, _, is_compiled in result)

    def test_glob_pattern_mixed_types(
        self, temp_dir, sample_playbook, sample_compiled_playbook
    ):
        """Test glob pattern that matches both .pb and .pbasm files."""
        # Create mixed files
        pb_file = temp_dir / "test1.pb"
        pbasm_file = temp_dir / "test2.pbasm"
        pb_file.write_text(sample_playbook)
        pbasm_file.write_text(sample_compiled_playbook)

        # Read with glob pattern
        pattern = str(temp_dir / "test*")
        result = Loader.read_program_files([pattern])

        assert len(result) == 2

        # Check that file types are correctly identified
        pb_result = next(r for r in result if r[0].endswith(".pb"))
        pbasm_result = next(r for r in result if r[0].endswith(".pbasm"))

        assert pb_result[2] is False  # .pb is not compiled
        assert pbasm_result[2] is True  # .pbasm is compiled

    def test_multiple_glob_patterns(self, temp_dir, sample_playbook):
        """Test multiple glob patterns in one call."""
        # Create files in subdirectories
        subdir1 = temp_dir / "dir1"
        subdir2 = temp_dir / "dir2"
        subdir1.mkdir()
        subdir2.mkdir()

        file1 = subdir1 / "test1.pb"
        file2 = subdir2 / "test2.pb"
        file1.write_text(sample_playbook.replace("TestAgent", "Agent1"))
        file2.write_text(sample_playbook.replace("TestAgent", "Agent2"))

        # Read with multiple patterns
        patterns = [str(subdir1 / "*.pb"), str(subdir2 / "*.pb")]
        result = Loader.read_program_files(patterns)

        assert len(result) == 2
        assert any("Agent1" in content for _, content, _ in result)
        assert any("Agent2" in content for _, content, _ in result)

    def test_recursive_glob_pattern(self, temp_dir, sample_playbook):
        """Test recursive glob pattern."""
        # Create nested directory structure
        nested_dir = temp_dir / "nested" / "deep"
        nested_dir.mkdir(parents=True)

        # Create files at different levels
        root_file = temp_dir / "root.pb"
        nested_file = nested_dir / "nested.pb"
        root_file.write_text(sample_playbook.replace("TestAgent", "RootAgent"))
        nested_file.write_text(sample_playbook.replace("TestAgent", "NestedAgent"))

        # Read with recursive pattern
        pattern = str(temp_dir / "**/*.pb")
        result = Loader.read_program_files([pattern])

        assert len(result) == 2
        assert any("RootAgent" in content for _, content, _ in result)
        assert any("NestedAgent" in content for _, content, _ in result)


class TestFileExtensionDetection:
    """Test file extension detection for compilation status."""

    def test_pb_extension_detection(self, temp_dir, sample_playbook):
        """Test .pb extension is detected as not compiled."""
        test_file = temp_dir / "test.pb"
        test_file.write_text(sample_playbook)

        result = Loader.read_program_files([str(test_file)])
        _, _, is_compiled = result[0]
        assert is_compiled is False

    def test_pbasm_extension_detection(self, temp_dir, sample_compiled_playbook):
        """Test .pbasm extension is detected as compiled."""
        test_file = temp_dir / "test.pbasm"
        test_file.write_text(sample_compiled_playbook)

        result = Loader.read_program_files([str(test_file)])
        _, _, is_compiled = result[0]
        assert is_compiled is True

    def test_unknown_extension_default(self, temp_dir, sample_playbook):
        """Test unknown extension defaults to not compiled."""
        test_file = temp_dir / "test.unknown"
        test_file.write_text(sample_playbook)

        result = Loader.read_program_files([str(test_file)])
        _, _, is_compiled = result[0]
        assert is_compiled is False  # Should default to False

    def test_no_extension_default(self, temp_dir, sample_playbook):
        """Test file with no extension defaults to not compiled."""
        test_file = temp_dir / "test_no_extension"
        test_file.write_text(sample_playbook)

        result = Loader.read_program_files([str(test_file)])
        _, _, is_compiled = result[0]
        assert is_compiled is False


class TestErrorHandling:
    """Test error handling in file reading."""

    def test_nonexistent_file(self, temp_dir):
        """Test handling of nonexistent files."""
        nonexistent_file = temp_dir / "nonexistent.pb"

        with pytest.raises(ProgramLoadError):
            Loader.read_program_files([str(nonexistent_file)])

    def test_empty_file_list(self):
        """Test handling of empty file list."""
        with pytest.raises(ProgramLoadError):
            Loader.read_program_files([])

    def test_directory_instead_of_file(self, temp_dir):
        """Test handling when directory is passed instead of file."""
        # This should either raise an error or handle gracefully
        # depending on implementation choice
        with pytest.raises(ProgramLoadError):
            Loader.read_program_files([str(temp_dir)])

    def test_permission_denied(self, temp_dir, sample_playbook):
        """Test handling of permission denied errors."""
        test_file = temp_dir / "test.pb"
        test_file.write_text(sample_playbook)

        # Mock permission error
        with patch(
            "pathlib.Path.read_text", side_effect=PermissionError("Permission denied")
        ):
            with pytest.raises(ProgramLoadError):
                Loader.read_program_files([str(test_file)])

    def test_invalid_glob_pattern(self):
        """Test handling of invalid glob patterns."""
        # Some invalid patterns might cause issues
        invalid_pattern = "[invalid_bracket"

        # Should either handle gracefully or raise appropriate error
        with pytest.raises(ProgramLoadError):
            Loader.read_program_files([invalid_pattern])


class TestFileOrdering:
    """Test file ordering and consistency."""

    def test_deterministic_ordering(self, temp_dir, sample_playbook):
        """Test that file ordering is deterministic."""
        # Create multiple files
        files = []
        for i in range(5):
            test_file = temp_dir / f"test{i:02d}.pb"
            test_file.write_text(sample_playbook.replace("TestAgent", f"Agent{i}"))
            files.append(str(test_file))

        # Read files multiple times
        result1 = Loader.read_program_files(files)
        result2 = Loader.read_program_files(files)

        # Results should be in the same order
        assert [r[0] for r in result1] == [r[0] for r in result2]

    def test_glob_ordering_consistency(self, temp_dir, sample_playbook):
        """Test that glob results are consistently ordered."""
        # Create files that would be in different order when sorted
        files = ["z_last.pb", "a_first.pb", "m_middle.pb"]
        for filename in files:
            test_file = temp_dir / filename
            test_file.write_text(sample_playbook)

        # Read with glob pattern multiple times
        pattern = str(temp_dir / "*.pb")
        result1 = Loader.read_program_files([pattern])
        result2 = Loader.read_program_files([pattern])

        # Results should be in the same order both times
        assert [r[0] for r in result1] == [r[0] for r in result2]


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_legacy_single_file_usage(self, temp_dir, sample_playbook):
        """Test that legacy single file usage still works."""
        test_file = temp_dir / "test.pb"
        test_file.write_text(sample_playbook)

        # Should work with single file (not in list)
        # Note: This depends on implementation - may need to be a list
        result = Loader.read_program_files([str(test_file)])
        assert len(result) == 1

    def test_return_format_consistency(self, temp_dir, sample_playbook):
        """Test that return format is consistent with expectations."""
        test_file = temp_dir / "test.pb"
        test_file.write_text(sample_playbook)

        result = Loader.read_program_files([str(test_file)])

        # Should return list of tuples
        assert isinstance(result, list)
        assert len(result) == 1

        # Each tuple should have 3 elements: path, content, is_compiled
        tuple_result = result[0]
        assert isinstance(tuple_result, tuple)
        assert len(tuple_result) == 3

        file_path, content, is_compiled = tuple_result
        assert isinstance(file_path, str)
        assert isinstance(content, str)
        assert isinstance(is_compiled, bool)
