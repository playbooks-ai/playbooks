"""
Tests for the Compiler class with agent-level compilation and caching.

The compiler now processes agents individually rather than files,
enabling better parallelization and caching at the agent level.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from playbooks.compilation.compiler import (
    Compiler,
    FileCompilationSpec,
)
from playbooks.core.exceptions import ProgramLoadError
from playbooks.utils.version import get_playbooks_version


@pytest.fixture
def compiler():
    """Create a compiler instance."""
    with patch("playbooks.compilation.compiler.config") as mock_config:
        mock_config.model.compilation.name = "test-model"
        mock_config.model.compilation.provider = "test-provider"
        mock_config.model.compilation.temperature = 0.7
        mock_config.model.compilation.max_completion_tokens = 7500
        return Compiler(use_cache=True)


@pytest.fixture
def compiler_no_cache():
    """Create a compiler instance with caching disabled."""
    with patch("playbooks.compilation.compiler.config") as mock_config:
        mock_config.model.compilation.name = "test-model"
        mock_config.model.compilation.provider = "test-provider"
        mock_config.model.compilation.temperature = 0.7
        mock_config.model.compilation.max_completion_tokens = 7500
        return Compiler(use_cache=False)


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

    @pytest.mark.asyncio
    @patch("playbooks.compilation.compiler.get_completion")
    async def test_compile_single_agent(
        self, mock_completion, compiler, single_agent_content
    ):
        """Test compiling a single agent."""
        mock_completion.return_value = iter(["# CompiledTestAgent\nCompiled content"])

        compiled = await compiler._compile_agent(single_agent_content)

        assert "CompiledTestAgent" in compiled
        assert "Playbooks Assembly Language" in compiled  # Version header
        mock_completion.assert_called_once()

    @pytest.mark.asyncio
    @patch("playbooks.compilation.compiler.get_completion")
    @patch("pathlib.Path.exists")
    async def test_compile_agent_with_caching(
        self,
        mock_exists,
        mock_completion,
        compiler,
        single_agent_content,
    ):
        """Test agent compilation with caching."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled content"])

        # First call - cache doesn't exist
        mock_exists.return_value = False

        agent_info = {"name": "TestAgent", "content": single_agent_content}

        # First compilation - should call LLM
        result1 = await compiler._compile_agent_with_caching(agent_info)
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
            result2 = await compiler._compile_agent_with_caching(agent_info)
            assert mock_completion.call_count == 0  # No LLM call

        # Results should be identical
        assert result1.content == result2.content

    @pytest.mark.asyncio
    @patch("playbooks.compilation.compiler.get_completion")
    async def test_compile_without_cache(
        self, mock_completion, compiler_no_cache, single_agent_content
    ):
        """Test compilation with caching disabled."""
        mock_completion.side_effect = [
            iter(["# CompiledAgent\nCompiled content"]),
            iter(["# CompiledAgent\nCompiled content"]),
        ]

        agent_info = {"name": "TestAgent", "content": single_agent_content}

        # Multiple compilations should all call LLM
        await compiler_no_cache._compile_agent_with_caching(agent_info)
        assert mock_completion.call_count == 1

        await compiler_no_cache._compile_agent_with_caching(agent_info)
        assert mock_completion.call_count == 2

    @pytest.mark.asyncio
    @patch("playbooks.compilation.compiler.get_completion")
    @patch("pathlib.Path.write_text")
    async def test_cache_write_failure_handling(
        self, mock_write, mock_completion, compiler, single_agent_content
    ):
        """Test graceful handling of cache write failures."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled content"])
        mock_write.side_effect = PermissionError("Cannot write cache")

        agent_info = {"name": "TestAgent", "content": single_agent_content}

        # Should complete successfully despite cache write failure
        result = await compiler._compile_agent_with_caching(agent_info)
        assert result.is_compiled is True
        assert "CompiledAgent" in result.content


class TestFileProcessing:
    """Test file processing with agent-level compilation."""

    @pytest.mark.asyncio
    @patch("playbooks.compilation.compiler.get_completion")
    @patch("pathlib.Path.exists")
    async def test_process_single_pb_file(
        self,
        mock_exists,
        mock_completion,
        compiler,
        single_agent_content,
    ):
        """Test processing a single .pb file."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled content"])
        mock_exists.return_value = False  # Cache doesn't exist

        files = [
            FileCompilationSpec(
                file_path="test.pb", content=single_agent_content, is_compiled=False
            )
        ]

        results = await compiler.process_files(files)

        assert len(results) == 1
        assert results[0].is_compiled is True
        assert "CompiledAgent" in results[0].content
        mock_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_single_pbasm_file(self, compiler):
        """Test processing a single .pbasm file (no compilation needed)."""
        compiled_content = "# AlreadyCompiled\nPre-compiled content"

        files = [
            FileCompilationSpec(
                file_path="test.pbasm", content=compiled_content, is_compiled=True
            )
        ]

        with patch.object(compiler, "_compile_agent") as mock_compile:
            results = await compiler.process_files(files)

            assert len(results) == 1
            assert results[0].is_compiled is True
            assert "AlreadyCompiled" in results[0].content
            mock_compile.assert_not_called()  # No compilation needed

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("pathlib.Path.exists")
    @pytest.mark.asyncio
    async def test_process_multiple_pb_files(
        self, mock_exists, mock_completion, compiler, multi_agent_content
    ):
        """Test processing multiple .pb files with multiple agents."""
        mock_completion.side_effect = [
            iter(["# CompiledFirst\nFirst compiled"]),
            iter(["# CompiledSecond\nSecond compiled"]),
        ]
        mock_exists.return_value = False  # Cache doesn't exist

        files = [
            FileCompilationSpec(
                file_path="multi.pb", content=multi_agent_content, is_compiled=False
            )
        ]

        results = await compiler.process_files(files)

        # Should have one result per agent
        assert len(results) == 2
        assert all(r.is_compiled for r in results)
        assert mock_completion.call_count == 2

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("pathlib.Path.exists")
    @pytest.mark.asyncio
    async def test_process_mixed_files(
        self,
        mock_exists,
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

        results = await compiler.process_files(files)

        assert len(results) == 2
        # Both agents get compiled when there are mixed file types
        assert mock_completion.call_count == 2

    @pytest.mark.asyncio
    async def test_process_all_pbasm_files(self, compiler):
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
            results = await compiler.process_files(files)

            assert len(results) == 2
            assert all(r.is_compiled for r in results)
            mock_compile.assert_not_called()  # No compilation needed

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("pathlib.Path.exists")
    @pytest.mark.asyncio
    async def test_parallel_compilation(
        self, mock_exists, mock_completion, compiler, multi_agent_content
    ):
        """Test that multiple agents are compiled."""
        mock_completion.side_effect = [iter(["# Compiled1"]), iter(["# Compiled2"])]
        mock_exists.return_value = False  # No cache exists

        files = [
            FileCompilationSpec(
                file_path="multi.pb", content=multi_agent_content, is_compiled=False
            )
        ]

        results = await compiler.process_files(files)

        # Verify compilation happened
        assert mock_completion.call_count == 2
        assert len(results) == 2  # One result per agent


class TestFrontmatterHandling:
    """Test frontmatter extraction and preservation."""

    def test_frontmatter_extraction(self, compiler, content_with_frontmatter):
        """Test extracting frontmatter from content."""
        import frontmatter

        fm_data = frontmatter.loads(content_with_frontmatter)

        assert fm_data.metadata["title"] == "Test Playbook"
        assert fm_data.metadata["author"] == "Test Author"
        assert fm_data.metadata["version"] == "1.0"

    @pytest.mark.asyncio
    @patch("playbooks.compilation.compiler.get_completion")
    async def test_frontmatter_preservation(
        self, mock_completion, compiler, content_with_frontmatter
    ):
        """Test that frontmatter is extracted at file level for duplicate detection."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled"])

        files = [
            FileCompilationSpec(
                file_path="test.pb", content=content_with_frontmatter, is_compiled=False
            )
        ]

        results = await compiler.process_files(files)

        assert len(results) == 1
        # Frontmatter is extracted at the file level for duplicate checking
        # Individual agent results get frontmatter from their compiled content
        assert results[0].is_compiled is True

    @pytest.mark.asyncio
    async def test_duplicate_frontmatter_detection(self, compiler):
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
            await compiler.process_files(files)

    @pytest.mark.asyncio
    async def test_frontmatter_in_pbasm_files(self, compiler):
        """Test frontmatter extraction from .pbasm files."""
        # For pbasm files, the agent content itself should contain frontmatter
        pbasm_content = """# CompiledAgent
Already compiled content"""

        files = [
            FileCompilationSpec(
                file_path="compiled.pbasm", content=pbasm_content, is_compiled=True
            )
        ]

        results = await compiler.process_files(files)

        assert len(results) == 1
        # For .pbasm files, frontmatter comes from the agent content itself
        # In this case, no frontmatter in agent content, so empty dict
        assert results[0].frontmatter_dict == {}
        assert results[0].is_compiled is True


class TestBackwardCompatibility:
    """Test backward compatibility with the compile() method."""

    @pytest.mark.asyncio
    @patch("playbooks.compilation.compiler.get_completion")
    @patch("pathlib.Path.exists")
    async def test_compile_method_single_file(
        self,
        mock_exists,
        mock_completion,
        compiler,
        single_agent_content,
        temp_dir,
    ):
        """Test the compile() method for backward compatibility."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled"])
        mock_exists.return_value = False  # Cache doesn't exist

        test_file = temp_dir / "test.pb"
        test_file.write_text(single_agent_content)

        frontmatter, content, cache_path = await compiler.compile(
            file_path=str(test_file)
        )

        assert "CompiledAgent" in content
        assert isinstance(cache_path, Path)
        mock_completion.assert_called_once()

    @pytest.mark.asyncio
    @patch("playbooks.compilation.compiler.get_completion")
    async def test_compile_method_with_content(
        self, mock_completion, compiler, single_agent_content
    ):
        """Test compile() method with content parameter."""
        mock_completion.return_value = iter(["# CompiledAgent\nCompiled"])

        frontmatter, content, cache_path = await compiler.compile(
            content=single_agent_content
        )

        assert "CompiledAgent" in content
        assert isinstance(cache_path, Path)

    @pytest.mark.asyncio
    async def test_compile_method_invalid_params(self, compiler):
        """Test compile() method with invalid parameters."""
        # Both file_path and content provided
        with pytest.raises(ValueError):
            await compiler.compile(file_path="test.pb", content="content")

        # Neither provided
        with pytest.raises(ValueError):
            await compiler.compile()


class TestErrorHandling:
    """Test error handling in the compiler."""

    @pytest.mark.asyncio
    async def test_no_agents_found_error(self, compiler):
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
            await compiler.process_files(files)

    @pytest.mark.asyncio
    async def test_empty_content_handling(self, compiler):
        """Test handling of empty file content."""
        files = [
            FileCompilationSpec(file_path="empty.pb", content="", is_compiled=False)
        ]

        with pytest.raises(ProgramLoadError, match="No agents found"):
            await compiler.process_files(files)

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("pathlib.Path.exists")
    @pytest.mark.asyncio
    async def test_llm_failure_handling(
        self,
        mock_exists,
        mock_completion,
        compiler,
        single_agent_content,
    ):
        """Test handling of LLM failures during compilation."""
        mock_completion.side_effect = Exception("LLM API error")
        mock_exists.return_value = False  # Cache doesn't exist, force LLM call

        files = [
            FileCompilationSpec(
                file_path="test.pb", content=single_agent_content, is_compiled=False
            )
        ]

        with pytest.raises(Exception, match="LLM API error"):
            await compiler.process_files(files)

    @patch("playbooks.compilation.compiler.get_completion")
    @patch("pathlib.Path.exists")
    @pytest.mark.asyncio
    async def test_partial_compilation_failure(
        self, mock_exists, mock_completion, compiler, multi_agent_content
    ):
        """Test handling when one agent fails to compile in multi-agent scenario."""
        # First agent compiles successfully, second fails
        mock_completion.side_effect = [
            iter(["# CompiledFirst\nFirst compiled"]),
            Exception("Second agent compilation failed"),
        ]
        mock_exists.return_value = False  # Cache doesn't exist, force LLM calls

        files = [
            FileCompilationSpec(
                file_path="multi.pb", content=multi_agent_content, is_compiled=False
            )
        ]

        with pytest.raises(Exception, match="Second agent compilation failed"):
            await compiler.process_files(files)


class TestLLMConfiguration:
    """Test LLM configuration handling."""

    def test_llm_config_initialization(self):
        """Test that LLM config is properly initialized."""
        with patch("playbooks.compilation.compiler.config") as mock_config:
            mock_config.model.compilation.name = "claude-3"
            mock_config.model.compilation.provider = "anthropic"
            mock_config.model.compilation.temperature = 0.5
            mock_config.model.compilation.max_completion_tokens = 7500

            compiler = Compiler()

            assert compiler.llm_config.model == "claude-3"
            assert compiler.llm_config.provider == "anthropic"
            assert compiler.llm_config.temperature == 0.5

    def test_api_key_determination(self):
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
                mock_config.model.compilation.max_completion_tokens = 7500

                with patch.dict("os.environ", {env_var: expected_key}):
                    compiler = Compiler()
                    assert compiler.llm_config.api_key == expected_key

    def test_vertex_ai_no_api_key_required(self):
        """Test that Vertex AI models don't require an API key.

        Vertex AI uses gcloud Application Default Credentials (ADC) instead of API keys.
        LiteLLM handles this authentication automatically when api_key is None.
        See: https://github.com/playbooks-ai/playbooks/issues/73
        """
        with patch("playbooks.compilation.compiler.config") as mock_config:
            mock_config.model.compilation.name = "vertex_ai/gemini-1.5-flash"
            mock_config.model.compilation.provider = "vertex_ai"
            mock_config.model.compilation.temperature = 0.7
            mock_config.model.compilation.max_completion_tokens = 7500

            # No API key environment variables set - should not raise
            with patch.dict("os.environ", {}, clear=True):
                compiler = Compiler()
                # API key should be None - LiteLLM will use gcloud ADC
                assert compiler.llm_config.api_key is None
                assert compiler.llm_config.model == "vertex_ai/gemini-1.5-flash"
                assert compiler.llm_config.provider == "vertex_ai"

    def test_bedrock_no_api_key_required(self):
        """Test that AWS Bedrock models don't require an API key.

        Bedrock uses AWS credential chain instead of API keys.
        LiteLLM handles this authentication automatically when api_key is None.
        """
        with patch("playbooks.compilation.compiler.config") as mock_config:
            mock_config.model.compilation.name = "bedrock/anthropic.claude-v2"
            mock_config.model.compilation.provider = "bedrock"
            mock_config.model.compilation.temperature = 0.7
            mock_config.model.compilation.max_completion_tokens = 7500

            # No API key environment variables set - should not raise
            with patch.dict("os.environ", {}, clear=True):
                compiler = Compiler()
                # API key should be None - LiteLLM will use AWS credentials
                assert compiler.llm_config.api_key is None
                assert compiler.llm_config.model == "bedrock/anthropic.claude-v2"

    def test_vertex_ai_claude_no_api_key_required(self):
        """Test that Claude models on Vertex AI don't require ANTHROPIC_API_KEY.

        When using Claude via Vertex AI (vertex_ai/claude-*), authentication
        should use gcloud ADC, not ANTHROPIC_API_KEY.
        See: https://github.com/playbooks-ai/playbooks/issues/73
        """
        with patch("playbooks.compilation.compiler.config") as mock_config:
            mock_config.model.compilation.name = "vertex_ai/claude-sonnet-4"
            mock_config.model.compilation.provider = "vertex_ai"
            mock_config.model.compilation.temperature = 0.7
            mock_config.model.compilation.max_completion_tokens = 7500

            # No API keys set - should work because Vertex AI uses ADC
            with patch.dict("os.environ", {}, clear=True):
                compiler = Compiler()
                assert compiler.llm_config.api_key is None
                assert compiler.llm_config.model == "vertex_ai/claude-sonnet-4"


class TestPromptHandling:
    """Test compiler prompt handling."""

    def test_prompt_loading(self):
        """Test that compiler prompt is loaded correctly."""
        with patch("playbooks.compilation.compiler.config") as mock_config:
            mock_config.model.compilation.name = "test-model"
            mock_config.model.compilation.provider = "test"
            mock_config.model.compilation.temperature = 0.7
            mock_config.model.compilation.max_completion_tokens = 7500

            compiler = Compiler()

            assert compiler.compiler_prompt is not None
            assert "Playbooks Assembly Language Compiler" in compiler.compiler_prompt

    def test_prompt_file_not_found(self):
        """Test error handling when prompt file is not found."""
        with patch("playbooks.compilation.compiler.config") as mock_config:
            mock_config.model.compilation.name = "test-model"
            mock_config.model.compilation.provider = "test"
            mock_config.model.compilation.temperature = 0.7
            mock_config.model.compilation.max_completion_tokens = 7500

            with patch(
                "builtins.open", side_effect=FileNotFoundError("Prompt not found")
            ):
                with pytest.raises(
                    ProgramLoadError, match="Error reading prompt template"
                ):
                    Compiler()


class TestParallelCompilation:
    """Test parallel compilation of multiple agents."""

    @patch("playbooks.compilation.compiler.get_completion")
    @pytest.mark.asyncio
    async def test_agents_compiled_in_parallel(self, mock_completion, compiler):
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

        files = [
            FileCompilationSpec(
                file_path="multi.pb", content=content, is_compiled=False
            )
        ]

        results = await compiler.process_files(files)

        # Should have 3 results in order
        assert len(results) == 3
        all_content = results[0].content + results[1].content + results[2].content
        assert "Compiled1" in all_content
        assert "Compiled2" in all_content
        assert "Compiled3" in all_content

        # All should be compiled
        assert all(r.is_compiled for r in results)
