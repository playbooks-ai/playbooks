"""Remote playbook implementations for external server execution.

This module provides playbooks that execute on remote servers via protocols
like MCP (Model Context Protocol), enabling distributed agent execution.
"""

import logging
from typing import Any, Callable, Dict, Optional

from .base import Playbook

logger = logging.getLogger(__name__)


class RemotePlaybook(Playbook):
    """A playbook that executes on a remote system.

    This class represents playbooks that are executed remotely, such as
    through MCP (Model Context Protocol) or other remote execution mechanisms.
    """

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        agent_name: Optional[str] = None,
        execute_fn: Optional[Callable] = None,
        parameters: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a remote playbook.

        Args:
            name: The name of the playbook
            description: Human-readable description of the playbook
            agent_name: Name of the agent this playbook belongs to
            execute_fn: Function to call for remote execution
            parameters: Schema describing the expected parameters
            timeout: Timeout for remote execution in seconds
            metadata: Additional metadata for the playbook
        """
        super().__init__(name, description, agent_name, metadata)
        self.execute_fn = execute_fn
        self.parameters = parameters or {}
        self.timeout = timeout

    @property
    def signature(self) -> str:
        """Get the signature of the remote playbook.

        Returns:
            The signature of the remote playbook
        """
        return f"{self.name}({', '.join([f'{param}: {type(param).__name__}' for param in self.parameters])})"

    async def execute(self, *args, **kwargs) -> Any:
        """Execute the remote playbook.

        Args:
            *args: Positional arguments for the playbook
            **kwargs: Keyword arguments for the playbook

        Returns:
            The result of executing the remote playbook

        Raises:
            ValueError: If no execution function is configured
            Exception: If remote execution fails
        """
        if not self.execute_fn:
            raise ValueError(f"Remote playbook {self.name} has no execution function")

        logger.debug(
            f"Executing remote playbook {self.name} with args={args}, kwargs={kwargs}"
        )

        try:
            # Execute the remote function
            if self.timeout:
                # TODO: Add timeout handling when we implement the transport layer
                result = await self.execute_fn(*args, **kwargs)
            else:
                result = await self.execute_fn(*args, **kwargs)

            logger.debug(f"Remote playbook {self.name} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Remote playbook {self.name} failed: {str(e)}")
            raise

    def get_parameters(self) -> Dict[str, Any]:
        """Get the parameters schema for this playbook.

        Returns:
            A dictionary describing the expected parameters
        """
        return self.parameters

    def get_description(self) -> str:
        """Get a human-readable description of this playbook.

        Returns:
            The description if available, otherwise the name
        """
        return self.description or self.name

    def create_namespace_function(self, agent) -> "Callable":
        """RemotePlaybooks should not be added to namespace.

        Raises:
            NotImplementedError: RemotePlaybooks don't support namespace functions
        """
        raise NotImplementedError("RemotePlaybooks should not be added to namespace")

    def __repr__(self) -> str:
        """Return a string representation of the playbook."""
        return f"RemotePlaybook {self.agent_name}.{self.name}: {self.description}"
