import logging
import traceback
from abc import abstractmethod
from typing import Any, Dict, Optional

from playbooks.exceptions import ExecutionFinished

from .base import Playbook

logger = logging.getLogger(__name__)


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
    ):
        """Initialize a local playbook.

        Args:
            name: The name/class of the playbook
            description: Human-readable description of the playbook
            agent_name: Name of the agent this playbook belongs to
        """
        super().__init__(
            name=name,
            description=description,
            agent_name=agent_name,
            metadata=metadata,
        )

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
        logger.debug(
            f"Executing local playbook {self.name} with args={args}, kwargs={kwargs}"
        )

        try:
            result = await self._execute_impl(*args, **kwargs)
            logger.debug(f"Local playbook {self.name} completed successfully")
            return result
        except ExecutionFinished:
            raise
        except Exception as e:
            logger.error(
                f"Local playbook {self.name} failed: {str(e)}\n\n{traceback.format_exc()}"
            )
            return f"Error: {str(e)}"

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
