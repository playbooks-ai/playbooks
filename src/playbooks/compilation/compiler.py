"""Playbook compilation system.

This module handles the compilation of playbook files from various formats
(.pb, .md) into executable Python code, with support for LLM-based processing,
metadata extraction, and parallel compilation.
"""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterator, List, NamedTuple, Optional, Tuple

import frontmatter
from rich.console import Console

from playbooks.compilation.markdown_to_ast import (
    markdown_to_ast,
    refresh_markdown_attributes,
)
from playbooks.config import config
from playbooks.core.exceptions import ProgramLoadError
from playbooks.utils.langfuse_helper import LangfuseHelper
from playbooks.utils.llm_config import LLMConfig
from playbooks.utils.llm_helper import (
    _check_llm_calls_allowed,
    get_completion,
    get_messages_for_prompt,
)
from playbooks.utils.version import get_playbooks_version

console = Console(stderr=True)  # All compiler output to stderr


class FileCompilationSpec(NamedTuple):
    """Specification for a file to be compiled."""

    file_path: str
    content: str
    is_compiled: bool


class FileCompilationResult(NamedTuple):
    """Result of compiling a file."""

    file_path: str
    frontmatter_dict: dict
    content: str
    is_compiled: bool
    compiled_file_path: str


class Compiler:
    """
    Compiles Markdown playbooks into a format with line types and numbers for processing.
    Uses agent-level caching to avoid redundant LLM calls.
    """

    def __init__(self, llm_config: LLMConfig, use_cache: bool = True) -> None:
        """
        Initialize the compiler with LLM configuration.

        Args:
            llm_config: Configuration for the language model
            use_cache: Whether to use compilation caching
        """
        compilation_model = config.model.compilation

        self.llm_config = llm_config.copy()
        self.llm_config.model = compilation_model.name
        self.llm_config.provider = compilation_model.provider
        self.llm_config.temperature = compilation_model.temperature

        # Re-determine API key after model change
        if "claude" in self.llm_config.model:
            self.llm_config.api_key = os.environ.get("ANTHROPIC_API_KEY")
        elif "gemini" in self.llm_config.model:
            self.llm_config.api_key = os.environ.get("GEMINI_API_KEY")
        elif "groq" in self.llm_config.model:
            self.llm_config.api_key = os.environ.get("GROQ_API_KEY")
        elif "openrouter" in self.llm_config.model:
            self.llm_config.api_key = os.environ.get("OPENROUTER_API_KEY")
        else:
            # Default to OpenAI for other models
            self.llm_config.api_key = os.environ.get("OPENAI_API_KEY")

        self.use_cache = use_cache
        self.prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts/preprocess_playbooks.txt",
        )

        # Load compiler prompt once
        try:
            with open(self.prompt_path, "r") as f:
                self.compiler_prompt = f.read()
        except (IOError, OSError) as e:
            raise ProgramLoadError(f"Error reading prompt template: {str(e)}") from e

    def process_files(
        self, files: List[FileCompilationSpec]
    ) -> List[FileCompilationResult]:
        """
        Process files and compile them with agent-level caching.

        Args:
            files: List of FileCompilationSpec objects

        Returns:
            List of FileCompilationResult objects
        """
        # Combine all file contents into one document
        all_content_parts = []
        all_frontmatter = {}

        for file_spec in files:
            fm_data = frontmatter.loads(file_spec.content)

            # Collect frontmatter
            if fm_data.metadata:
                for key, value in fm_data.metadata.items():
                    if key in all_frontmatter:
                        raise ValueError(
                            f"Duplicate frontmatter attribute '{key}' found. "
                            f"Previously defined with value: {all_frontmatter[key]}"
                        )
                    all_frontmatter[key] = value

            # Add content (without frontmatter)
            all_content_parts.append(fm_data.content)

        # Combine all content
        combined_content = "\n\n".join(all_content_parts)

        # Extract agents from combined content
        agents = self._extract_agents(combined_content)

        if not agents:
            raise ProgramLoadError("No agents found in the provided files")

        # Check if all content is from .pbasm files (all files are compiled)
        all_compiled = all(f.is_compiled for f in files)

        # Compile agents in parallel
        compilation_results = []

        if all_compiled:
            # No compilation needed - process sequentially since no LLM calls
            for agent_info in agents:
                agent_name = agent_info["name"]
                agent_content = agent_info["content"]

                # Still generate cache path for tracking
                cache_key = self._generate_cache_key(agent_content)
                cache_path = self._get_cache_path(agent_name, cache_key)

                fm_data = frontmatter.loads(agent_content)
                compilation_results.append(
                    FileCompilationResult(
                        file_path=cache_path,
                        frontmatter_dict=fm_data.metadata,
                        content=fm_data.content,
                        is_compiled=True,
                        compiled_file_path=str(cache_path),
                    )
                )
        else:
            # Need compilation - use parallel processing for LLM calls
            with ThreadPoolExecutor(max_workers=min(len(agents), 4)) as executor:
                # Submit all compilation tasks with their original index
                future_to_index = {
                    executor.submit(self._compile_agent_with_caching, agent_info): i
                    for i, agent_info in enumerate(agents)
                }

                # Collect results maintaining original order
                results_by_index = {}
                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        result = future.result()
                        results_by_index[index] = result
                    except Exception as exc:
                        agent_name = agents[index]["name"]
                        console.print(
                            f"[red]Agent {agent_name} compilation failed: {exc}[/red]"
                        )
                        raise

                # Sort results by original index to maintain order
                compilation_results = [results_by_index[i] for i in range(len(agents))]

        compilation_results[0].frontmatter_dict.update(all_frontmatter)
        return compilation_results

    def compile(
        self, file_path: Optional[str] = None, content: Optional[str] = None
    ) -> Tuple[dict, str, Path]:
        """Compile a single .pb file.

        Args:
            file_path: Path to the file being compiled (optional if content provided)
            content: File content to compile (optional if file_path provided)

        Returns:
            Tuple of (frontmatter_dict, compiled_content, cache_path)

        Raises:
            ValueError: If neither file_path nor content is provided, or both are provided
        """
        if not file_path and not content:
            raise ValueError("Either file_path or content must be provided")

        if file_path and content:
            raise ValueError(
                "Cannot provide both file_path and content - use one or the other"
            )

        if file_path:
            with open(file_path, "r") as f:
                content = f.read()
        # else: content is already set

        # Create a FileCompilationSpec and process it
        spec = FileCompilationSpec(
            file_path=file_path,
            content=content,
            is_compiled=file_path and file_path.endswith(".pbasm"),
        )

        results = self.process_files([spec])
        result = results[0]

        return result.frontmatter_dict, result.content, Path(result.compiled_file_path)

    def _extract_agents(self, content: str) -> List[Dict[str, str]]:
        """Extract individual agents from markdown content.

        Parses markdown AST and groups content under H1 headings as agents.

        Args:
            content: Markdown content (already has frontmatter removed)

        Returns:
            List of agent dictionaries with 'name' and 'content' keys
        """
        # Parse markdown AST
        ast = markdown_to_ast(content)

        agents = []
        current_h1 = None

        for child in ast.get("children", []):
            if child["type"] == "h1":
                # Start new agent
                current_h1 = {
                    "name": child.get("text", "").strip(),
                    "content": child.get("markdown", "") + "\n",
                }
                agents.append(current_h1)
            elif current_h1:
                # Accumulate content for current agent
                current_h1["content"] += child.get("markdown", "") + "\n"

        return agents

    def _generate_cache_key(self, agent_content: str) -> str:
        """
        Generate a cache key for an agent based on prompt and content.

        Args:
            agent_content: The agent content (after all imports inlined)

        Returns:
            16-character hash key for cache filename
        """
        combined = self.compiler_prompt + agent_content
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _get_cache_path(self, agent_name: str, cache_key: str) -> Path:
        """
        Get the cache file path for an agent.

        Args:
            agent_name: Name of the agent
            cache_key: Hash key for cache

        Returns:
            Cache file path
        """
        cache_dir = Path(".pbasm_cache")
        # Sanitize agent name for filesystem
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in agent_name)
        cache_filename = f"{safe_name}_{cache_key}.pbasm"
        return cache_dir / cache_filename

    def _compile_agent_with_caching(
        self, agent_info: Dict[str, str]
    ) -> FileCompilationResult:
        """Compile a single agent with caching, suitable for parallel execution.

        Checks cache first, compiles if needed, and saves result to cache.

        Args:
            agent_info: Dictionary with 'name' and 'content' keys

        Returns:
            FileCompilationResult for the compiled agent
        """
        agent_name = agent_info["name"]
        agent_content = agent_info["content"]

        # Check if LLM calls (including compilation) are allowed in this context
        # This prevents unit tests from bypassing the check via compilation cache
        if not _check_llm_calls_allowed():
            raise RuntimeError(
                "LLM calls (including compilation) are not allowed in this context (likely a unit test).\n"
                "Either use pre-compiled .pbasm files or move this test to tests/integration/.\n"
                "Compilation requires LLM calls even when using cached results."
            )

        # Generate cache key and path
        cache_key = self._generate_cache_key(agent_content)
        cache_path = self._get_cache_path(agent_name, cache_key)

        if cache_path.exists() and self.use_cache:
            # Use cached version
            compiled_agent = cache_path.read_text()
        else:
            # Print to stderr so it doesn't pollute stdout when piping
            import sys

            print(f"  Compiling agent: {agent_name}", file=sys.stderr)

            compiled_agent = self._compile_agent(agent_content)

            # Cache the result
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                ast = markdown_to_ast(compiled_agent)
                refresh_markdown_attributes(ast)
                compiled_agent = ast["markdown"].strip()
                cache_path.write_text(compiled_agent)
            except (OSError, IOError, PermissionError):
                # Cache write failed, continue without caching
                pass

        fm_data = frontmatter.loads(compiled_agent)
        return FileCompilationResult(
            file_path=cache_path,
            frontmatter_dict=fm_data.metadata,
            content=fm_data.content,
            is_compiled=True,
            compiled_file_path=str(cache_path),
        )

    def _compile_agent(self, agent_content: str) -> str:
        """
        Compile a single agent using LLM.

        Args:
            agent_content: Agent markdown content

        Returns:
            Compiled agent content
        """
        # Replace the playbooks placeholder
        prompt = self.compiler_prompt.replace("{{PLAYBOOKS}}", agent_content)

        # Get LLM response
        messages = get_messages_for_prompt(prompt)
        langfuse_span = LangfuseHelper.instance().start_observation(
            name="compile_agent", as_type="generation", input=agent_content
        )

        response: Iterator[str] = get_completion(
            llm_config=self.llm_config,
            messages=messages,
            stream=False,
        )

        compiled = next(response)
        langfuse_span.update(output=compiled)
        langfuse_span.end()

        version = get_playbooks_version()
        compiled = (
            f"""<!-- 
============================================
Playbooks Assembly Language v{version}
============================================ 
-->

"""
            + compiled
        )

        return compiled
