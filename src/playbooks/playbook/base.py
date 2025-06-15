from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Playbook(ABC):
    """Abstract base class for all playbook implementations.

    This class defines the interface that all playbook types must implement,
    whether they are local markdown playbooks, remote MCP playbooks, or other types.
    """

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        agent_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a playbook.

        Args:
            name: The name/class of the playbook
            description: Human-readable description of the playbook
            agent_name: Name of the agent this playbook belongs to
            metadata: Additional metadata for the playbook
        """
        self.name = name
        self.description = description
        self.agent_name = agent_name
        self.metadata = metadata or {}

    @property
    def public(self) -> bool:
        """Return whether this playbook is public.

        Public playbooks can be called by other agents.

        Returns:
            True if the playbook is public, False otherwise
        """
        return self.metadata.get("public", False)

    @property
    def export(self) -> bool:
        """Return whether this playbook is exported.

        Exported playbooks are available for external use.

        Returns:
            True if the playbook is exported, False otherwise
        """
        return self.metadata.get("export", False)

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Execute the playbook with the given arguments.

        Args:
            *args: Positional arguments for the playbook
            **kwargs: Keyword arguments for the playbook

        Returns:
            The result of executing the playbook

        Raises:
            Exception: If execution fails
        """
        pass

    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get the parameters schema for this playbook.

        Returns:
            A dictionary describing the expected parameters
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get a human-readable description of this playbook.

        Returns:
            A string describing what this playbook does
        """
        pass

    def __repr__(self) -> str:
        """Return a string representation of the playbook."""
        return (
            f"{self.__class__.__name__}(name='{self.name}', agent='{self.agent_name}')"
        )

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        return self.name

    def trigger_instructions(
        self, namespace: Optional[str] = None, skip_bgn: bool = True
    ) -> List[str]:
        """Get the trigger instructions for the playbook.

        Returns:
            A list of trigger instruction strings, or an empty list if no triggers.
        """
        return []
