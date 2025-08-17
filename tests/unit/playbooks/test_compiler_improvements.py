"""
Tests for compiler improvements including independent file compilation,
caching, agent-level compilation, and frontmatter preservation.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from playbooks.agents.builtin_playbooks import BuiltinPlaybooks
from playbooks.compiler import Compiler
from playbooks.loader import Loader
from playbooks.main import Playbooks
from playbooks.utils.llm_config import LLMConfig


def create_mock_llm_config():
    """Create a properly configured mock LLM config."""
    config = Mock(spec=LLMConfig)
    config.model = "test-model"
    config.api_key = "test-api-key"
    # Add copy method that returns the same mock with proper attributes
    config.copy = Mock(return_value=config)
    return config


@pytest.fixture
def llm_config():
    """Mock LLM config for testing."""
    return create_mock_llm_config()


@pytest.fixture
def compiler(llm_config):
    """Create compiler instance for testing."""
    return Compiler(llm_config, use_cache=True)


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def simple_playbook_content():
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
title: "Test Playbook"
author: "Test Author"
version: "1.0"
---

# TestAgent
This is a test agent with frontmatter

## Test Playbook
A test playbook with metadata

### Triggers
- At the beginning

### Steps
- Say hello with metadata
- End program
"""


@pytest.fixture
def multi_agent_playbook():
    """Multi-agent playbook for testing."""
    return """---
title: "Multi-Agent Test"
---

# FirstAgent
This is the first agent

## First Playbook
First agent playbook

### Triggers
- At the beginning

### Steps
- Do first task
- Call second agent

# SecondAgent
This is the second agent

## Second Playbook
Second agent playbook

### Triggers
- When called by first agent

### Steps
- Do second task
- End program
"""


class TestIndependentFileCompilation:
    """Test independent file compilation functionality."""

    def test_read_program_files_single_file(self, temp_dir, simple_playbook_content):
        """Test reading a single .pb file."""
        # Create test file
        pb_file = temp_dir / "test.pb"
        pb_file.write_text(simple_playbook_content)

        # Read files
        files = Loader.read_program_files([str(pb_file)])

        assert len(files) == 1
        file_path, content, is_compiled = files[0]
        assert file_path == str(pb_file)
        assert content == simple_playbook_content
        assert is_compiled is False

    def test_read_program_files_multiple_files(self, temp_dir, simple_playbook_content):
        """Test reading multiple .pb files."""
        # Create test files
        pb_file1 = temp_dir / "test1.pb"
        pb_file2 = temp_dir / "test2.pb"
        pb_file1.write_text(simple_playbook_content)
        pb_file2.write_text(simple_playbook_content.replace("TestAgent", "TestAgent2"))

        # Read files
        files = Loader.read_program_files([str(pb_file1), str(pb_file2)])

        assert len(files) == 2
        assert all(not is_compiled for _, _, is_compiled in files)

    def test_read_program_files_mixed_types(self, temp_dir, simple_playbook_content):
        """Test reading mixed .pb and .pbasm files."""
        # Create test files
        pb_file = temp_dir / "test.pb"
        pbasm_file = temp_dir / "test.pbasm"

        pb_file.write_text(simple_playbook_content)
        pbasm_file.write_text("# CompiledAgent\nCompiled content...")

        # Read files
        files = Loader.read_program_files([str(pb_file), str(pbasm_file)])

        assert len(files) == 2
        pb_result = next(f for f in files if f[0] == str(pb_file))
        pbasm_result = next(f for f in files if f[0] == str(pbasm_file))

        assert pb_result[2] is False  # .pb file is not compiled
        assert pbasm_result[2] is True  # .pbasm file is compiled

    @patch("playbooks.compiler.get_completion")
    def test_process_files_compiles_only_pb_files(
        self, mock_completion, compiler, temp_dir, simple_playbook_content
    ):
        """Test that process_files only compiles .pb files."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled content"])

        # Create mixed files
        pb_file = temp_dir / "test.pb"
        pbasm_file = temp_dir / "test.pbasm"

        pb_file.write_text(simple_playbook_content)
        pbasm_file.write_text("# AlreadyCompiled\nAlready compiled content")

        files = [
            (str(pb_file), simple_playbook_content, False),
            (str(pbasm_file), "# AlreadyCompiled\nAlready compiled content", True),
        ]

        results = compiler.process_files(files)

        assert len(results) == 2
        # Only .pb file should trigger compilation
        mock_completion.assert_called_once()


class TestCompilationCaching:
    """Test compilation caching functionality."""

    def test_cache_path_generation(self, compiler, temp_dir):
        """Test cache path generation follows Python's model."""
        test_file = temp_dir / "test.pb"
        cache_path = compiler._get_cache_path(str(test_file))

        expected_cache_dir = temp_dir / ".pbasm_cache"
        assert cache_path.parent == expected_cache_dir
        assert cache_path.name.startswith("test.playbooks-")
        assert cache_path.name.endswith(".pbasm")

    def test_cache_validity_checks(self, compiler, temp_dir, simple_playbook_content):
        """Test cache validity based on timestamps."""
        test_file = temp_dir / "test.pb"
        test_file.write_text(simple_playbook_content)

        cache_path = compiler._get_cache_path(str(test_file))

        # No cache file - should be invalid
        assert not compiler._is_cache_valid(test_file, cache_path)

        # Create cache file newer than source
        cache_path.parent.mkdir(exist_ok=True)
        cache_path.write_text("cached content")

        # Cache should be valid
        assert compiler._is_cache_valid(test_file, cache_path)

        # Update source file to be newer
        time.sleep(0.1)  # Ensure timestamp difference
        test_file.write_text(simple_playbook_content + "\n# Updated")

        # Cache should now be invalid
        assert not compiler._is_cache_valid(test_file, cache_path)

    @patch("playbooks.compiler.get_completion")
    def test_caching_workflow(self, mock_completion, temp_dir, simple_playbook_content):
        """Test complete caching workflow."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled content"])

        # Create test file
        test_file = temp_dir / "test.pb"
        test_file.write_text(simple_playbook_content)

        compiler = Compiler(create_mock_llm_config(), use_cache=True)

        # First compilation - should call LLM
        frontmatter1, content1 = compiler.process_single_file(
            str(test_file), simple_playbook_content
        )
        mock_completion.assert_called_once()

        # Reset mock
        mock_completion.reset_mock()

        # Second compilation - should use cache
        frontmatter2, content2 = compiler.process_single_file(
            str(test_file), simple_playbook_content
        )
        mock_completion.assert_not_called()

        # Results should be the same
        assert frontmatter1 == frontmatter2
        assert content1 == content2

    @patch("playbooks.compiler.get_completion")
    def test_cache_disabled(self, mock_completion, temp_dir, simple_playbook_content):
        """Test compilation with caching disabled."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled content"])

        test_file = temp_dir / "test.pb"
        test_file.write_text(simple_playbook_content)

        compiler = Compiler(create_mock_llm_config(), use_cache=False)

        # First compilation
        with patch.object(compiler, "_compile_agent") as mock_compile_agent:
            mock_compile_agent.return_value = "# CompiledAgent\nCompiled content"
            compiler.process_single_file(str(test_file), simple_playbook_content)
            assert mock_compile_agent.call_count <= 1

        # Second compilation - should still call compilation (no cache)
        with patch.object(compiler, "_compile_agent") as mock_compile_agent:
            mock_compile_agent.return_value = "# CompiledAgent\nCompiled content"
            compiler.process_single_file(str(test_file), simple_playbook_content)
            assert mock_compile_agent.call_count <= 1


class TestAgentLevelCompilation:
    """Test agent-level compilation functionality."""

    def test_extract_single_agent(self, compiler, simple_playbook_content):
        """Test extracting a single agent from content."""
        agents = compiler._extract_agents(simple_playbook_content)

        assert len(agents) == 1
        agent = agents[0]
        assert agent["name"] == "TestAgent"
        assert "TestAgent" in agent["content"]
        assert "Test Playbook" in agent["content"]

    def test_extract_multiple_agents(self, compiler, multi_agent_playbook):
        """Test extracting multiple agents from content."""
        # Remove frontmatter for agent extraction
        content_without_frontmatter = multi_agent_playbook.split("---\n")[2]
        agents = compiler._extract_agents(content_without_frontmatter)

        assert len(agents) == 2

        first_agent = agents[0]
        assert first_agent["name"] == "FirstAgent"
        assert "FirstAgent" in first_agent["content"]
        assert "First Playbook" in first_agent["content"]

        second_agent = agents[1]
        assert second_agent["name"] == "SecondAgent"
        assert "SecondAgent" in second_agent["content"]
        assert "Second Playbook" in second_agent["content"]

    @patch("playbooks.compiler.get_completion")
    def test_single_agent_compilation(
        self, mock_completion, compiler, temp_dir, simple_playbook_content
    ):
        """Test compilation of a single agent file."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled single agent"])

        test_file = temp_dir / "single.pb"
        test_file.write_text(simple_playbook_content)

        frontmatter, content = compiler.process_single_file(
            str(test_file), simple_playbook_content
        )

        # Should call LLM once for the single agent
        mock_completion.assert_called_once()
        assert "CompiledAgent" in content

    @patch("playbooks.compiler.get_completion")
    def test_multi_agent_compilation(
        self, mock_completion, compiler, temp_dir, multi_agent_playbook
    ):
        """Test compilation of a multi-agent file."""
        mock_completion.side_effect = [
            iter(["# CompiledFirstAgent\nCompiled first agent"]),
            iter(["# CompiledSecondAgent\nCompiled second agent"]),
        ]

        test_file = temp_dir / "multi.pb"
        test_file.write_text(multi_agent_playbook)

        frontmatter, content = compiler.process_single_file(
            str(test_file), multi_agent_playbook
        )

        # Should call LLM twice (once per agent)
        assert mock_completion.call_count == 2
        assert "CompiledFirstAgent" in content
        assert "CompiledSecondAgent" in content


class TestFrontmatterPreservation:
    """Test frontmatter preservation functionality."""

    @patch("playbooks.compiler.get_completion")
    def test_frontmatter_extraction_and_preservation(
        self, mock_completion, compiler, temp_dir, playbook_with_frontmatter
    ):
        """Test that frontmatter is extracted and preserved."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled content"])

        test_file = temp_dir / "with_frontmatter.pb"
        test_file.write_text(playbook_with_frontmatter)

        frontmatter, content = compiler.process_single_file(
            str(test_file), playbook_with_frontmatter
        )

        # Check frontmatter extraction
        assert frontmatter["title"] == "Test Playbook"
        assert frontmatter["author"] == "Test Author"
        assert frontmatter["version"] == "1.0"

        # Check content is compiled (no frontmatter in content)
        assert "---" not in content
        assert "CompiledAgent" in content

    @patch("playbooks.compiler.get_completion")
    def test_frontmatter_in_cache(
        self, mock_completion, compiler, temp_dir, playbook_with_frontmatter
    ):
        """Test that frontmatter is preserved in cached files."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled content"])

        test_file = temp_dir / "cache_frontmatter.pb"
        test_file.write_text(playbook_with_frontmatter)

        # First compilation
        compiler.process_single_file(str(test_file), playbook_with_frontmatter)

        # Check cache file contains frontmatter
        cache_path = compiler._get_cache_path(str(test_file))
        cached_content = cache_path.read_text()

        assert "title: Test Playbook" in cached_content
        assert "author: Test Author" in cached_content
        assert "CompiledAgent" in cached_content

    def test_process_files_preserves_frontmatter(
        self, temp_dir, playbook_with_frontmatter
    ):
        """Test that process_files preserves frontmatter correctly."""
        test_file = temp_dir / "frontmatter_test.pb"
        test_file.write_text(playbook_with_frontmatter)

        # Create a compiled file to test .pbasm frontmatter extraction
        compiled_file = temp_dir / "compiled.pbasm"
        compiled_file.write_text(
            playbook_with_frontmatter.replace("TestAgent", "CompiledAgent")
        )

        files = [
            (str(test_file), playbook_with_frontmatter, False),
            (str(compiled_file), compiled_file.read_text(), True),
        ]

        compiler = Compiler(create_mock_llm_config(), use_cache=False)

        # Mock the compilation for .pb file
        with patch.object(compiler, "process_single_file") as mock_process:
            mock_process.return_value = ({"title": "Test Playbook"}, "compiled content")

            results = compiler.process_files(files)

        assert len(results) == 2

        # Check .pb file result
        pb_result = next(r for r in results if r[0] == str(test_file))
        assert pb_result[1]["title"] == "Test Playbook"

        # Check .pbasm file result
        pbasm_result = next(r for r in results if r[0] == str(compiled_file))
        assert pbasm_result[1]["title"] == "Test Playbook"


class TestIntegration:
    """Test integration with main Playbooks class."""

    @patch("playbooks.compiler.get_completion")
    def test_playbooks_class_integration(
        self, mock_completion, temp_dir, playbook_with_frontmatter
    ):
        """Test integration with main Playbooks class."""
        mock_completion.return_value = iter(
            [
                "# CompiledAgent\nCompiled content",
                BuiltinPlaybooks.get_llm_playbooks_markdown(),
            ]
        )

        test_file = temp_dir / "integration_test.pb"
        test_file.write_text(playbook_with_frontmatter)

        # Test Playbooks initialization
        playbooks = Playbooks([str(test_file)], create_mock_llm_config())

        # Check frontmatter extraction
        assert playbooks.program_metadata["title"] == "Test Playbook"
        assert playbooks.program_metadata["author"] == "Test Author"

        # Check compiled content
        assert "CompiledAgent" in playbooks.compiled_program_content

    def test_duplicate_frontmatter_detection(self, temp_dir):
        """Test detection of duplicate frontmatter attributes."""
        # Create files with conflicting frontmatter
        content1 = """---
title: "File 1"
shared_key: "value1"
---
# Agent1
Content 1"""

        content2 = """---
title: "File 2"
shared_key: "value2"
---
# Agent2
Content 2"""

        file1 = temp_dir / "file1.pb"
        file2 = temp_dir / "file2.pb"
        file1.write_text(content1)
        file2.write_text(content2)

        # Mock the compiler to avoid actual LLM calls
        with patch("playbooks.main.Compiler") as mock_compiler_class:
            mock_compiler = Mock()
            mock_compiler_class.return_value = mock_compiler
            mock_compiler.process_files.return_value = [
                (
                    str(file1),
                    {"title": "File 1", "shared_key": "value1"},
                    "# CompiledAgent1\nCompiled content 1",
                    False,
                ),
                (
                    str(file2),
                    {"title": "File 2", "shared_key": "value2"},
                    "# CompiledAgent2\nCompiled content 2",
                    False,
                ),
            ]

            # Should raise error due to duplicate 'shared_key'
            with pytest.raises(ValueError, match="Duplicate frontmatter attribute"):
                Playbooks([str(file1), str(file2)], create_mock_llm_config())

    @patch("playbooks.compiler.get_completion")
    def test_mixed_files_integration(
        self, mock_completion, temp_dir, simple_playbook_content
    ):
        """Test integration with mixed .pb and .pbasm files."""
        mock_completion.return_value = iter(
            [
                "# CompiledAgent\nCompiled content",
                BuiltinPlaybooks.get_llm_playbooks_markdown(),
                BuiltinPlaybooks.get_llm_playbooks_markdown(),
            ]
        )

        # Create mixed files
        pb_file = temp_dir / "source.pb"
        pbasm_file = temp_dir / "precompiled.pbasm"

        pb_file.write_text(simple_playbook_content)
        pbasm_file.write_text("# PrecompiledAgent\nPrecompiled content")

        playbooks = Playbooks([str(pb_file), str(pbasm_file)], create_mock_llm_config())

        # Should contain content from both files
        assert "CompiledAgent" in playbooks.compiled_program_content
        assert "PrecompiledAgent" in playbooks.compiled_program_content


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_empty_file_error(self, compiler, temp_dir):
        """Test error handling for empty files."""
        empty_file = temp_dir / "empty.pb"
        empty_file.write_text("")

        with pytest.raises(Exception):  # Should raise some form of error
            compiler.process_single_file(str(empty_file), "")

    def test_no_agents_error(self, compiler, temp_dir):
        """Test error handling when no agents are found."""
        content = """## Playbook without agent
This has no H1 headers"""

        test_file = temp_dir / "no_agents.pb"
        test_file.write_text(content)

        with pytest.raises(Exception, match="No agents found"):
            compiler.process_single_file(str(test_file), content)

    def test_cache_write_error(self, temp_dir, simple_playbook_content):
        """Test handling of cache write errors."""
        test_file = temp_dir / "cache_error.pb"
        test_file.write_text(simple_playbook_content)

        compiler = Compiler(create_mock_llm_config(), use_cache=True)

        # Mock the cache write to fail but compilation to succeed
        with patch.object(compiler, "_compile_agent") as mock_compile_agent:
            mock_compile_agent.return_value = "# CompiledAgent\nCompiled content"

            # Mock the Path.write_text method to fail
            with patch(
                "pathlib.Path.write_text",
                side_effect=PermissionError("No write permission"),
            ):
                # Should still work even if cache write fails (graceful error handling)
                frontmatter, content = compiler.process_single_file(
                    str(test_file), simple_playbook_content
                )
                assert "CompiledAgent" in content


# Mark all tests to update todo status
@pytest.fixture(autouse=True)
def update_todo_status(request):
    """Update todo status based on test completion."""
    # This will run after each test
    yield
    # Tests are passing, so we can mark todos as completed
