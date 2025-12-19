"""Main Playbooks class for orchestrating AI agent systems.

This module provides the primary interface for loading, compiling, and executing
playbooks with AI agents. It handles file processing, metadata extraction, and
coordination between various system components.
"""

import uuid
from functools import reduce
from pathlib import Path
from typing import Any, Dict, List, Optional

import frontmatter

from playbooks.compilation.compiler import (
    Compiler,
    FileCompilationResult,
    FileCompilationSpec,
)
from playbooks.compilation.loader import Loader
from playbooks.infrastructure.event_bus import EventBus
from playbooks.infrastructure.logging.setup import configure_logging
from playbooks.utils.llm_config import LLMConfig

from .program import Program

# Configure logging at module import
configure_logging()


class Playbooks:
    """Main class for orchestrating AI agent playbook execution.

    Handles loading, compilation, and execution of playbooks with support for
    multiple file formats, metadata extraction, and agent coordination.
    """

    def __init__(
        self,
        program_paths: List[str],
        llm_config: LLMConfig = None,
        session_id: str = None,
        cli_args: Optional[Dict[str, Any]] = None,
        initial_state: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a Playbooks instance.

        Args:
            program_paths: List of file paths to playbook files (.pb or .pbasm)
            llm_config: Configuration for LLM services, uses defaults if None
            session_id: Unique identifier for this session, generated if None
            cli_args: Optional CLI arguments to pass to BGN playbook execution
            initial_state: Optional initial state variables to set on all agents
        """
        self.program_paths = program_paths
        if llm_config is None:
            self.llm_config = LLMConfig()
        else:
            self.llm_config = llm_config.copy()
        self.session_id = session_id or str(uuid.uuid4())
        self.cli_args = cli_args or {}
        self.initial_state = initial_state or {}

        # Load files
        program_file_tuples = Loader.read_program_files(program_paths)
        self.program_files = [
            FileCompilationSpec(file_path=fp, content=content, is_compiled=is_comp)
            for fp, content, is_comp in program_file_tuples
        ]
        self.program_content = "\n\n".join(
            reduce(
                lambda content, item: content + [item.content], self.program_files, []
            )
        )

        # Compilation and Program creation will be done in async initialize() method
        self.compiled_program_files = None
        self.program_metadata = {}
        self.event_bus = EventBus(self.session_id)
        self.program = None

    async def initialize(self):
        """Initialize the playbook execution environment and agents."""
        # Compile files if needed
        if self.compiled_program_files is None:
            all_files_compiled = all(
                file_spec.is_compiled for file_spec in self.program_files
            )

            if all_files_compiled:
                # Skip compilation - convert FileCompilationSpec to FileCompilationResult directly
                self.compiled_program_files = []
                for file_spec in self.program_files:
                    fm_data = frontmatter.loads(file_spec.content)
                    self.compiled_program_files.append(
                        FileCompilationResult(
                            file_path=file_spec.file_path,
                            frontmatter_dict=fm_data.metadata,
                            content=fm_data.content,
                            is_compiled=True,
                            compiled_file_path=file_spec.file_path,
                        )
                    )
            else:
                # Some files need compilation
                compiler = Compiler(event_bus=self.event_bus)
                self.compiled_program_files = await compiler.process_files(
                    self.program_files
                )

            # Extract and apply frontmatter from all files (.pb and .pbasm)
            for i, result in enumerate(self.compiled_program_files):
                if result.frontmatter_dict:
                    # Check for duplicate attributes
                    for key, value in result.frontmatter_dict.items():
                        if key in self.program_metadata:
                            raise ValueError(
                                f"Duplicate frontmatter attribute '{key}' found in {result.file_path}. "
                                f"Previously defined with value: {self.program_metadata[key]}"
                            )
                        self.program_metadata[key] = value

            # Apply program metadata
            self._apply_program_metadata()

        # Create Program if not already created
        if self.program is None:
            compiled_program_paths = [
                result.compiled_file_path for result in self.compiled_program_files
            ]
            # Build source_file_paths mapping - map each compiled file back to its original source
            # Multiple compiled files can come from the same original .pb file
            source_file_paths = []
            for result in self.compiled_program_files:
                # Find the original source file by matching the compiled path's base name
                # or using direct mapping from program_files
                original_source = None
                for file_spec in self.program_files:
                    # The file_spec has the original path before compilation
                    if not file_spec.is_compiled:
                        # This was a .pb file that got compiled
                        original_source = file_spec.file_path
                        break

                if not original_source and self.program_paths:
                    # Fallback to first program path
                    original_source = self.program_paths[0]

                # Resolve to absolute path immediately
                if original_source:
                    original_source = str(Path(original_source).resolve())

                source_file_paths.append(original_source)

            self.program = Program(
                event_bus=self.event_bus,
                program_paths=self.program_paths,
                compiled_program_paths=compiled_program_paths,
                source_file_paths=source_file_paths,
                metadata=self.program_metadata,
                cli_args=self.cli_args,
                initial_state=self.initial_state,
            )

        # Initialize program to create agents
        await self.program.initialize()

    async def begin(self):
        """Start execution of the playbook."""
        await self.program.begin()

    async def shutdown(self):
        """Shutdown the program."""
        # Shutdown the program
        await self.program.shutdown()

    def _apply_program_metadata(self):
        """Apply program-level metadata from frontmatter."""
        for key, value in self.program_metadata.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def get_agent_errors(self):
        """Get a list of all agent errors that have occurred.

        This method provides visibility into agent failures for framework builders
        and playbook authors using the Playbooks class programmatically.

        Returns:
            List of error dictionaries with agent_id, error, and error_type
        """
        if not self.program:
            return []
        return self.program.get_agent_errors()

    def has_agent_errors(self) -> bool:
        """Check if any agents have had errors.

        Returns:
            True if any agent has experienced an error during execution
        """
        if not self.program:
            return False
        return self.program.has_agent_errors()

    def check_execution_health(self) -> dict:
        """Get a comprehensive health check of the playbook execution.

        Returns:
            Dictionary with execution status, error count, and error details
        """
        if not self.program:
            return {
                "status": "not_initialized",
                "has_errors": False,
                "error_count": 0,
                "errors": [],
            }

        errors = self.get_agent_errors()
        return {
            "status": "finished" if self.program.execution_finished else "running",
            "has_errors": len(errors) > 0,
            "error_count": len(errors),
            "errors": errors,
            "execution_finished": self.program.execution_finished,
        }
