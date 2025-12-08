"""Provides clean access to agent registry."""

from typing import TYPE_CHECKING, Dict, List

from playbooks.infrastructure.logging.debug_logger import debug

if TYPE_CHECKING:
    from playbooks.agents.base_agent import BaseAgent
    from playbooks.program import Program


class AgentsAccessor:
    """Access to all agents in the program.

    Provides read-only access to agent collections with proper encapsulation.
    Returns copies/views to prevent external mutation of internal state.
    """

    def __init__(self, program: "Program") -> None:
        """Initialize the agents accessor.

        Args:
            program: The Program instance containing agent registries
        """
        self._program = program

    @property
    def by_klass(self) -> Dict[str, List["BaseAgent"]]:
        """Get agents grouped by class name.

        Returns:
            Dictionary mapping class names to lists of agent instances.
            Returns a shallow copy of the dict with copied lists to prevent
            external mutation of the dictionary structure and list references.
            Note: Agent objects within lists are still references.
        """
        if not self._program or not hasattr(self._program, "agents_by_klass"):
            if not self._program:
                debug("AgentsAccessor.by_klass: program is None")
            return {}
        # Return a shallow copy of dict with copied lists to prevent external mutation
        return {k: list(v) for k, v in self._program.agents_by_klass.items()}

    @property
    def by_id(self) -> Dict[str, "BaseAgent"]:
        """Get agents by their ID.

        Returns:
            Dictionary mapping agent IDs to agent instances.
            Returns a copy to prevent external mutation.
        """
        if not self._program or not hasattr(self._program, "agents_by_id"):
            if not self._program:
                debug("AgentsAccessor.by_id: program is None")
            return {}
        # Return a copy to prevent external mutation
        return dict(self._program.agents_by_id)

    @property
    def all(self) -> List["BaseAgent"]:
        """Get all agents in the program.

        Returns:
            List of all agent instances. Returns a copy to prevent external mutation.
        """
        if not self._program or not hasattr(self._program, "agents"):
            if not self._program:
                debug("AgentsAccessor.all: program is None")
            return []
        # Return a copy to prevent external mutation
        return list(self._program.agents)
