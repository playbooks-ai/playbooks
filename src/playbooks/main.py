import uuid
from functools import reduce
from typing import List

from .compiler import Compiler, FileCompilationSpec
from .event_bus import EventBus
from .loader import Loader
from .logging_setup import configure_logging
from .program import Program
from .utils.llm_config import LLMConfig

# Configure logging at module import
configure_logging()


class Playbooks:
    def __init__(
        self,
        program_paths: List[str],
        llm_config: LLMConfig = None,
        session_id: str = None,
    ):
        self.program_paths = program_paths
        if llm_config is None:
            self.llm_config = LLMConfig()
        else:
            self.llm_config = llm_config.copy()
        self.session_id = session_id or str(uuid.uuid4())

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
        compiler = Compiler(self.llm_config)
        self.compiled_program_files = compiler.process_files(self.program_files)

        # Extract and apply frontmatter from all files (.pb and .pbasm)
        self.program_metadata = {}
        # compiled_content = []
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

            # compiled_content.append(file_content)

        # Compiled agents without frontmatter
        # self.compiled_program_content = "\n\n".join(compiled_content)

        # Apply program metadata
        self._apply_program_metadata()

        self.event_bus = EventBus(self.session_id)
        compiled_program_paths = [
            compiled_file_path
            for _, _, _, _, compiled_file_path in self.compiled_program_files
        ]

        self.program = Program(
            event_bus=self.event_bus,
            program_paths=self.program_paths,
            compiled_program_paths=compiled_program_paths,
            metadata=self.program_metadata,
        )

    async def initialize(self):
        await self.program.initialize()

    async def begin(self):
        await self.program.begin()

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
