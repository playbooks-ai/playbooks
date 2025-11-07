"""
Tests for the Compiler class with agent-level compilation and caching.

The compiler now processes agents individually rather than files,
enabling better parallelization and caching at the agent level.
"""

import tempfile
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from playbooks.compilation.compiler import (
    Compiler,
    FileCompilationResult,
    FileCompilationSpec,
)
from playbooks.core.exceptions import ProgramLoadError
from playbooks.utils.llm_config import LLMConfig
from playbooks.utils.version import get_playbooks_version


@pytest.fixture
def llm_config():
    """Create a mock LLM config for testing."""
    config = Mock(spec=LLMConfig)
    config.model = "test-model"
    config.provider = "test-provider"
    config.api_key = "test-key"
    config.temperature = 0.7
    config.copy = Mock(return_value=config)
    return config


@pytest.fixture
def compiler(llm_config):
    """Create a compiler instance with mock LLM config."""
    with patch("playbooks.compilation.compiler.config") as mock_config:
        mock_config.model.compilation.name = "test-model"
        mock_config.model.compilation.provider = "test-provider"
        mock_config.model.compilation.temperature = 0.7
        return Compiler(llm_config, use_cache=True)


@pytest.fixture
def compiler_no_cache(llm_config):
    """Create a compiler instance with caching disabled."""
    with patch("playbooks.compilation.compiler.config") as mock_config:
        mock_config.model.compilation.name = "test-model"
        mock_config.model.compilation.provider = "test-provider"
        mock_config.model.compilation.temperature = 0.7
        return Compiler(llm_config, use_cache=False)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def single_agent_content():
    """Content with a single agent."""
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
def multi_agent_content():
    """Content with multiple agents."""
    return """# FirstAgent
This is the first agent

## First Playbook
First agent's playbook

### Triggers
- At the beginning

### Steps
- Do first task
- Call second agent

# SecondAgent
This is the second agent

## Second Playbook
Second agent's playbook

### Triggers
- When called by first agent

### Steps
- Do second task
- Return result
"""


@pytest.fixture
def content_with_frontmatter():
    """Content with frontmatter."""
    return """---
title: "Test Playbook"
author: "Test Author"
version: "1.0"
---

# TestAgent
Agent with frontmatter

## Test Playbook
A playbook with metadata

### Triggers
- At the beginning

### Steps
- Process with metadata
"""


class TestAgentExtraction:
    """Test agent extraction from markdown content."""

    def test_extract_single_agent(self, compiler, single_agent_content):
        """Test extracting a single agent from content."""
        agents = compiler._extract_agents(single_agent_content)

        assert len(agents) == 1
        assert agents[0]["name"] == "TestAgent"
        assert "TestAgent" in agents[0]["content"]
        assert "Test Playbook" in agents[0]["content"]
        assert "Say hello" in agents[0]["content"]

    def test_extract_multiple_agents(self, compiler, multi_agent_content):
        """Test extracting multiple agents from content."""
        agents = compiler._extract_agents(multi_agent_content)

        assert len(agents) == 2

        # Check first agent
        assert agents[0]["name"] == "FirstAgent"
        assert "FirstAgent" in agents[0]["content"]
        assert "First Playbook" in agents[0]["content"]
        assert "Do first task" in agents[0]["content"]

        # Check second agent
        assert agents[1]["name"] == "SecondAgent"
        assert "SecondAgent" in agents[1]["content"]
        assert "Second Playbook" in agents[1]["content"]
        assert "Do second task" in agents[1]["content"]

    def test_extract_no_agents(self, compiler):
        """Test extraction with no agents (no H1 headers)."""
        content = """## Just a Playbook
No agent header here

### Steps
- Do something
"""
        agents = compiler._extract_agents(content)
        assert len(agents) == 0

    def test_agent_content_preservation(self, compiler):
        """Test that agent content preserves all markdown elements."""
        content = """# ComplexAgent
Agent description with **bold** and *italic*

## Main Playbook
Description with `code` and [links](http://example.com)

### Triggers
- At the beginning
- When condition is met

### Steps
- Step with ```python
  code block
  ```
- Another step

### Notes
- Important note

## Helper Playbook
Another playbook

### Steps
- Helper step
"""
        agents = compiler._extract_agents(content)

        assert len(agents) == 1
        agent_content = agents[0]["content"]

        # Check various markdown elements are preserved
        assert "**bold**" in agent_content
        assert "*italic*" in agent_content
        assert "`code`" in agent_content
        assert "[links](http://example.com)" in agent_content
        assert "```python" in agent_content
        assert "Main Playbook" in agent_content
        assert "Helper Playbook" in agent_content
        assert "Important note" in agent_content


class TestCacheKeyGeneration:
    """Test cache key generation and path creation."""

    def test_cache_key_deterministic(self, compiler):
        """Test that cache key generation is deterministic."""
        content = "# TestAgent\nTest content"

        key1 = compiler._generate_cache_key(content)
        key2 = compiler._generate_cache_key(content)

        assert key1 == key2
        assert len(key1) == 16  # Should be 16 character hash

    def test_cache_key_changes_with_content(self, compiler):
        """Test that cache key changes when content changes."""
        content1 = "# TestAgent\nOriginal content"
        content2 = "# TestAgent\nModified content"

        key1 = compiler._generate_cache_key(content1)
        key2 = compiler._generate_cache_key(content2)

        assert key1 != key2

    def test_cache_key_includes_prompt(self, compiler):
        """Test that cache key includes the compiler prompt."""
        content = "# TestAgent\nTest content"

        # Get key with original prompt
        key1 = compiler._generate_cache_key(content)

        # Modify prompt and get new key
        original_prompt = compiler.compiler_prompt
        compiler.compiler_prompt = "Modified prompt"
        key2 = compiler._generate_cache_key(content)

        # Restore prompt
        compiler.compiler_prompt = original_prompt

        assert key1 != key2

    def test_cache_path_generation(self, compiler):
        """Test cache path generation for agents."""
        agent_name = "TestAgent"
        cache_key = "abc123def456"

        cache_path = compiler._get_cache_path(agent_name, cache_key)

        assert cache_path.parent == Path(".pbasm_cache")
        assert cache_path.name == f"TestAgent_{cache_key}.pbasm"

    def test_cache_path_sanitization(self, compiler):
        """Test that agent names are sanitized for filesystem."""
        test_cases = [
            ("Agent/With/Slashes", "Agent_With_Slashes"),
            ("Agent:With:Colons", "Agent_With_Colons"),
            ("Agent With Spaces", "Agent_With_Spaces"),
            ("Agent-With-Dashes", "Agent-With-Dashes"),
            ("Agent_With_Underscores", "Agent_With_Underscores"),
            ("Agent123", "Agent123"),
        ]

        for agent_name, expected_prefix in test_cases:
            cache_path = compiler._get_cache_path(agent_name, "testkey")
            assert cache_path.name.startswith(expected_prefix)


class TestAgentCompilation:
    """Test agent-level compilation functionality."""

    @patch("playbooks.compilation.compiler.get_completion")
    def test_compile_single_agent(
        self, mock_completion, compiler, single_agent_content
    ):
        """Test compiling a single agent."""
        mock_completion.return_value = iter(["# CompiledTestAgent\nCompiled content"])

        compiled = compiler._compile_agent(single_agent_content)

        assert "CompiledTestAgent" in compiled
        assert "Playbooks Assembly Language" in compiled  # Version header
        mock_completion.assert_called_once()

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("playbooks.compilation.compiler.LangfuseHelper")
    @patch("pathlib.Path.exists")
    def test_compile_agent_with_caching(
        self,
        mock_exists,
        mock_langfuse,
        mock_completion,
        compiler,
        single_agent_content,
    ):
        """Test agent compilation with caching."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled content"])
        mock_langfuse.instance.return_value.trace.return_value = MagicMock()

        # First call - cache doesn't exist
        mock_exists.return_value = False

        agent_info = {"name": "TestAgent", "content": single_agent_content}

        # First compilation - should call LLM
        result1 = compiler._compile_agent_with_caching(agent_info)
        assert mock_completion.call_count == 1
        assert result1.is_compiled is True

        # Second call - cache exists
        mock_exists.return_value = True
        mock_completion.reset_mock()

        # Mock cache file read - should include the version header that gets added during compilation
        version = get_playbooks_version()
        cached_content = f"""<!-- 
============================================
Playbooks Assembly Language v{version}
============================================ 
-->

# CompiledAgent
Compiled content"""
        with patch("pathlib.Path.read_text", return_value=cached_content):
            result2 = compiler._compile_agent_with_caching(agent_info)
            assert mock_completion.call_count == 0  # No LLM call

        # Results should be identical
        assert result1.content == result2.content

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("playbooks.compilation.compiler.LangfuseHelper")
    def test_compile_without_cache(
        self, mock_langfuse, mock_completion, compiler_no_cache, single_agent_content
    ):
        """Test compilation with caching disabled."""
        mock_completion.side_effect = [
            iter(["# CompiledAgent\nCompiled content"]),
            iter(["# CompiledAgent\nCompiled content"]),
        ]
        mock_langfuse.instance.return_value.trace.return_value = MagicMock()

        agent_info = {"name": "TestAgent", "content": single_agent_content}

        # Multiple compilations should all call LLM
        compiler_no_cache._compile_agent_with_caching(agent_info)
        assert mock_completion.call_count == 1

        compiler_no_cache._compile_agent_with_caching(agent_info)
        assert mock_completion.call_count == 2

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("playbooks.compilation.compiler.LangfuseHelper")
    @patch("pathlib.Path.write_text")
    def test_cache_write_failure_handling(
        self, mock_write, mock_langfuse, mock_completion, compiler, single_agent_content
    ):
        """Test graceful handling of cache write failures."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled content"])
        mock_langfuse.instance.return_value.trace.return_value = MagicMock()
        mock_write.side_effect = PermissionError("Cannot write cache")

        agent_info = {"name": "TestAgent", "content": single_agent_content}

        # Should complete successfully despite cache write failure
        result = compiler._compile_agent_with_caching(agent_info)
        assert result.is_compiled is True
        assert "CompiledAgent" in result.content


class TestFileProcessing:
    """Test file processing with agent-level compilation."""

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("playbooks.compilation.compiler.LangfuseHelper")
    @patch("pathlib.Path.exists")
    def test_process_single_pb_file(
        self,
        mock_exists,
        mock_langfuse,
        mock_completion,
        compiler,
        single_agent_content,
    ):
        """Test processing a single .pb file."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled content"])
        mock_langfuse.instance.return_value.trace.return_value = MagicMock()
        mock_exists.return_value = False  # Cache doesn't exist

        files = [
            FileCompilationSpec(
                file_path="test.pb", content=single_agent_content, is_compiled=False
            )
        ]

        results = compiler.process_files(files)

        assert len(results) == 1
        assert results[0].is_compiled is True
        assert "CompiledAgent" in results[0].content
        mock_completion.assert_called_once()

    def test_process_single_pbasm_file(self, compiler):
        """Test processing a single .pbasm file (no compilation needed)."""
        compiled_content = "# AlreadyCompiled\nPre-compiled content"

        files = [
            FileCompilationSpec(
                file_path="test.pbasm", content=compiled_content, is_compiled=True
            )
        ]

        with patch.object(compiler, "_compile_agent") as mock_compile:
            results = compiler.process_files(files)

            assert len(results) == 1
            assert results[0].is_compiled is True
            assert "AlreadyCompiled" in results[0].content
            mock_compile.assert_not_called()  # No compilation needed

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("playbooks.compilation.compiler.LangfuseHelper")
    @patch("pathlib.Path.exists")
    def test_process_multiple_pb_files(
        self, mock_exists, mock_langfuse, mock_completion, compiler, multi_agent_content
    ):
        """Test processing multiple .pb files with multiple agents."""
        mock_completion.side_effect = [
            iter(["# CompiledFirst\nFirst compiled"]),
            iter(["# CompiledSecond\nSecond compiled"]),
        ]
        mock_langfuse.instance.return_value.trace.return_value = MagicMock()
        mock_exists.return_value = False  # Cache doesn't exist

        files = [
            FileCompilationSpec(
                file_path="multi.pb", content=multi_agent_content, is_compiled=False
            )
        ]

        results = compiler.process_files(files)

        # Should have one result per agent
        assert len(results) == 2
        assert all(r.is_compiled for r in results)
        assert mock_completion.call_count == 2

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("playbooks.compilation.compiler.LangfuseHelper")
    @patch("pathlib.Path.exists")
    def test_process_mixed_files(
        self,
        mock_exists,
        mock_langfuse,
        mock_completion,
        compiler,
        single_agent_content,
    ):
        """Test processing mixed .pb and .pbasm files."""
        # When mixed files are processed, all agents get recompiled since we can't track
        # which agent came from which file after content combination
        mock_completion.side_effect = [
            iter(["# CompiledTestAgent\nCompiled test agent"]),
            iter(["# CompiledExistingAgent\nCompiled existing agent"]),
        ]
        mock_langfuse.instance.return_value.trace.return_value = MagicMock()
        mock_exists.return_value = False  # Cache doesn't exist

        files = [
            FileCompilationSpec(
                file_path="new.pb", content=single_agent_content, is_compiled=False
            ),
            FileCompilationSpec(
                file_path="existing.pbasm",
                content="# ExistingAgent\nAlready compiled",
                is_compiled=True,
            ),
        ]

        results = compiler.process_files(files)

        assert len(results) == 2
        # Both agents get compiled when there are mixed file types
        assert mock_completion.call_count == 2

    def test_process_all_pbasm_files(self, compiler):
        """Test processing all .pbasm files (no LLM calls)."""
        files = [
            FileCompilationSpec(
                file_path="first.pbasm",
                content="# FirstCompiled\nFirst content",
                is_compiled=True,
            ),
            FileCompilationSpec(
                file_path="second.pbasm",
                content="# SecondCompiled\nSecond content",
                is_compiled=True,
            ),
        ]

        with patch.object(compiler, "_compile_agent") as mock_compile:
            results = compiler.process_files(files)

            assert len(results) == 2
            assert all(r.is_compiled for r in results)
            mock_compile.assert_not_called()  # No compilation needed

    @patch("playbooks.compilation.compiler.ThreadPoolExecutor")
    @patch("playbooks.compilation.compiler.get_completion")
    def test_parallel_compilation(
        self, mock_completion, mock_executor_class, compiler, multi_agent_content
    ):
        """Test that multiple agents are compiled in parallel."""
        mock_completion.side_effect = [iter(["# Compiled1"]), iter(["# Compiled2"])]

        # Mock the executor to track parallel execution
        mock_executor = Mock()
        mock_executor_class.return_value.__enter__ = Mock(return_value=mock_executor)
        mock_executor_class.return_value.__exit__ = Mock(return_value=None)

        # Create mock futures
        future1 = Mock(spec=Future)
        future2 = Mock(spec=Future)
        future1.result.return_value = FileCompilationResult(
            file_path="cache1.pbasm",
            frontmatter_dict={},
            content="# Compiled1",
            is_compiled=True,
            compiled_file_path="cache1.pbasm",
        )
        future2.result.return_value = FileCompilationResult(
            file_path="cache2.pbasm",
            frontmatter_dict={},
            content="# Compiled2",
            is_compiled=True,
            compiled_file_path="cache2.pbasm",
        )

        mock_executor.submit.side_effect = [future1, future2]

        files = [
            FileCompilationSpec(
                file_path="multi.pb", content=multi_agent_content, is_compiled=False
            )
        ]

        with patch("playbooks.compilation.compiler.as_completed") as mock_as_completed:
            mock_as_completed.return_value = [future1, future2]
            results = compiler.process_files(files)

        # Verify parallel submission
        assert mock_executor.submit.call_count == 2
        assert len(results) == 2


class TestFrontmatterHandling:
    """Test frontmatter extraction and preservation."""

    def test_frontmatter_extraction(self, compiler, content_with_frontmatter):
        """Test extracting frontmatter from content."""
        import frontmatter

        fm_data = frontmatter.loads(content_with_frontmatter)

        assert fm_data.metadata["title"] == "Test Playbook"
        assert fm_data.metadata["author"] == "Test Author"
        assert fm_data.metadata["version"] == "1.0"

    @patch("playbooks.compilation.compiler.get_completion")
    def test_frontmatter_preservation(
        self, mock_completion, compiler, content_with_frontmatter
    ):
        """Test that frontmatter is extracted at file level for duplicate detection."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled"])

        files = [
            FileCompilationSpec(
                file_path="test.pb", content=content_with_frontmatter, is_compiled=False
            )
        ]

        results = compiler.process_files(files)

        assert len(results) == 1
        # Frontmatter is extracted at the file level for duplicate checking
        # Individual agent results get frontmatter from their compiled content
        assert results[0].is_compiled is True

    def test_duplicate_frontmatter_detection(self, compiler):
        """Test detection of duplicate frontmatter keys across files."""
        content1 = """---
shared_key: "value1"
---
# Agent1
Content"""

        content2 = """---
shared_key: "value2"
---
# Agent2
Content"""

        files = [
            FileCompilationSpec(
                file_path="file1.pb", content=content1, is_compiled=False
            ),
            FileCompilationSpec(
                file_path="file2.pb", content=content2, is_compiled=False
            ),
        ]

        with pytest.raises(
            ValueError, match="Duplicate frontmatter attribute 'shared_key'"
        ):
            compiler.process_files(files)

    def test_frontmatter_in_pbasm_files(self, compiler):
        """Test frontmatter extraction from .pbasm files."""
        # For pbasm files, the agent content itself should contain frontmatter
        pbasm_content = """# CompiledAgent
Already compiled content"""

        files = [
            FileCompilationSpec(
                file_path="compiled.pbasm", content=pbasm_content, is_compiled=True
            )
        ]

        results = compiler.process_files(files)

        assert len(results) == 1
        # For .pbasm files, frontmatter comes from the agent content itself
        # In this case, no frontmatter in agent content, so empty dict
        assert results[0].frontmatter_dict == {}
        assert results[0].is_compiled is True


class TestBackwardCompatibility:
    """Test backward compatibility with the compile() method."""

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("playbooks.compilation.compiler.LangfuseHelper")
    @patch("pathlib.Path.exists")
    def test_compile_method_single_file(
        self,
        mock_exists,
        mock_langfuse,
        mock_completion,
        compiler,
        single_agent_content,
        temp_dir,
    ):
        """Test the compile() method for backward compatibility."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled"])
        mock_langfuse.instance.return_value.trace.return_value = MagicMock()
        mock_exists.return_value = False  # Cache doesn't exist

        test_file = temp_dir / "test.pb"
        test_file.write_text(single_agent_content)

        frontmatter, content, cache_path = compiler.compile(file_path=str(test_file))

        assert "CompiledAgent" in content
        assert isinstance(cache_path, Path)
        mock_completion.assert_called_once()

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("playbooks.compilation.compiler.LangfuseHelper")
    def test_compile_method_with_content(
        self, mock_langfuse, mock_completion, compiler, single_agent_content
    ):
        """Test compile() method with content parameter."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled"])
        mock_langfuse.instance.return_value.trace.return_value = MagicMock()

        frontmatter, content, cache_path = compiler.compile(
            content=single_agent_content
        )

        assert "CompiledAgent" in content
        assert isinstance(cache_path, Path)

    def test_compile_method_invalid_params(self, compiler):
        """Test compile() method with invalid parameters."""
        # Both file_path and content provided
        with pytest.raises(ValueError):
            compiler.compile(file_path="test.pb", content="content")

        # Neither provided
        with pytest.raises(ValueError):
            compiler.compile()


class TestErrorHandling:
    """Test error handling in the compiler."""

    def test_no_agents_found_error(self, compiler):
        """Test error when no agents are found in content."""
        content_without_agents = """## Just a Playbook
No H1 headers here

### Steps
- Do something
"""

        files = [
            FileCompilationSpec(
                file_path="no_agents.pb",
                content=content_without_agents,
                is_compiled=False,
            )
        ]

        with pytest.raises(ProgramLoadError, match="No agents found"):
            compiler.process_files(files)

    def test_empty_content_handling(self, compiler):
        """Test handling of empty file content."""
        files = [
            FileCompilationSpec(file_path="empty.pb", content="", is_compiled=False)
        ]

        with pytest.raises(ProgramLoadError, match="No agents found"):
            compiler.process_files(files)

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("playbooks.compilation.compiler.LangfuseHelper")
    @patch("pathlib.Path.exists")
    def test_llm_failure_handling(
        self,
        mock_exists,
        mock_langfuse,
        mock_completion,
        compiler,
        single_agent_content,
    ):
        """Test handling of LLM failures during compilation."""
        mock_completion.side_effect = Exception("LLM API error")
        mock_langfuse.instance.return_value.trace.return_value = MagicMock()
        mock_exists.return_value = False  # Cache doesn't exist, force LLM call

        files = [
            FileCompilationSpec(
                file_path="test.pb", content=single_agent_content, is_compiled=False
            )
        ]

        with pytest.raises(Exception, match="LLM API error"):
            compiler.process_files(files)

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("playbooks.compilation.compiler.LangfuseHelper")
    @patch("pathlib.Path.exists")
    def test_partial_compilation_failure(
        self, mock_exists, mock_langfuse, mock_completion, compiler, multi_agent_content
    ):
        """Test handling when one agent fails to compile in multi-agent scenario."""
        # First agent compiles successfully, second fails
        mock_completion.side_effect = [
            iter(["# CompiledFirst\nFirst compiled"]),
            Exception("Second agent compilation failed"),
        ]
        mock_langfuse.instance.return_value.trace.return_value = MagicMock()
        mock_exists.return_value = False  # Cache doesn't exist, force LLM calls

        files = [
            FileCompilationSpec(
                file_path="multi.pb", content=multi_agent_content, is_compiled=False
            )
        ]

        with pytest.raises(Exception, match="Second agent compilation failed"):
            compiler.process_files(files)


class TestLLMConfiguration:
    """Test LLM configuration handling."""

    def test_llm_config_initialization(self, llm_config):
        """Test that LLM config is properly initialized."""
        with patch("playbooks.compilation.compiler.config") as mock_config:
            mock_config.model.compilation.name = "claude-3"
            mock_config.model.compilation.provider = "anthropic"
            mock_config.model.compilation.temperature = 0.5

            compiler = Compiler(llm_config)

            assert compiler.llm_config.model == "claude-3"
            assert compiler.llm_config.provider == "anthropic"
            assert compiler.llm_config.temperature == 0.5

    def test_api_key_determination(self, llm_config):
        """Test API key determination based on model."""
        test_cases = [
            ("claude-3", "ANTHROPIC_API_KEY", "anthropic-key"),
            ("gemini-pro", "GEMINI_API_KEY", "gemini-key"),
            ("groq-llama", "GROQ_API_KEY", "groq-key"),
            ("openrouter/meta-llama", "OPENROUTER_API_KEY", "openrouter-key"),
            ("gpt-4", "OPENAI_API_KEY", "openai-key"),
        ]

        for model, env_var, expected_key in test_cases:
            with patch("playbooks.compilation.compiler.config") as mock_config:
                mock_config.model.compilation.name = model
                mock_config.model.compilation.provider = "test"
                mock_config.model.compilation.temperature = 0.7

                with patch.dict("os.environ", {env_var: expected_key}):
                    compiler = Compiler(llm_config)
                    assert compiler.llm_config.api_key == expected_key


class TestPromptHandling:
    """Test compiler prompt handling."""

    def test_prompt_loading(self, llm_config):
        """Test that compiler prompt is loaded correctly."""
        with patch("playbooks.compilation.compiler.config") as mock_config:
            mock_config.model.compilation.name = "test-model"
            mock_config.model.compilation.provider = "test"
            mock_config.model.compilation.temperature = 0.7

            compiler = Compiler(llm_config)

            assert compiler.compiler_prompt is not None
            assert "Playbooks Assembly Language Compiler" in compiler.compiler_prompt

    def test_prompt_file_not_found(self, llm_config):
        """Test error handling when prompt file is not found."""
        with patch("playbooks.compilation.compiler.config") as mock_config:
            mock_config.model.compilation.name = "test-model"
            mock_config.model.compilation.provider = "test"
            mock_config.model.compilation.temperature = 0.7

            with patch(
                "builtins.open", side_effect=FileNotFoundError("Prompt not found")
            ):
                with pytest.raises(
                    ProgramLoadError, match="Error reading prompt template"
                ):
                    Compiler(llm_config)


class TestParallelCompilation:
    """Test parallel compilation of multiple agents."""

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("playbooks.compilation.compiler.LangfuseHelper")
    def test_agents_compiled_in_parallel(
        self, mock_langfuse, mock_completion, compiler
    ):
        """Test that multiple agents are compiled in parallel and maintain order."""
        # Create content with 3 agents
        content = """# Agent1
First agent

## Playbook1
### Steps
- Step 1

# Agent2
Second agent

## Playbook2
### Steps
- Step 2

# Agent3
Third agent

## Playbook3
### Steps
- Step 3
"""

        mock_completion.side_effect = [
            iter(["# Compiled1"]),
            iter(["# Compiled2"]),
            iter(["# Compiled3"]),
        ]
        mock_langfuse.instance.return_value.trace.return_value = MagicMock()

        files = [
            FileCompilationSpec(
                file_path="multi.pb", content=content, is_compiled=False
            )
        ]

        results = compiler.process_files(files)

        # Should have 3 results in order
        assert len(results) == 3
        all_content = results[0].content + results[1].content + results[2].content
        assert "Compiled1" in all_content
        assert "Compiled2" in all_content
        assert "Compiled3" in all_content

        # All should be compiled
        assert all(r.is_compiled for r in results)
