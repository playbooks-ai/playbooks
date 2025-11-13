"""Local playbook implementations for direct execution.

This module provides playbook types that execute locally without external
server communication, including both LLM-based and Python function playbooks.
"""

from abc import abstractmethod
from typing import Any, Dict, Optional

from rich.console import Console

from playbooks.core.exceptions import ExecutionFinished
from playbooks.infrastructure.logging.debug_logger import debug

from .base import Playbook


class LocalPlaybook(Playbook):
    """Abstract base class for playbooks that execute locally.

    This class provides common functionality for playbooks that run in the local
    environment, including error handling and logging.
    """

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        agent_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source_file_path: Optional[str] = None,
        source_line_number: Optional[int] = None,
    ):
        """Initialize a local playbook.

        Args:
            name: The name/class of the playbook
            description: Human-readable description of the playbook
            agent_name: Name of the agent this playbook belongs to
            source_file_path: The file path of the source where this playbook is defined
            source_line_number: The line number in the source where this playbook is defined
        """
        super().__init__(
            name=name,
            description=description,
            agent_name=agent_name,
            metadata=metadata,
        )
        self.source_file_path = source_file_path
        self.source_line_number = source_line_number

    async def execute(self, *args, **kwargs) -> Any:
        """Execute the local playbook with error handling and logging.

        Args:
            *args: Positional arguments for the playbook
            **kwargs: Keyword arguments for the playbook

        Returns:
            The result of executing the playbook

        Raises:
            Exception: If execution fails
        """
        debug(f"Executing local playbook {self.name} with args={args}, kwargs={kwargs}")

        try:
            result = await self._execute_impl(*args, **kwargs)
            debug(f"Local playbook {self.name} completed successfully")
            return result
        except ExecutionFinished:
            raise
        except Exception as e:
            error_msg = f"Local playbook {self.name} failed: {str(e)}"
            Console(stderr=True).print(f"[bold red]ERROR:[/bold red] {error_msg}")
            raise

    @abstractmethod
    async def _execute_impl(self, *args, **kwargs) -> Any:
        """Implementation-specific execution logic.

        Subclasses must implement this method to define their execution behavior.

        Args:
            *args: Positional arguments for the playbook
            **kwargs: Keyword arguments for the playbook

        Returns:
            The result of executing the playbook
        """
        pass

    def get_description(self) -> str:
        """Get a human-readable description of this playbook.

        Returns:
            The description if available, otherwise the name
        """
        return self.description or self.name
