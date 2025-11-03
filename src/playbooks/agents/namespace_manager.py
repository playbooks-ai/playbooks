"""Agent namespace management for execution environments.

This module provides utilities for managing Python namespaces during
agent execution, including playbook function registration and variable scoping.
"""

from typing import Any, Dict

from playbooks.playbook_decorator import playbook_decorator


class AgentNamespaceManager:
    """Manages Python namespace for agent execution environment."""

    def __init__(self, namespace: Dict[str, Any] = None):
        self.namespace = namespace if namespace is not None else {}

    def prepare_execution_environment(self) -> Dict[str, Any]:
        """Prepare the execution environment for code blocks.

        Returns:
            Dict[str, Any]: Environment dictionary with necessary bindings
        """
        environment = {}

        environment.update(
            {
                "playbook": playbook_decorator,  # Inject decorator
                "__builtins__": __builtins__,  # Safe default
            }
        )

        return environment
