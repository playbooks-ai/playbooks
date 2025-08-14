import os
from functools import lru_cache
from pathlib import Path
from typing import Iterator, List, Tuple

import frontmatter
from rich.console import Console

from .exceptions import ProgramLoadError
from .utils.langfuse_helper import LangfuseHelper
from .utils.llm_config import LLMConfig
from .utils.llm_helper import get_completion, get_messages_for_prompt
from .utils.markdown_to_ast import (
    markdown_to_ast,
)

console = Console()


class Compiler:
    """
    Compiles Markdown playbooks into a format with line types and numbers for processing.

    The Compiler uses LLM to preprocess playbook content by adding line type codes,
    line numbers, and other metadata that enables the interpreter to understand the
    structure and flow of the playbook. It acts as a preprocessing step before the
    playbook is converted to an AST and executed.

    It validates basic playbook requirements before compilation, including checking
    for required headers that define agent name and playbook structure.
    """

    def __init__(self, llm_config: LLMConfig, use_cache: bool = True) -> None:
        """
        Initialize the compiler with LLM configuration.

        Args:
            llm_config: Configuration for the language model
            use_cache: Whether to use compilation caching
        """
        self.llm_config = llm_config.copy()
        self.llm_config.model = os.getenv("COMPILER_MODEL", self.llm_config.model)
        self.use_cache = use_cache
        self.playbooks_version = self._get_playbooks_version()
        self.prompt_path = os.path.join(
            os.path.dirname(__file__), "prompts/preprocess_playbooks.txt"
        )

    def process_files(
        self, files: List[Tuple[str, str, bool]]
    ) -> List[Tuple[str, dict, str, bool]]:
        """
        Process files individually and combine results.

        Args:
            files: List of (file_path, content, is_compiled) tuples

        Returns:
            List of (file_path, frontmatter_dict, content, is_compiled) tuples
        """
        compiled_files = []

        for file_path, content, is_compiled in files:
            if is_compiled:
                # Already compiled, extract frontmatter and content
                fm_data = frontmatter.loads(content)
                compiled_files.append(
                    (file_path, fm_data.metadata, fm_data.content, is_compiled)
                )
            else:
                # Compile individual file
                frontmatter_dict, compiled_content = self.process_single_file(
                    file_path, content
                )
                compiled_files.append(
                    (file_path, frontmatter_dict, compiled_content, is_compiled)
                )

        return compiled_files

    @lru_cache(maxsize=128)
    def process_single_file(self, file_path: str, content: str) -> Tuple[dict, str]:
        """
        Compile a single .pb file with caching support and agent-level compilation.

        Args:
            file_path: Path to the file being compiled
            content: File content to compile (may include frontmatter)

        Returns:
            Tuple[dict, str]: (frontmatter_dict, compiled_content)
        """
        source_path = Path(file_path)

        # Check cache first (file-level, not agent-level)
        if self.use_cache:
            cache_path = self._get_cache_path(file_path)
            if self._is_cache_valid(source_path, cache_path):
                cached_content = cache_path.read_text()
                fm_data = frontmatter.loads(cached_content)
                return fm_data.metadata, fm_data.content

        # Extract and preserve frontmatter
        fm_data = frontmatter.loads(content)
        content_without_frontmatter = fm_data.content

        # Extract agents from content without frontmatter
        agents = self._extract_agents(content_without_frontmatter)

        if len(agents) == 0:
            raise ProgramLoadError(f"No agents found in {file_path}")

        if len(agents) == 1:
            # Single agent - compile just the agent
            if not file_path.startswith("__"):  # internal like __builtin_playbooks.pb
                console.print(f"[dim pink]Compiling {file_path}[/dim pink]")
            compiled = self._compile_agent(agents[0]["content"])
        else:
            # Multiple agents - compile each independently
            console.print(
                f"[dim pink]Compiling {file_path} ({len(agents)} agents)[/dim pink]"
            )
            compiled_agents = []

            for i, agent_info in enumerate(agents):
                agent_name = agent_info["name"]
                agent_content = agent_info["content"]

                # Compile individual agent
                console.print(f"  [dim pink]Agent: {agent_name}[/dim pink]")
                compiled_agent = self._compile_agent(agent_content)
                compiled_agents.append(compiled_agent)

            # Combine all agents
            compiled = "\n\n".join(compiled_agents)

        # Cache the result (with frontmatter for proper storage)
        if self.use_cache:
            try:
                cache_path = self._get_cache_path(file_path)
                cache_path.parent.mkdir(exist_ok=True)

                # Add frontmatter back for caching
                if fm_data.metadata:
                    compiled_with_frontmatter = frontmatter.Post(
                        compiled, **fm_data.metadata
                    )
                    compiled_content_with_frontmatter = frontmatter.dumps(
                        compiled_with_frontmatter
                    )
                else:
                    compiled_content_with_frontmatter = compiled

                cache_path.write_text(compiled_content_with_frontmatter)
            except (OSError, IOError, PermissionError):
                # Cache write failed, but compilation succeeded - continue silently
                console.print(
                    f"[dim yellow]Warning: Could not write cache for {file_path}[/dim yellow]"
                )
                pass

        return fm_data.metadata, compiled

    def _compile_content(self, content: str) -> str:
        """
        Internal method to compile preprocessed content.

        Args:
            content: Preprocessed content to compile

        Returns:
            str: Compiled content
        """
        # Basic validation of playbook format
        if not content.strip():
            raise ProgramLoadError("Empty playbook content")

        # Check for required H1 and H2 headers
        lines = content.split("\n")
        found_h1 = False
        found_h2 = False

        for line in lines:
            if line.startswith("# "):
                found_h1 = True
            elif line.startswith("## ") or "@playbook" in line:
                found_h2 = True

        if not found_h1:
            raise ProgramLoadError(
                "Failed to parse playbook: Missing H1 header (Agent name)"
            )
        if not found_h2:
            raise ProgramLoadError(
                "Failed to parse playbooks program: No playbook found"
            )

        # Load and prepare the prompt template
        prompt_path = os.path.join(
            os.path.dirname(__file__), "prompts/preprocess_playbooks.txt"
        )
        try:
            with open(prompt_path, "r") as f:
                prompt = f.read()
        except (IOError, OSError) as e:
            raise ProgramLoadError(f"Error reading prompt template: {str(e)}") from e

        prompt = prompt.replace("{{PLAYBOOKS}}", content)
        messages = get_messages_for_prompt(prompt)
        langfuse_span = LangfuseHelper.instance().trace(
            name="compile_playbooks", input=content
        )

        # Get the compiled content from the LLM
        response: Iterator[str] = get_completion(
            llm_config=self.llm_config,
            messages=messages,
            stream=False,
            langfuse_span=langfuse_span,
        )

        processed_content = next(response)
        langfuse_span.update(output=processed_content)

        return processed_content

    def _get_playbooks_version(self) -> str:
        """Get the current playbooks version for cache naming."""
        try:
            from importlib.metadata import version

            return version("playbooks")
        except ImportError:
            try:
                from importlib_metadata import version

                return version("playbooks")
            except ImportError:
                return "dev"
        except Exception:
            return "dev"

    def _get_cache_path(self, file_path: str) -> Path:
        """Get cache file path following Python's model."""
        source_path = Path(file_path)
        cache_dir = source_path.parent / ".pbasm_cache"
        cache_name = f"{source_path.stem}.playbooks-{self.playbooks_version}.pbasm"
        return cache_dir / cache_name

    def _is_cache_valid(self, source_path: Path, cache_path: Path) -> bool:
        """Check if cache is still valid based on timestamps."""
        if not cache_path.exists():
            return False

        # Check source file timestamp
        try:
            source_mtime = source_path.stat().st_mtime
            cache_mtime = cache_path.stat().st_mtime

            if source_mtime > cache_mtime:
                return False

            # Check compiler prompt timestamp
            prompt_mtime = Path(self.prompt_path).stat().st_mtime
            if prompt_mtime > cache_mtime:
                return False

            return True
        except (OSError, IOError):
            # If we can't get timestamps, assume cache is invalid
            return False

    def _extract_agents(self, content: str) -> List[dict]:
        """
        Extract individual agents from markdown content.

        Args:
            content: Markdown content (should already have frontmatter removed)

        Returns:
            List of agent dictionaries with name, content, and start_line
        """
        # Parse markdown AST (content should already have frontmatter removed)
        ast = markdown_to_ast(content)

        agents = []
        current_h1 = None

        for child in ast.get("children", []):
            if child["type"] == "h1":
                # Start new agent
                current_h1 = {
                    "name": child.get("text", "").strip(),
                    "content": child.get("markdown", "") + "\n",
                    "start_line": child.get("line", 0),
                }
                agents.append(current_h1)
            elif current_h1:
                # Accumulate content for current agent
                current_h1["content"] += child.get("markdown", "") + "\n"

        return agents

    def _compile_agent(self, agent_content: str) -> str:
        """
        Compile a single agent.

        Args:
            agent_content: Agent markdown content (without frontmatter)

        Returns:
            str: Compiled agent content
        """
        # Use existing prompt with agent content only (no frontmatter)
        try:
            with open(self.prompt_path, "r") as f:
                prompt = f.read()
        except (IOError, OSError) as e:
            raise ProgramLoadError(f"Error reading prompt template: {str(e)}") from e

        # Replace the playbooks placeholder
        prompt = prompt.replace("{{PLAYBOOKS}}", agent_content)

        # Get LLM response
        messages = get_messages_for_prompt(prompt)
        langfuse_span = LangfuseHelper.instance().trace(
            name="compile_agent", input=agent_content
        )

        response = get_completion(
            llm_config=self.llm_config,
            messages=messages,
            stream=False,
            langfuse_span=langfuse_span,
        )

        compiled = next(response)
        langfuse_span.update(output=compiled)

        return compiled
